//! Staged, consent-driven signed updates + the user-data backup lifecycle.
//!
//! A signed update requires the Tauri updater key pair. The public key is
//! embedded at build time (tauri.updater.conf.json); the private key signs
//! release artifacts in CI. Default builds hold neither, so the network path is
//! gated behind the `updater` Cargo feature:
//!
//!   * default build (source/dev/CI): the plugin is NOT registered; every
//!     command reports `disabled` honestly and the UI shows a git/download note.
//!   * `--features updater` build:    the staged flow below runs for real.
//!
//! The flow is deliberately staged so nothing happens without an explicit click:
//!
//!   updater_check              metadata only, zero side effects
//!   updater_download           streams into RAM, emits `updater://progress`,
//!                              then `updater://state` {phase:"ready"} — the
//!                              signature is verified inside download()
//!   updater_cancel             aborts an in-flight download
//!   updater_install_and_restart  stops the sidecar FIRST (Windows installers
//!                              cannot replace a running exe and NSIS only kills
//!                              the main binary), snapshots the ledger, writes a
//!                              pending-update marker, installs, restarts.
//!                              On Windows install() never returns — the
//!                              installer exits us, updates, and relaunches.
//!
//! The backup has a full lifecycle, keyed by the pending-update marker:
//!   * healthy first boot after an install  -> backup retired, success recorded
//!     (feeds the UI's one-time "Updated to X" toast — honestly: no marker, no
//!     toast, so a manual reinstall never claims a backup that was never taken);
//!   * failed first boot after an install   -> ledger restored from the backup
//!     (staged copy + rename, never delete-then-copy), marker consumed;
//!   * failed boot with NO marker           -> NEVER restores. A transient
//!     sidecar failure months later must not overwrite newer ledger data.
//!
//! What is NOT gated behind the feature is the data-protection half: markers,
//! backups and restore are always compiled — a default build must still finish
//! or repair an update installed by a previous updater-enabled run.

use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Manager, Runtime};

/// Manual fallback surfaced in every error path the user might dead-end in.
pub const RELEASES_URL: &str = "https://github.com/udhawan97/Golavo/releases";

const PLATFORM: &str = if cfg!(target_os = "macos") {
    "macos"
} else if cfg!(target_os = "windows") {
    "windows"
} else {
    "other"
};

// ---------------------------------------------------------------------------
// Serializable surface shared with the frontend
// ---------------------------------------------------------------------------

#[derive(Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct StatusInfo {
    pub app_version: String,
    pub enabled: bool,
    pub platform: &'static str,
    /// An update was installed but its first (verifying) boot hasn't happened.
    pub pending_update: Option<PendingUpdate>,
    /// The persistent record of the most recent verified update.
    pub just_updated: Option<JustUpdated>,
}

#[derive(Serialize, Deserialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct PendingUpdate {
    pub from: String,
    pub to: String,
    pub at_epoch: u64,
    pub backup_taken: bool,
}

#[derive(Serialize, Deserialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct JustUpdated {
    pub from: String,
    pub to: String,
    pub at_epoch: u64,
    pub backup_taken: bool,
}

#[derive(Serialize, Clone, Debug)]
#[serde(rename_all = "camelCase")]
pub struct UpdateError {
    /// "disabled" | "busy" | "needs_move" | "unreachable" | "rate_limited"
    /// | "bad_manifest" | "install_failed" | "other"
    pub kind: &'static str,
    pub message: String,
}

#[derive(Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct CheckOutcome {
    pub available: bool,
    pub version: Option<String>,
    pub notes: Option<String>,
    pub date: Option<String>,
}

#[cfg_attr(not(feature = "updater"), allow(dead_code))]
#[derive(Serialize, Clone)]
#[serde(rename_all = "camelCase")]
struct ProgressPayload {
    downloaded: u64,
    total: Option<u64>,
}

#[cfg_attr(not(feature = "updater"), allow(dead_code))]
#[derive(Serialize, Clone)]
#[serde(rename_all = "camelCase")]
struct StatePayload {
    phase: &'static str,
    error: Option<UpdateError>,
    version: Option<String>,
}

#[cfg_attr(feature = "updater", allow(dead_code))]
fn disabled_error() -> UpdateError {
    UpdateError {
        kind: "disabled",
        message: "This build has no signed updater (source or dev build). Update via git pull \
                  or a fresh download from the releases page."
            .into(),
    }
}

#[cfg_attr(not(feature = "updater"), allow(dead_code))]
fn other_error(message: String) -> UpdateError {
    UpdateError {
        kind: "other",
        message,
    }
}

// ---------------------------------------------------------------------------
// Paths, markers, timestamps (always compiled)
// ---------------------------------------------------------------------------

/// The per-user ledger directory the sidecar reads/writes (kept in sync with lib.rs).
pub fn ledger_dir<R: Runtime>(app: &AppHandle<R>) -> Result<PathBuf, String> {
    Ok(app
        .path()
        .app_local_data_dir()
        .map_err(|e| e.to_string())?
        .join("ledger"))
}

fn backup_root<R: Runtime>(app: &AppHandle<R>) -> Result<PathBuf, String> {
    Ok(app
        .path()
        .app_local_data_dir()
        .map_err(|e| e.to_string())?
        .join("backups")
        .join("pre-update"))
}

fn updates_dir<R: Runtime>(app: &AppHandle<R>) -> Result<PathBuf, String> {
    let dir = app
        .path()
        .app_local_data_dir()
        .map_err(|e| e.to_string())?
        .join("updates");
    std::fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    Ok(dir)
}

fn now_epoch() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

fn read_json_file<T: for<'de> Deserialize<'de>, R: Runtime>(
    app: &AppHandle<R>,
    name: &str,
) -> Option<T> {
    let path = updates_dir(app).ok()?.join(name);
    let text = std::fs::read_to_string(path).ok()?;
    serde_json::from_str(&text).ok()
}

fn write_json_file<T: Serialize, R: Runtime>(app: &AppHandle<R>, name: &str, value: &T) {
    if let Ok(dir) = updates_dir(app) {
        if let Ok(text) = serde_json::to_string_pretty(value) {
            let _ = std::fs::write(dir.join(name), text);
        }
    }
}

const PENDING_FILE: &str = "pending-update.json";
const JUST_UPDATED_FILE: &str = "just-updated.json";

pub fn read_pending<R: Runtime>(app: &AppHandle<R>) -> Option<PendingUpdate> {
    read_json_file(app, PENDING_FILE)
}

fn clear_pending<R: Runtime>(app: &AppHandle<R>) {
    if let Ok(dir) = updates_dir(app) {
        let _ = std::fs::remove_file(dir.join(PENDING_FILE));
    }
}

pub fn read_just_updated<R: Runtime>(app: &AppHandle<R>) -> Option<JustUpdated> {
    read_json_file(app, JUST_UPDATED_FILE)
}

// ---------------------------------------------------------------------------
// Backup lifecycle (always compiled)
// ---------------------------------------------------------------------------

/// Copy the ledger (the only mutable user state today) into a fresh backup dir,
/// returning that dir. Called immediately before an update is installed.
///
/// On ANY failure the half-written backup dir is removed, so a partial backup
/// can never sit at the armed path masquerading as trustworthy — the caller's
/// `backup_taken` flag (false, since we Err) then truthfully means "no backup".
#[cfg_attr(not(feature = "updater"), allow(dead_code))]
pub fn backup_user_state<R: Runtime>(app: &AppHandle<R>) -> Result<PathBuf, String> {
    let backup = backup_root(app)?;
    match backup_user_state_inner(app, &backup) {
        Ok(()) => Ok(backup),
        Err(e) => {
            let _ = std::fs::remove_dir_all(&backup);
            Err(e)
        }
    }
}

fn backup_user_state_inner<R: Runtime>(app: &AppHandle<R>, backup: &Path) -> Result<(), String> {
    if backup.exists() {
        std::fs::remove_dir_all(backup).map_err(|e| e.to_string())?;
    }
    std::fs::create_dir_all(backup).map_err(|e| e.to_string())?;
    let ledger = ledger_dir(app)?;
    if ledger.exists() {
        copy_dir(&ledger, &backup.join("ledger")).map_err(|e| e.to_string())?;
    }
    Ok(())
}

/// Restore the pre-update backup over the live ledger — staged: copy the backup
/// beside the live dir, move the live dir aside (kept, never deleted), then
/// rename the staged copy into place. A failed copy can no longer lose BOTH the
/// live ledger and the backup.
pub fn restore_backup<R: Runtime>(app: &AppHandle<R>) -> Result<bool, String> {
    let backup_ledger = backup_root(app)?.join("ledger");
    if !backup_ledger.exists() {
        return Ok(false);
    }
    let live = ledger_dir(app)?;
    let parent = live
        .parent()
        .ok_or_else(|| "ledger dir has no parent".to_string())?
        .to_path_buf();
    let staging = parent.join("ledger.restoring");
    if staging.exists() {
        std::fs::remove_dir_all(&staging).map_err(|e| e.to_string())?;
    }
    copy_dir(&backup_ledger, &staging).map_err(|e| e.to_string())?;
    if live.exists() {
        // Keep only the newest displaced copy: prune older pre-restore dirs
        // before creating this one so repeated failed updates can't accumulate
        // full ledger copies without bound.
        prune_pre_restore(&parent);
        let aside = parent.join(format!("ledger.pre-restore-{}", now_epoch()));
        std::fs::rename(&live, &aside).map_err(|e| e.to_string())?;
    }
    std::fs::rename(&staging, &live).map_err(|e| e.to_string())?;
    Ok(true)
}

/// Remove every `ledger.pre-restore-*` under `parent`. Called right before a new
/// one is minted, so at most one displaced generation survives at a time.
fn prune_pre_restore(parent: &Path) {
    let Ok(entries) = std::fs::read_dir(parent) else {
        return;
    };
    for entry in entries.flatten() {
        if entry
            .file_name()
            .to_string_lossy()
            .starts_with("ledger.pre-restore-")
        {
            let _ = std::fs::remove_dir_all(entry.path());
        }
    }
}

/// After the first healthy boot on a new version, the pre-update backup has done
/// its job: move it out of the armed location so it can never be restored over
/// newer data, keeping exactly one retired generation around for forensics.
fn retire_backup<R: Runtime>(app: &AppHandle<R>, to_version: &str) {
    let Ok(armed) = backup_root(app) else { return };
    if !armed.exists() {
        return;
    }
    let Some(parent) = armed.parent().map(Path::to_path_buf) else {
        return;
    };
    let retired = parent.join(format!("retired-{to_version}"));
    if retired.exists() {
        let _ = std::fs::remove_dir_all(&retired);
    }
    let _ = std::fs::rename(&armed, &retired);
}

fn copy_dir(from: &Path, to: &Path) -> std::io::Result<()> {
    std::fs::create_dir_all(to)?;
    for entry in std::fs::read_dir(from)? {
        let entry = entry?;
        let target = to.join(entry.file_name());
        if entry.file_type()?.is_dir() {
            copy_dir(&entry.path(), &target)?;
        } else {
            std::fs::copy(entry.path(), &target)?;
        }
    }
    Ok(())
}

/// Complete a restore that was interrupted mid-swap, BEFORE the launch path
/// fabricates an empty ledger over the gap.
///
/// `restore_backup` stages as: copy backup -> `ledger.restoring`, move live ->
/// `ledger.pre-restore-<epoch>`, rename `ledger.restoring` -> `ledger`. A crash
/// between the last two renames leaves NO canonical `ledger` while a full staged
/// copy sits at `ledger.restoring`. Left alone, `create_dir_all(ledger)` at
/// launch would fabricate an EMPTY ledger, the sidecar would pass its health
/// gate serving nothing, and the user's data would appear lost. This detects
/// that exact state and finishes the swap so the correct ledger is in place.
///
/// GATED on a live pending-update marker: a real interrupted restore always
/// still has its marker (repair clears it only AFTER restore returns), so the
/// gate keeps every genuine case working while refusing to resurrect a
/// marker-less orphan (e.g. a `ledger.restoring` left by a crash whose retry
/// boot already succeeded) if the live ledger is later lost by external means.
/// No-op when a canonical ledger already exists (the common case).
pub fn recover_interrupted_restore<R: Runtime>(app: &AppHandle<R>) {
    let Ok(live) = ledger_dir(app) else { return };
    if live.exists() {
        return; // canonical ledger present — nothing was interrupted
    }
    if read_pending(app).is_none() {
        return; // no restore was in flight — never resurrect a stale orphan
    }
    let Some(parent) = live.parent().map(Path::to_path_buf) else {
        return;
    };
    let staging = parent.join("ledger.restoring");
    if !staging.exists() {
        return;
    }
    // The staged copy is complete (copy_dir finished before the live-move);
    // finishing the swap lands exactly what the restore intended. Prefer a
    // rename; if it fails (AV lock, odd FS state) fall back to a copy rather
    // than let the caller's create_dir_all mask the staged data with an empty
    // ledger — the whole point of this function.
    if std::fs::rename(&staging, &live).is_ok() {
        eprintln!("[golavo] completed an interrupted ledger restore (rename)");
    } else if copy_dir(&staging, &live).is_ok() {
        let _ = std::fs::remove_dir_all(&staging);
        eprintln!("[golavo] completed an interrupted ledger restore (copy fallback)");
    } else {
        eprintln!(
            "[golavo] WARNING: could not complete an interrupted restore; your data is safe at \
             {}",
            staging.display()
        );
    }
}

// ---------------------------------------------------------------------------
// Launch-time hooks (called from lib.rs; always compiled)
// ---------------------------------------------------------------------------

/// Healthy boot: if the previous run installed an update, the new version just
/// proved it can serve — retire the backup and record the success.
pub fn finalize_update_if_pending<R: Runtime>(app: &AppHandle<R>) {
    let Some(pending) = read_pending(app) else {
        return;
    };
    // Only claim success if the promised version is actually what is running.
    // If the install silently didn't land (e.g. relaunched into the old
    // binary), consume the marker without recording an update — the data is
    // untouched, so just disarm quietly.
    let running = app.package_info().version.to_string();
    if pending.to != running {
        eprintln!(
            "[golavo] pending update said {} but {} is running; disarming without a record",
            pending.to, running
        );
        retire_backup(app, &pending.to);
        clear_pending(app);
        return;
    }
    write_json_file(
        app,
        JUST_UPDATED_FILE,
        &JustUpdated {
            from: pending.from.clone(),
            to: pending.to.clone(),
            at_epoch: now_epoch(),
            backup_taken: pending.backup_taken,
        },
    );
    retire_backup(app, &pending.to);
    clear_pending(app);
    eprintln!(
        "[golavo] update {} -> {} verified healthy; backup retired",
        pending.from, pending.to
    );
}

/// Failed health gate: build the message for the native error dialog, restoring
/// the pre-update backup ONLY when this boot is the first one after an install
/// (marker present). The marker is consumed either way so a restore can never
/// run twice, and a marker-less failure never touches the ledger.
pub fn repair_failed_launch<R: Runtime>(app: &AppHandle<R>, health_err: &str) -> String {
    match read_pending(app) {
        Some(pending) => {
            // Only a VERIFIED backup may overwrite the live ledger. When the
            // pre-install backup didn't complete (backup_taken == false) it is not
            // trustworthy — and the install never touches the live ledger anyway —
            // so restoring a half-copy would trade good data for bad. Leave it.
            let data_note = if pending.backup_taken {
                match restore_backup(app) {
                    Ok(true) => "Your ledger was restored from the pre-update backup.",
                    _ => {
                        "The pre-update backup could not be restored automatically; \
                         it is preserved on disk under backups/pre-update."
                    }
                }
            } else {
                "Your ledger was not modified."
            };
            // Consume the marker only AFTER the restore attempt returns: a crash
            // mid-restore keeps the marker and leaves a `ledger.restoring` staging
            // dir, which recover_interrupted_restore completes on next boot.
            clear_pending(app);
            format!(
                "Golavo {} could not start after the update.\n\n{}\n\nPlease download the \
                 previous version from:\n{}\n\n(Details: {})",
                pending.to, data_note, RELEASES_URL, health_err
            )
        }
        None => format!(
            "Golavo's local engine failed to start.\n\nYour data is untouched. Try launching \
             Golavo again; if this keeps happening, download a fresh copy from:\n{}\n\n\
             (Details: {})",
            RELEASES_URL, health_err
        ),
    }
}

// ---------------------------------------------------------------------------
// Staged updater engine (feature-gated)
// ---------------------------------------------------------------------------

#[cfg(feature = "updater")]
mod engine {
    #[derive(Default, PartialEq, Clone, Copy)]
    pub enum Phase {
        #[default]
        Idle,
        Downloading,
        Ready,
    }

    #[derive(Default)]
    pub struct Inner {
        pub phase: Phase,
        pub update: Option<tauri_plugin_updater::Update>,
        pub bytes: Option<Vec<u8>>,
        pub task: Option<tauri::async_runtime::JoinHandle<()>>,
    }

    /// One updater flow at a time; the async mutex serializes the commands.
    #[derive(Default)]
    pub struct UpdaterEngine {
        pub inner: tauri::async_runtime::Mutex<Inner>,
    }
}

#[cfg(feature = "updater")]
pub use engine::UpdaterEngine;

#[cfg(feature = "updater")]
fn classify(e: &tauri_plugin_updater::Error) -> UpdateError {
    let message = e.to_string();
    let l = message.to_lowercase();
    let kind = if l.contains("dns")
        || l.contains("connect")
        || l.contains("timed out")
        || l.contains("timeout")
        || l.contains("network")
        || l.contains("sending request")
        || l.contains("unreachable")
    {
        // reqwest ignores OS proxy settings, so a corporate-proxy user lands
        // here too — the UI copy says "offline or firewall/proxy", not "offline".
        "unreachable"
    } else if l.contains("403") || l.contains("429") || l.contains("rate limit") {
        "rate_limited"
    } else if l.contains("404")
        || l.contains("json")
        || l.contains("parse")
        || l.contains("deserialize")
        || l.contains("platform")
        || l.contains("signature")
        || l.contains("semver")
    {
        // Also covers the brief mid-publish window where latest.json 404s.
        "bad_manifest"
    } else {
        "other"
    };
    UpdateError { kind, message }
}

/// Catch the macOS locations that would fail install with a cryptic error, with
/// actionable copy BEFORE downloading ~100 MB that could never install:
///   * Gatekeeper App Translocation (a read-only randomized mount);
///   * a genuinely read-only filesystem — i.e. running from the mounted DMG.
///
/// We block ONLY on a read-only *filesystem* (EROFS), never on mere permission
/// denial: `/Applications` is writable only by admins, but macOS's updater
/// prompts for an admin password on PermissionDenied and can still swap in
/// place — so a standard (non-admin) user with Golavo correctly in
/// `/Applications` must NOT be told to "move it to Applications". And an app on
/// a writable external drive under `/Volumes/` must not be blocked at all.
#[cfg(feature = "updater")]
fn install_location_blocked() -> Option<String> {
    if !cfg!(target_os = "macos") {
        return None;
    }
    let exe = std::env::current_exe().ok()?;
    if exe.to_string_lossy().contains("/AppTranslocation/") {
        return Some(
            "macOS is running Golavo from a temporary security location. Move Golavo to your \
             Applications folder with Finder, open it from there, then update."
                .into(),
        );
    }
    // Walk up to the .app bundle; its parent is where the swap must write.
    let bundle_parent = exe
        .ancestors()
        .find(|p| p.extension().is_some_and(|e| e == "app"))
        .and_then(|app_bundle| app_bundle.parent());
    if let Some(parent) = bundle_parent {
        if dir_is_read_only(parent) {
            return Some(
                "Golavo is running from a read-only location, likely straight from the \
                 downloaded disk image. Drag Golavo to your Applications folder, open it from \
                 there, then update."
                    .into(),
            );
        }
    }
    None
}

/// True only when `dir` lives on a READ-ONLY filesystem (a mounted DMG). A
/// permission failure on a writable volume (e.g. `/Applications` for a standard
/// user) returns false — the OS updater's admin-password prompt handles that,
/// so we must not pre-block it. Any other/unknown error also returns false, so
/// we never block on a false negative; a truly unwritable dir surfaces the real
/// install error later.
#[cfg(feature = "updater")]
fn dir_is_read_only(dir: &Path) -> bool {
    const EROFS: i32 = 30; // "Read-only file system"
    let probe = dir.join(format!(".golavo-write-probe-{}", std::process::id()));
    match std::fs::File::create(&probe) {
        Ok(_) => {
            let _ = std::fs::remove_file(&probe);
            false
        }
        Err(e) => e.raw_os_error() == Some(EROFS),
    }
}

// ---------------------------------------------------------------------------
// Commands (registered in both builds; non-updater builds answer "disabled")
// ---------------------------------------------------------------------------

#[tauri::command]
pub async fn updater_status<R: Runtime>(app: AppHandle<R>) -> Result<StatusInfo, UpdateError> {
    Ok(StatusInfo {
        app_version: app.package_info().version.to_string(),
        enabled: cfg!(feature = "updater"),
        platform: PLATFORM,
        pending_update: read_pending(&app),
        just_updated: read_just_updated(&app),
    })
}

/// Check only — zero side effects beyond remembering the offered update.
#[tauri::command]
pub async fn updater_check<R: Runtime>(app: AppHandle<R>) -> Result<CheckOutcome, UpdateError> {
    #[cfg(not(feature = "updater"))]
    {
        let _ = app;
        Err(disabled_error())
    }

    #[cfg(feature = "updater")]
    {
        use tauri_plugin_updater::UpdaterExt;

        let updater = app.updater().map_err(|e| other_error(e.to_string()))?;
        match updater.check().await {
            Ok(Some(update)) => {
                let outcome = CheckOutcome {
                    available: true,
                    version: Some(update.version.clone()),
                    notes: update.body.clone(),
                    date: update.date.map(|d| d.to_string()),
                };
                let engine = app.state::<UpdaterEngine>();
                let mut inner = engine.inner.lock().await;
                match inner.phase {
                    engine::Phase::Idle => inner.update = Some(update),
                    // Never clobber an in-flight download.
                    engine::Phase::Downloading => {}
                    // Staged bytes for a version that is no longer the latest
                    // are stale — drop them so the user can never install an
                    // update that is itself already outdated.
                    engine::Phase::Ready => {
                        let staged = inner.update.as_ref().map(|u| u.version.clone());
                        if staged.as_deref() != Some(update.version.as_str()) {
                            inner.bytes = None;
                            inner.phase = engine::Phase::Idle;
                            inner.update = Some(update);
                        }
                    }
                }
                Ok(outcome)
            }
            Ok(None) => Ok(CheckOutcome {
                available: false,
                version: None,
                notes: None,
                date: None,
            }),
            Err(e) => Err(classify(&e)),
        }
    }
}

/// Download the offered update into memory (signature verified inside), emitting
/// `updater://progress` then `updater://state` {phase:"ready"|"error"}.
#[tauri::command]
pub async fn updater_download<R: Runtime>(app: AppHandle<R>) -> Result<(), UpdateError> {
    #[cfg(not(feature = "updater"))]
    {
        let _ = app;
        Err(disabled_error())
    }

    #[cfg(feature = "updater")]
    {
        use tauri::Emitter;

        if let Some(message) = install_location_blocked() {
            return Err(UpdateError {
                kind: "needs_move",
                message,
            });
        }
        let engine = app.state::<UpdaterEngine>();
        let mut inner = engine.inner.lock().await;
        match inner.phase {
            engine::Phase::Downloading => {
                return Err(UpdateError {
                    kind: "busy",
                    message: "A download is already in progress.".into(),
                })
            }
            engine::Phase::Ready => {
                // Idempotent — already staged. Re-announce it, otherwise a UI
                // that just optimistically entered "downloading" waits forever
                // for an event that would never come.
                let version = inner.update.as_ref().map(|u| u.version.clone());
                let _ = app.emit(
                    "updater://state",
                    StatePayload {
                        phase: "ready",
                        error: None,
                        version,
                    },
                );
                return Ok(());
            }
            engine::Phase::Idle => {}
        }
        let Some(update) = inner.update.clone() else {
            return Err(other_error(
                "No update staged — check for updates first.".into(),
            ));
        };
        inner.phase = engine::Phase::Downloading;
        inner.bytes = None;

        let task_app = app.clone();
        let version = update.version.clone();
        let task = tauri::async_runtime::spawn(async move {
            let mut downloaded: u64 = 0;
            let mut last_emitted: u64 = 0;
            let result = update
                .download(
                    |chunk, total| {
                        downloaded += chunk as u64;
                        // Throttle IPC: every ~2 MB, plus the final chunk.
                        if downloaded - last_emitted >= 2 * 1024 * 1024
                            || total.is_some_and(|t| downloaded >= t)
                        {
                            last_emitted = downloaded;
                            let _ = task_app
                                .emit("updater://progress", ProgressPayload { downloaded, total });
                        }
                    },
                    || {},
                )
                .await;
            let engine = task_app.state::<UpdaterEngine>();
            let mut inner = engine.inner.lock().await;
            inner.task = None;
            match result {
                Ok(bytes) => {
                    inner.bytes = Some(bytes);
                    inner.phase = engine::Phase::Ready;
                    let _ = task_app.emit(
                        "updater://state",
                        StatePayload {
                            phase: "ready",
                            error: None,
                            version: Some(version),
                        },
                    );
                }
                Err(e) => {
                    inner.bytes = None;
                    inner.phase = engine::Phase::Idle;
                    let _ = task_app.emit(
                        "updater://state",
                        StatePayload {
                            phase: "error",
                            error: Some(classify(&e)),
                            version: Some(version),
                        },
                    );
                }
            }
        });
        inner.task = Some(task);
        Ok(())
    }
}

/// Abort an in-flight download. Nothing has touched the disk yet, so this is
/// always safe; the staged backup location is untouched too.
#[tauri::command]
pub async fn updater_cancel<R: Runtime>(app: AppHandle<R>) -> Result<(), UpdateError> {
    #[cfg(not(feature = "updater"))]
    {
        let _ = app;
        Ok(())
    }

    #[cfg(feature = "updater")]
    {
        use tauri::Emitter;

        let engine = app.state::<UpdaterEngine>();
        let mut inner = engine.inner.lock().await;
        if let Some(task) = inner.task.take() {
            task.abort();
        }
        inner.bytes = None;
        inner.phase = engine::Phase::Idle;
        let _ = app.emit(
            "updater://state",
            StatePayload {
                phase: "idle",
                error: None,
                version: None,
            },
        );
        Ok(())
    }
}

/// The explicit consent click. Order matters:
///   1. stop the sidecar (polite HTTP shutdown, then kill) — a live sidecar exe
///      makes the Windows installer fail with file-in-use;
///   2. snapshot the ledger + write the pending-update marker;
///   3. install. Windows: never returns — the installer exits us, swaps files,
///      relaunches. macOS: the .app is swapped in place, then we restart.
#[tauri::command]
pub async fn updater_install_and_restart<R: Runtime>(app: AppHandle<R>) -> Result<(), UpdateError> {
    #[cfg(not(feature = "updater"))]
    {
        let _ = app;
        Err(disabled_error())
    }

    #[cfg(feature = "updater")]
    {
        use tauri::Emitter;

        let engine = app.state::<UpdaterEngine>();
        let mut inner = engine.inner.lock().await;
        if inner.phase != engine::Phase::Ready {
            return Err(other_error("No downloaded update is staged.".into()));
        }
        let Some(update) = inner.update.clone() else {
            return Err(other_error("No update metadata staged.".into()));
        };
        let Some(bytes) = inner.bytes.take() else {
            return Err(other_error(
                "Downloaded bytes were lost — download again.".into(),
            ));
        };
        inner.phase = engine::Phase::Idle;
        drop(inner);

        let _ = app.emit(
            "updater://state",
            StatePayload {
                phase: "installing",
                error: None,
                version: Some(update.version.clone()),
            },
        );

        crate::stop_sidecar_for_install(&app);

        let from = app.package_info().version.to_string();
        let backup_taken = backup_user_state(&app).is_ok();
        write_json_file(
            &app,
            PENDING_FILE,
            &PendingUpdate {
                from,
                to: update.version.clone(),
                at_epoch: now_epoch(),
                backup_taken,
            },
        );

        if let Err(e) = update.install(bytes) {
            // No update landed: the marker must not survive to claim one did.
            clear_pending(&app);
            let error = UpdateError {
                kind: "install_failed",
                message: e.to_string(),
            };
            let _ = app.emit(
                "updater://state",
                StatePayload {
                    phase: "error",
                    error: Some(error.clone()),
                    version: Some(update.version.clone()),
                },
            );
            return Err(error);
        }

        // Windows never reaches this line. macOS/Linux: relaunch into the new
        // version; the next boot's health gate verifies it and retires the backup.
        app.restart();
    }
}

/// Recovery relaunch after a failed install: the sidecar was already stopped,
/// so restart the (still old, still working) app cleanly.
#[tauri::command]
pub fn updater_relaunch<R: Runtime>(app: AppHandle<R>) -> Result<(), UpdateError> {
    app.restart();
}
