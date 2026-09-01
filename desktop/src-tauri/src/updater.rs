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
//!                              ledger + correction stores, writes a pending-
//!                              update marker, installs, restarts.
//!                              On Windows install() never returns — the
//!                              installer exits us, updates, and relaunches.
//!
//! The backup has a full lifecycle, keyed by the pending-update marker:
//!   * healthy first boot after an install  -> backup retired, success recorded
//!     (feeds the UI's one-time "Updated to X" toast — honestly: no marker, no
//!     toast, so a manual reinstall never claims a backup that was never taken);
//!   * failed first boot after an install   -> mutable user state restored from the backup
//!     (staged copy + rename, never delete-then-copy), marker consumed;
//!   * failed boot with NO marker           -> NEVER restores. A transient
//!     sidecar failure months later must not overwrite newer user data.
//!
//! What is NOT gated behind the feature is the data-protection half: markers,
//! backups and restore are always compiled — a default build must still finish
//! or repair an update installed by a previous updater-enabled run.

use std::fs::{File, OpenOptions};
use std::io::{Read, Write};
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

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct PendingUpdate {
    pub from: String,
    pub to: String,
    pub at_epoch: u64,
    pub backup_taken: bool,
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
struct PendingBackupRetirement {
    from: String,
    to: String,
    at_epoch: u64,
    backup_taken: bool,
    retired_name: String,
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

/// Sibling local correction stores are user-authored state, never source packs.
pub fn corrections_dir<R: Runtime>(app: &AppHandle<R>) -> Result<PathBuf, String> {
    Ok(app
        .path()
        .app_local_data_dir()
        .map_err(|e| e.to_string())?
        .join("corrections"))
}

/// Foreground match-research history is user-reviewed state, not bundled data.
pub fn research_dir<R: Runtime>(app: &AppHandle<R>) -> Result<PathBuf, String> {
    Ok(app
        .path()
        .app_local_data_dir()
        .map_err(|e| e.to_string())?
        .join("research"))
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

fn unique_suffix() -> String {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_nanos())
        .unwrap_or(0);
    format!("{}-{nanos}", std::process::id())
}

#[cfg(unix)]
fn sync_directory(path: &Path) -> std::io::Result<()> {
    File::open(path)?.sync_all()
}

#[cfg(windows)]
fn sync_directory(_path: &Path) -> std::io::Result<()> {
    // Windows directory handles cannot be portably flushed through std. Every
    // trust-critical rename uses MOVEFILE_WRITE_THROUGH below instead.
    Ok(())
}

#[cfg(not(any(unix, windows)))]
fn sync_directory(_path: &Path) -> std::io::Result<()> {
    Ok(())
}

#[cfg(windows)]
fn durable_rename(from: &Path, to: &Path) -> std::io::Result<()> {
    use std::os::windows::ffi::OsStrExt;

    #[link(name = "Kernel32")]
    extern "system" {
        fn MoveFileExW(existing: *const u16, replacement: *const u16, flags: u32) -> i32;
    }
    const MOVEFILE_WRITE_THROUGH: u32 = 0x0000_0008;
    let existing = from
        .as_os_str()
        .encode_wide()
        .chain(Some(0))
        .collect::<Vec<_>>();
    let replacement = to
        .as_os_str()
        .encode_wide()
        .chain(Some(0))
        .collect::<Vec<_>>();
    // SAFETY: both pointers are valid, NUL-terminated UTF-16 buffers for the
    // duration of the call; the destination is deliberately required absent.
    let moved = unsafe {
        MoveFileExW(
            existing.as_ptr(),
            replacement.as_ptr(),
            MOVEFILE_WRITE_THROUGH,
        )
    };
    if moved == 0 {
        Err(std::io::Error::last_os_error())
    } else {
        Ok(())
    }
}

#[cfg(not(windows))]
fn durable_rename(from: &Path, to: &Path) -> std::io::Result<()> {
    std::fs::rename(from, to)
}

#[cfg(windows)]
fn durable_create(from: &Path, to: &Path) -> std::io::Result<()> {
    // MoveFileExW without MOVEFILE_REPLACE_EXISTING is an atomic no-clobber
    // create and WRITE_THROUGH asks Windows to flush the move before returning.
    durable_rename(from, to)
}

#[cfg(not(windows))]
fn durable_create(from: &Path, to: &Path) -> std::io::Result<()> {
    // POSIX rename replaces a destination that appears in the final existence-
    // check race. A same-directory hard link atomically fails if the pending
    // marker already exists; unlinking the temporary name leaves the exact
    // synced inode at the durable target name.
    std::fs::hard_link(from, to)?;
    std::fs::remove_file(from)
}

fn read_json_path<T: for<'de> Deserialize<'de>>(path: &Path) -> Result<T, String> {
    let text = std::fs::read_to_string(path).map_err(|error| error.to_string())?;
    serde_json::from_str(&text).map_err(|error| error.to_string())
}

fn write_json_atomic<T: Serialize>(
    dir: &Path,
    name: &str,
    value: &T,
    replace: bool,
) -> Result<(), String> {
    std::fs::create_dir_all(dir).map_err(|error| error.to_string())?;
    let target = dir.join(name);
    if !replace && target.exists() {
        return Err(format!("{} already exists", target.display()));
    }
    let temporary = dir.join(format!(".{name}.tmp-{}", unique_suffix()));
    let result = (|| -> Result<(), String> {
        let mut stream = OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&temporary)
            .map_err(|error| error.to_string())?;
        let bytes = serde_json::to_vec_pretty(value).map_err(|error| error.to_string())?;
        stream
            .write_all(&bytes)
            .map_err(|error| error.to_string())?;
        stream.write_all(b"\n").map_err(|error| error.to_string())?;
        stream.sync_all().map_err(|error| error.to_string())?;
        drop(stream);

        if !replace && target.exists() {
            return Err(format!("{} appeared while writing", target.display()));
        }
        #[cfg(windows)]
        if replace && target.exists() {
            // The trust-critical pending marker never takes this branch. Windows
            // rename cannot replace an existing file; just-updated is a toast
            // receipt and can safely be replaced after its new bytes are synced.
            std::fs::remove_file(&target).map_err(|error| error.to_string())?;
        }
        if replace {
            durable_rename(&temporary, &target).map_err(|error| error.to_string())?;
        } else {
            durable_create(&temporary, &target).map_err(|error| error.to_string())?;
        }
        OpenOptions::new()
            .read(true)
            .write(true)
            .open(&target)
            .and_then(|stream| stream.sync_all())
            .map_err(|error| error.to_string())?;
        sync_directory(dir).map_err(|error| error.to_string())?;
        Ok(())
    })();
    if result.is_err() {
        let _ = std::fs::remove_file(&temporary);
    }
    result
}

const PENDING_FILE: &str = "pending-update.json";
const RETIREMENT_FILE: &str = "pending-backup-retirement.json";
const JUST_UPDATED_FILE: &str = "just-updated.json";

pub fn read_pending<R: Runtime>(app: &AppHandle<R>) -> Option<PendingUpdate> {
    read_pending_checked(app).ok().flatten()
}

fn read_pending_checked<R: Runtime>(app: &AppHandle<R>) -> Result<Option<PendingUpdate>, String> {
    let path = updates_dir(app)?.join(PENDING_FILE);
    if !path.exists() {
        return Ok(None);
    }
    read_json_path(&path).map(Some)
}

#[cfg_attr(not(feature = "updater"), allow(dead_code))]
fn write_pending<R: Runtime>(app: &AppHandle<R>, pending: &PendingUpdate) -> Result<(), String> {
    let dir = updates_dir(app)?;
    write_json_atomic(&dir, PENDING_FILE, pending, false)?;
    let observed: PendingUpdate = read_json_path(&dir.join(PENDING_FILE))?;
    if observed != *pending {
        return Err("pending update marker failed its readback verification".into());
    }
    Ok(())
}

fn clear_update_file<R: Runtime>(app: &AppHandle<R>, name: &str) -> Result<(), String> {
    let dir = updates_dir(app)?;
    match std::fs::remove_file(dir.join(name)) {
        Ok(()) => sync_directory(&dir).map_err(|error| error.to_string()),
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(()),
        Err(error) => Err(error.to_string()),
    }
}

fn clear_pending<R: Runtime>(app: &AppHandle<R>) -> Result<(), String> {
    clear_update_file(app, PENDING_FILE)
}

fn read_retirement_checked<R: Runtime>(
    app: &AppHandle<R>,
) -> Result<Option<PendingBackupRetirement>, String> {
    let path = updates_dir(app)?.join(RETIREMENT_FILE);
    if !path.exists() {
        return Ok(None);
    }
    read_json_path(&path).map(Some)
}

fn write_retirement<R: Runtime>(
    app: &AppHandle<R>,
    retirement: &PendingBackupRetirement,
) -> Result<(), String> {
    let dir = updates_dir(app)?;
    write_json_atomic(&dir, RETIREMENT_FILE, retirement, false)?;
    let observed: PendingBackupRetirement = read_json_path(&dir.join(RETIREMENT_FILE))?;
    if observed != *retirement {
        return Err("backup retirement marker failed its readback verification".into());
    }
    Ok(())
}

fn clear_retirement<R: Runtime>(app: &AppHandle<R>) -> Result<(), String> {
    clear_update_file(app, RETIREMENT_FILE)
}

pub fn read_just_updated<R: Runtime>(app: &AppHandle<R>) -> Option<JustUpdated> {
    read_json_file(app, JUST_UPDATED_FILE)
}

// ---------------------------------------------------------------------------
// Backup lifecycle (always compiled)
// ---------------------------------------------------------------------------

/// Copy the ledger and isolated local correction stores into a fresh backup dir,
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
            if let Some(parent) = backup.parent() {
                let _ = sync_directory(parent);
            }
            Err(e)
        }
    }
}

fn backup_user_state_inner<R: Runtime>(app: &AppHandle<R>, backup: &Path) -> Result<(), String> {
    if backup.exists() {
        let parent = backup
            .parent()
            .ok_or_else(|| "backup directory has no parent".to_string())?;
        let preserved = parent.join(format!("preserved-unarmed-{}", unique_suffix()));
        durable_rename(backup, &preserved).map_err(|error| error.to_string())?;
        sync_directory(parent).map_err(|error| error.to_string())?;
    }
    std::fs::create_dir_all(backup).map_err(|e| e.to_string())?;
    let ledger = ledger_dir(app)?;
    if ledger.exists() {
        copy_dir(&ledger, &backup.join("ledger")).map_err(|e| e.to_string())?;
        verify_dir_copy(&ledger, &backup.join("ledger"), None)?;
    }
    let corrections = corrections_dir(app)?;
    if corrections.exists() {
        copy_dir(&corrections, &backup.join("corrections")).map_err(|e| e.to_string())?;
        verify_dir_copy(&corrections, &backup.join("corrections"), None)?;
    }
    let research = research_dir(app)?;
    if research.exists() {
        copy_dir(&research, &backup.join("research")).map_err(|e| e.to_string())?;
        let temporary = backup.join("research").join("tmp");
        if temporary.exists() {
            std::fs::remove_dir_all(&temporary).map_err(|error| error.to_string())?;
            sync_directory(&backup.join("research")).map_err(|error| error.to_string())?;
        }
        verify_dir_copy(&research, &backup.join("research"), Some("tmp"))?;
    }
    sync_directory(backup).map_err(|error| error.to_string())?;
    if let Some(parent) = backup.parent() {
        sync_directory(parent).map_err(|error| error.to_string())?;
    }
    Ok(())
}

fn restore_component_with_rename<F>(
    backup: &Path,
    live: &Path,
    name: &str,
    rename: &mut F,
) -> Result<bool, String>
where
    F: FnMut(&Path, &Path) -> std::io::Result<()>,
{
    if !backup.exists() {
        return Ok(false);
    }
    let parent = live
        .parent()
        .ok_or_else(|| format!("{name} dir has no parent"))?
        .to_path_buf();
    let staging = parent.join(format!("{name}.restoring-{}", unique_suffix()));
    copy_dir(backup, &staging).map_err(|e| e.to_string())?;
    verify_dir_copy(backup, &staging, None)?;
    let mut aside = None;
    if live.exists() {
        let displaced = parent.join(format!("{name}.pre-restore-{}", unique_suffix()));
        rename(live, &displaced).map_err(|error| error.to_string())?;
        if let Err(error) = sync_directory(&parent) {
            let compensation = rename(&displaced, live);
            return Err(format!(
                "could not durably move {name} aside: {error}; compensation: {compensation:?}"
            ));
        }
        aside = Some(displaced);
    }
    if let Err(error) = rename(&staging, live) {
        let compensation = aside.as_ref().map(|displaced| rename(displaced, live));
        return Err(format!(
            "could not activate restored {name}: {error}; compensation: {compensation:?}; staged copy: {}",
            staging.display()
        ));
    }
    sync_directory(&parent).map_err(|error| {
        format!(
            "restored {name} is canonical but its directory sync failed: {error}; recovery remains armed"
        )
    })?;
    Ok(true)
}

fn restore_component(backup: &Path, live: &Path, name: &str) -> Result<bool, String> {
    restore_component_with_rename(backup, live, name, &mut durable_rename)
}

fn verified_backup_root_exists(backup: &Path) -> Result<bool, String> {
    match std::fs::symlink_metadata(backup) {
        Ok(metadata) if metadata.file_type().is_dir() => Ok(true),
        Ok(_) => Err(format!(
            "verified pre-update backup root is not a directory: {}",
            backup.display()
        )),
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(false),
        Err(error) => Err(format!(
            "could not inspect pre-update backup root {}: {error}",
            backup.display()
        )),
    }
}

fn require_verified_backup_root(backup: &Path) -> Result<(), String> {
    if verified_backup_root_exists(backup)? {
        Ok(())
    } else {
        Err(format!(
            "the pending update records a verified backup, but its root is missing: {}; recovery remains armed",
            backup.display()
        ))
    }
}

/// Restore every backed-up user-state component with copy-then-rename swaps.
pub fn restore_backup<R: Runtime>(app: &AppHandle<R>) -> Result<bool, String> {
    let backup = backup_root(app)?;
    require_verified_backup_root(&backup)?;
    let ledger = restore_component(&backup.join("ledger"), &ledger_dir(app)?, "ledger")?;
    let corrections = restore_component(
        &backup.join("corrections"),
        &corrections_dir(app)?,
        "corrections",
    )?;
    let research = restore_component(&backup.join("research"), &research_dir(app)?, "research")?;
    Ok(ledger || corrections || research)
}

/// After the first healthy boot on a new version, the pre-update backup has done
/// its job: move it out of the armed location so it can never be restored over
/// newer data. Existing forensic generations are never overwritten.
fn retire_backup_path(armed: &Path, to_version: &str) -> Result<(), String> {
    if !verified_backup_root_exists(armed)? {
        return Ok(());
    }
    let parent = armed
        .parent()
        .ok_or_else(|| "backup directory has no parent".to_string())?;
    let label = safe_backup_label(to_version);
    let retired = parent.join(format!("retired-{label}-{}", unique_suffix()));
    retire_backup_to(armed, &retired)
}

fn safe_backup_label(value: &str) -> String {
    value
        .chars()
        .map(|value| {
            if value.is_ascii_alphanumeric() || matches!(value, '.' | '-' | '_') {
                value
            } else {
                '_'
            }
        })
        .collect()
}

fn retire_backup_to(armed: &Path, retired: &Path) -> Result<(), String> {
    require_verified_backup_root(armed)?;
    if verified_backup_root_exists(retired)? {
        return Err(format!(
            "refusing to overwrite forensic backup generation {}",
            retired.display()
        ));
    }
    let parent = armed
        .parent()
        .ok_or_else(|| "backup directory has no parent".to_string())?;
    if retired.parent() != Some(parent) {
        return Err("forensic backup generation is outside the backup directory".into());
    }
    durable_rename(armed, retired).map_err(|error| error.to_string())?;
    sync_directory(parent).map_err(|error| error.to_string())
}

fn recover_retired_backup_with<F>(
    armed: &Path,
    retired: &Path,
    rename: &mut F,
) -> Result<(), String>
where
    F: FnMut(&Path, &Path) -> std::io::Result<()>,
{
    let armed_exists = verified_backup_root_exists(armed)?;
    let retired_exists = verified_backup_root_exists(retired)?;
    match (armed_exists, retired_exists) {
        (true, false) => {
            let parent = armed
                .parent()
                .ok_or_else(|| "backup directory has no parent".to_string())?;
            sync_directory(parent).map_err(|error| error.to_string())
        }
        (false, true) => {
            rename(retired, armed).map_err(|error| {
                format!(
                    "could not re-arm retired backup {}; recovery receipt remains preserved: {error}",
                    retired.display()
                )
            })?;
            let parent = armed
                .parent()
                .ok_or_else(|| "backup directory has no parent".to_string())?;
            sync_directory(parent).map_err(|error| error.to_string())
        }
        (true, true) => Err(
            "both armed and retired recovery generations exist; refusing to overwrite either"
                .into(),
        ),
        (false, false) => Err(
            "the retirement receipt references no recoverable backup generation; recovery remains armed"
                .into(),
        ),
    }
}

fn recover_retired_backup(armed: &Path, retired: &Path) -> Result<(), String> {
    recover_retired_backup_with(armed, retired, &mut durable_rename)
}

fn retirement_target(
    armed: &Path,
    retirement: &PendingBackupRetirement,
) -> Result<PathBuf, String> {
    let name = Path::new(&retirement.retired_name);
    if !retirement.retired_name.starts_with("retired-")
        || name.components().count() != 1
        || name.file_name() != Some(name.as_os_str())
    {
        return Err("backup retirement receipt contains an unsafe generation name".into());
    }
    let parent = armed
        .parent()
        .ok_or_else(|| "backup directory has no parent".to_string())?;
    Ok(parent.join(name))
}

fn retirement_matches_pending(
    retirement: &PendingBackupRetirement,
    pending: &PendingUpdate,
) -> bool {
    retirement.from == pending.from
        && retirement.to == pending.to
        && retirement.at_epoch == pending.at_epoch
        && retirement.backup_taken == pending.backup_taken
}

fn retirement_for_pending(pending: &PendingUpdate) -> PendingBackupRetirement {
    PendingBackupRetirement {
        from: pending.from.clone(),
        to: pending.to.clone(),
        at_epoch: pending.at_epoch,
        backup_taken: pending.backup_taken,
        retired_name: format!(
            "retired-{}-{}",
            safe_backup_label(&pending.to),
            unique_suffix()
        ),
    }
}

/// Retire the backup under a durable receipt before consuming the pending
/// marker. If marker clearing fails, compensate by moving that exact generation
/// back to the armed name. A crash at either boundary is repaired from the same
/// receipt on the next launch without guessing among historical generations.
fn finalize_backup_retirement_with<C>(armed: &Path, retired: &Path, clear: C) -> Result<(), String>
where
    C: FnOnce() -> Result<(), String>,
{
    retire_backup_to(armed, retired).map_err(|error| {
        let compensation = recover_retired_backup(armed, retired);
        format!(
            "could not durably retire the armed backup: {error}; compensation: {compensation:?}"
        )
    })?;
    if let Err(error) = clear() {
        let compensation = recover_retired_backup(armed, retired);
        return Err(format!(
            "could not clear the pending update marker: {error}; compensation: {compensation:?}"
        ));
    }
    Ok(())
}

fn copy_dir(from: &Path, to: &Path) -> std::io::Result<()> {
    if from.is_symlink() {
        return Err(std::io::Error::other(
            "refusing to copy a symbolic-link store",
        ));
    }
    std::fs::create_dir_all(to)?;
    for entry in std::fs::read_dir(from)? {
        let entry = entry?;
        let target = to.join(entry.file_name());
        let file_type = entry.file_type()?;
        if file_type.is_symlink() {
            return Err(std::io::Error::other(
                "refusing to copy a symbolic-link entry",
            ));
        }
        if file_type.is_dir() {
            copy_dir(&entry.path(), &target)?;
        } else if file_type.is_file() {
            std::fs::copy(entry.path(), &target)?;
            OpenOptions::new()
                .read(true)
                .write(true)
                .open(&target)?
                .sync_all()?;
        } else {
            return Err(std::io::Error::other("unsupported user-state entry"));
        }
    }
    sync_directory(to)
}

fn files_equal(left: &Path, right: &Path) -> Result<bool, String> {
    if left.metadata().map_err(|error| error.to_string())?.len()
        != right.metadata().map_err(|error| error.to_string())?.len()
    {
        return Ok(false);
    }
    let mut left_stream = File::open(left).map_err(|error| error.to_string())?;
    let mut right_stream = File::open(right).map_err(|error| error.to_string())?;
    let mut left_buffer = [0_u8; 64 * 1024];
    let mut right_buffer = [0_u8; 64 * 1024];
    loop {
        let left_read = left_stream
            .read(&mut left_buffer)
            .map_err(|error| error.to_string())?;
        let right_read = right_stream
            .read(&mut right_buffer)
            .map_err(|error| error.to_string())?;
        if left_read != right_read || left_buffer[..left_read] != right_buffer[..right_read] {
            return Ok(false);
        }
        if left_read == 0 {
            return Ok(true);
        }
    }
}

fn verify_dir_copy(from: &Path, to: &Path, ignore_top_level: Option<&str>) -> Result<(), String> {
    let mut source_entries = Vec::new();
    for entry in std::fs::read_dir(from).map_err(|error| error.to_string())? {
        let entry = entry.map_err(|error| error.to_string())?;
        if ignore_top_level.is_some_and(|ignored| entry.file_name() == ignored) {
            continue;
        }
        source_entries.push(entry.file_name());
    }
    let mut target_entries = std::fs::read_dir(to)
        .map_err(|error| error.to_string())?
        .map(|entry| {
            entry
                .map(|value| value.file_name())
                .map_err(|error| error.to_string())
        })
        .collect::<Result<Vec<_>, _>>()?;
    source_entries.sort();
    target_entries.sort();
    if source_entries != target_entries {
        return Err(format!(
            "backup directory listing differs for {}",
            from.display()
        ));
    }
    for name in source_entries {
        let source = from.join(&name);
        let target = to.join(&name);
        let source_type = source
            .symlink_metadata()
            .map_err(|error| error.to_string())?
            .file_type();
        let target_type = target
            .symlink_metadata()
            .map_err(|error| error.to_string())?
            .file_type();
        if source_type.is_symlink() || target_type.is_symlink() {
            return Err("backup verification refuses symbolic links".into());
        }
        if source_type.is_dir() && target_type.is_dir() {
            verify_dir_copy(&source, &target, None)?;
        } else if source_type.is_file() && target_type.is_file() {
            if !files_equal(&source, &target)? {
                return Err(format!("backup bytes differ for {}", source.display()));
            }
        } else {
            return Err(format!(
                "backup entry type differs for {}",
                source.display()
            ));
        }
    }
    Ok(())
}

/// Complete a restore that was interrupted mid-swap, BEFORE the launch path
/// fabricates an empty ledger over the gap.
///
/// `restore_backup` stages as: copy backup -> `ledger.restoring-*`, move live ->
/// `ledger.pre-restore-<epoch>`, rename `ledger.restoring` -> `ledger`. A crash
/// between the last two renames leaves NO canonical `ledger` while a full staged
/// copy sits at `ledger.restoring-*`. Left alone, `create_dir_all(ledger)` at
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
fn newest_recovery_candidate(parent: &Path, prefix: &str) -> Result<Option<PathBuf>, String> {
    let mut candidates = std::fs::read_dir(parent)
        .map_err(|error| error.to_string())?
        .filter_map(|entry| entry.ok())
        .filter(|entry| entry.file_name().to_string_lossy().starts_with(prefix))
        .map(|entry| entry.path())
        .collect::<Vec<_>>();
    candidates.sort();
    Ok(candidates.pop())
}

fn recover_component(
    live: PathBuf,
    backup: PathBuf,
    name: &str,
    has_pending: bool,
) -> Result<bool, String> {
    if live.exists() {
        return Ok(false);
    }
    if !has_pending {
        return Ok(false);
    }
    let parent = live
        .parent()
        .ok_or_else(|| format!("{name} directory has no parent"))?;
    let candidate = if backup.exists() {
        // A crash can leave a partially copied `restoring-*` directory. Always
        // rebuild and byte-verify from the durable backup instead of trusting an
        // orphaned staging name merely because it exists.
        let staging = parent.join(format!("{name}.restoring-{}", unique_suffix()));
        copy_dir(&backup, &staging).map_err(|error| error.to_string())?;
        verify_dir_copy(&backup, &staging, None)?;
        Some(staging)
    } else {
        // A pre-restore entry was once the canonical live directory and moved
        // atomically. It is safe recovery evidence even if the backup vanished.
        newest_recovery_candidate(parent, &format!("{name}.pre-restore-"))?
    };
    let Some(candidate) = candidate else {
        if newest_recovery_candidate(parent, &format!("{name}.restoring-"))?.is_some() {
            return Err(format!(
                "refusing to activate an unverifiable partial {name} staging copy; recovery evidence remains preserved"
            ));
        }
        return Ok(false);
    };
    durable_rename(&candidate, &live).map_err(|error| {
        format!(
            "could not recover {name}; preserved recoverable copy at {}: {error}",
            candidate.display()
        )
    })?;
    sync_directory(parent).map_err(|error| error.to_string())?;
    eprintln!("[golavo] completed an interrupted {name} restore");
    Ok(true)
}

fn reconcile_backup_retirement<R: Runtime>(
    app: &AppHandle<R>,
    pending: Option<&PendingUpdate>,
) -> Result<(), String> {
    let Some(retirement) = read_retirement_checked(app)? else {
        return Ok(());
    };
    if let Some(pending) = pending {
        if !retirement_matches_pending(&retirement, pending) {
            return Err(
                "backup retirement receipt does not match the pending update; recovery evidence remains preserved"
                    .into(),
            );
        }
    }
    let armed = backup_root(app)?;
    let retired = retirement_target(&armed, &retirement)?;
    if pending.is_some() {
        recover_retired_backup(&armed, &retired)?;
    } else {
        let armed_exists = verified_backup_root_exists(&armed)?;
        let retired_exists = verified_backup_root_exists(&retired)?;
        match (armed_exists, retired_exists) {
            (false, true) => {}
            (true, false) => retire_backup_to(&armed, &retired)?,
            (true, true) => {
                return Err(
                    "both armed and retired recovery generations exist; refusing to overwrite either"
                        .into(),
                );
            }
            (false, false) => {
                return Err("backup retirement receipt references no preserved generation".into());
            }
        }
    }
    clear_retirement(app)
}

pub fn recover_interrupted_restore<R: Runtime>(app: &AppHandle<R>) -> Result<(), String> {
    let pending = read_pending_checked(app)?;
    reconcile_backup_retirement(app, pending.as_ref())?;
    let backup = backup_root(app)?;
    let Some(pending) = pending else {
        // The marker was durably cleared but the process may have exited before
        // post-commit retirement. Preserve the bytes under a unique forensic
        // generation so a future backup can never replace them.
        if let Err(error) = retire_backup_path(&backup, "unarmed") {
            eprintln!("[golavo] deferred retirement of an unarmed pre-update backup: {error}");
        }
        return Ok(());
    };
    if pending.backup_taken {
        require_verified_backup_root(&backup)?;
    }
    let has_pending = true;
    recover_component(
        ledger_dir(app)?,
        backup.join("ledger"),
        "ledger",
        has_pending,
    )?;
    recover_component(
        corrections_dir(app)?,
        backup.join("corrections"),
        "corrections",
        has_pending,
    )?;
    recover_component(
        research_dir(app)?,
        backup.join("research"),
        "research",
        has_pending,
    )?;
    Ok(())
}

// ---------------------------------------------------------------------------
// Launch-time hooks (called from lib.rs; always compiled)
// ---------------------------------------------------------------------------

/// Healthy boot: if the previous run installed an update, the new version just
/// proved it can serve — retire the backup and record the success.
pub fn pending_version_matches<R: Runtime>(app: &AppHandle<R>) -> Result<(), String> {
    let Some(pending) = read_pending_checked(app)? else {
        return Ok(());
    };
    let running = app.package_info().version.to_string();
    if pending.to != running {
        return Err(format!(
            "the pending update expected version {} but version {} is running; recovery remains armed",
            pending.to, running
        ));
    }
    Ok(())
}

/// Retire recovery only after liveness, protected-state readiness, and exact
/// running-version checks have all passed in the desktop supervisor.
pub fn finalize_update_if_pending<R: Runtime>(app: &AppHandle<R>) -> Result<bool, String> {
    let Some(pending) = read_pending_checked(app)? else {
        return Ok(false);
    };
    pending_version_matches(app)?;
    reconcile_backup_retirement(app, Some(&pending))?;
    let updates = updates_dir(app)?;
    write_json_atomic(
        &updates,
        JUST_UPDATED_FILE,
        &JustUpdated {
            from: pending.from.clone(),
            to: pending.to.clone(),
            at_epoch: now_epoch(),
            backup_taken: pending.backup_taken,
        },
        true,
    )?;
    if pending.backup_taken {
        let backup = backup_root(app)?;
        require_verified_backup_root(&backup)?;
        let retirement = retirement_for_pending(&pending);
        write_retirement(app, &retirement)?;
        let retired = retirement_target(&backup, &retirement)?;
        if let Err(error) =
            finalize_backup_retirement_with(&backup, &retired, || clear_pending(app))
        {
            let recovery = recover_retired_backup(&backup, &retired);
            let cleanup = recovery.as_ref().ok().map(|_| clear_retirement(app));
            return Err(format!(
                "{error}; final recovery: {recovery:?}; receipt cleanup: {cleanup:?}"
            ));
        }
        if let Err(error) = clear_retirement(app) {
            eprintln!(
                "[golavo] backup retired and recovery marker cleared; transition receipt cleanup deferred: {error}"
            );
        }
    } else {
        clear_pending(app)?;
    }
    eprintln!(
        "[golavo] update {} -> {} verified ready; backup retired",
        pending.from, pending.to
    );
    Ok(true)
}

/// Failed health gate: build the message for the native error dialog, restoring
/// the pre-update backup ONLY when this boot is the first one after an install
/// (marker present). The marker is consumed only after a complete restore; any
/// failed half-swap keeps both the marker and every recovery copy armed.
pub fn repair_failed_launch<R: Runtime>(app: &AppHandle<R>, health_err: &str) -> String {
    match read_pending_checked(app) {
        Err(error) => format!(
            "Golavo could not verify its pending update recovery marker. Your data and recovery \
             files were left untouched.\n\nPlease download a fresh copy from:\n{}\n\n(Details: {}; {})",
            RELEASES_URL, health_err, error
        ),
        Ok(None) => format!(
            "Golavo's local engine failed to start.\n\nYour data is untouched. Try launching \
             Golavo again; if this keeps happening, download a fresh copy from:\n{}\n\n\
             (Details: {})",
            RELEASES_URL, health_err
        ),
        Ok(Some(pending)) => {
            // Only a VERIFIED backup may overwrite the live ledger. When the
            // pre-install backup didn't complete (backup_taken == false) it is not
            // trustworthy — and the install never touches the live ledger anyway —
            // so restoring a half-copy would trade good data for bad. Leave it.
            let (data_note, restored) = if pending.backup_taken {
                match reconcile_backup_retirement(app, Some(&pending))
                    .and_then(|()| restore_backup(app))
                {
                    Ok(true) => (
                        "Your local user data was restored from the pre-update backup.",
                        true,
                    ),
                    Ok(false) => ("The protected stores were empty before the update.", true),
                    Err(_) => (
                        "The verified pre-update backup is missing or could not be restored \
                         automatically; the recovery marker and any remaining staging/aside \
                         copies remain preserved for the next recovery attempt.",
                        false,
                    ),
                }
            } else {
                ("No verified pre-update backup is available; recovery remains armed.", false)
            };
            let marker_note = if restored {
                match clear_pending(app) {
                    Ok(()) => "",
                    Err(_) => " The recovery marker could not be cleared and remains armed.",
                }
            } else {
                " The recovery marker remains armed."
            };
            format!(
                "Golavo {} could not start after the update.\n\n{}{}\n\nPlease download the \
                 previous version from:\n{}\n\n(Details: {})",
                pending.to, data_note, marker_note, RELEASES_URL, health_err
            )
        }
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
        match read_pending_checked(&app) {
            Ok(None) => {}
            Ok(Some(_)) => {
                return Err(other_error(
                    "A previous update still has recovery armed; refusing to replace its evidence."
                        .into(),
                ));
            }
            Err(error) => {
                return Err(other_error(format!(
                    "The existing update recovery marker is unreadable; refusing to install: {error}"
                )));
            }
        }
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
        let protection = (|| -> Result<(), UpdateError> {
            backup_user_state(&app).map_err(|error| {
                other_error(format!(
                    "The update was not installed because protected user data could not be backed up and verified: {error}"
                ))
            })?;
            let pending = PendingUpdate {
                from,
                to: update.version.clone(),
                at_epoch: now_epoch(),
                backup_taken: true,
            };
            write_pending(&app, &pending).map_err(|error| {
                other_error(format!(
                    "The update was not installed because its durable recovery marker could not be verified: {error}"
                ))
            })
        })();
        if let Err(error) = protection {
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

        if let Err(e) = update.install(bytes) {
            // The updater API can report an error after touching application
            // files. Keep the verified backup and marker armed until a running
            // version plus protected-store readiness prove what actually landed.
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

#[cfg(test)]
mod tests {
    use std::cell::Cell;
    use std::path::{Path, PathBuf};

    use super::{
        finalize_backup_retirement_with, read_json_path, recover_component, recover_retired_backup,
        recover_retired_backup_with, require_verified_backup_root, restore_component_with_rename,
        retire_backup_to, unique_suffix, write_json_atomic, PendingUpdate,
    };

    fn test_root(label: &str) -> PathBuf {
        let root = std::env::temp_dir().join(format!("golavo-updater-{label}-{}", unique_suffix()));
        std::fs::create_dir_all(&root).unwrap();
        root
    }

    fn write_state(root: &Path, value: &str) {
        std::fs::create_dir_all(root).unwrap();
        std::fs::write(root.join("state.txt"), value).unwrap();
    }

    #[test]
    fn pending_marker_is_durable_readable_and_never_overwritten() {
        let root = test_root("pending");
        let pending = PendingUpdate {
            from: "0.19.0".into(),
            to: "0.20.0".into(),
            at_epoch: 42,
            backup_taken: true,
        };

        write_json_atomic(&root, "pending-update.json", &pending, false).unwrap();
        let first_bytes = std::fs::read(root.join("pending-update.json")).unwrap();
        assert_eq!(
            read_json_path::<PendingUpdate>(&root.join("pending-update.json")).unwrap(),
            pending
        );
        assert!(write_json_atomic(&root, "pending-update.json", &pending, false).is_err());
        assert_eq!(
            std::fs::read(root.join("pending-update.json")).unwrap(),
            first_bytes
        );
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn marker_failure_is_deterministic_and_leaves_no_marker() {
        let root = test_root("marker-failure");
        let blocker = root.join("not-a-directory");
        std::fs::write(&blocker, "block").unwrap();
        let pending = PendingUpdate {
            from: "0.19.0".into(),
            to: "0.20.0".into(),
            at_epoch: 42,
            backup_taken: true,
        };

        assert!(write_json_atomic(&blocker, "pending-update.json", &pending, false).is_err());
        assert!(!blocker.join("pending-update.json").exists());
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn retirement_clear_failure_keeps_marker_and_backup_armed() {
        let root = test_root("retirement-clear-fails");
        let marker = root.join("pending-update.json");
        let backup = root.join("pre-update");
        let retired = root.join("retired-0.20.0-injected");
        std::fs::write(&marker, "pending").unwrap();
        write_state(&backup, "backup");

        let result = finalize_backup_retirement_with(&backup, &retired, || {
            Err("injected clear failure".into())
        });

        assert!(result.is_err());
        assert_eq!(std::fs::read_to_string(&marker).unwrap(), "pending");
        assert_eq!(
            std::fs::read_to_string(backup.join("state.txt")).unwrap(),
            "backup"
        );
        assert!(!retired.exists());
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn crash_after_retirement_is_rearmed_from_the_exact_generation() {
        let root = test_root("retirement-crash-boundary");
        let marker = root.join("pending-update.json");
        let backup = root.join("pre-update");
        let retired = root.join("retired-0.20.0-recorded");
        std::fs::write(&marker, "pending").unwrap();
        write_state(&backup, "backup");

        retire_backup_to(&backup, &retired).unwrap();
        assert!(marker.exists());
        assert!(!backup.exists());
        assert_eq!(
            std::fs::read_to_string(retired.join("state.txt")).unwrap(),
            "backup"
        );

        recover_retired_backup(&backup, &retired).unwrap();
        assert!(marker.exists());
        assert!(!retired.exists());
        assert_eq!(
            std::fs::read_to_string(backup.join("state.txt")).unwrap(),
            "backup"
        );
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn failed_rearm_preserves_retired_generation_and_marker() {
        let root = test_root("retirement-rearm-fails");
        let marker = root.join("pending-update.json");
        let backup = root.join("pre-update");
        let retired = root.join("retired-0.20.0-recorded");
        std::fs::write(&marker, "pending").unwrap();
        write_state(&retired, "backup");
        let mut rename =
            |_from: &Path, _to: &Path| Err(std::io::Error::other("injected re-arm failure"));

        assert!(recover_retired_backup_with(&backup, &retired, &mut rename).is_err());
        assert!(marker.exists());
        assert!(!backup.exists());
        assert_eq!(
            std::fs::read_to_string(retired.join("state.txt")).unwrap(),
            "backup"
        );
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn verified_empty_backup_is_distinct_from_a_missing_backup() {
        let root = test_root("verified-empty-backup");
        let empty = root.join("pre-update");
        std::fs::create_dir(&empty).unwrap();

        assert!(require_verified_backup_root(&empty).is_ok());
        assert!(require_verified_backup_root(&root.join("missing")).is_err());
        assert!(empty.read_dir().unwrap().next().is_none());
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn failed_activation_compensates_back_to_the_original_canonical_store() {
        let root = test_root("restore-compensates");
        let backup = root.join("backup");
        let live = root.join("ledger");
        write_state(&backup, "backup");
        write_state(&live, "original");
        let calls = Cell::new(0_u8);
        let mut rename = |from: &Path, to: &Path| {
            calls.set(calls.get() + 1);
            if calls.get() == 2 {
                return Err(std::io::Error::other("injected activation failure"));
            }
            std::fs::rename(from, to)
        };

        assert!(restore_component_with_rename(&backup, &live, "ledger", &mut rename).is_err());
        assert_eq!(
            std::fs::read_to_string(live.join("state.txt")).unwrap(),
            "original"
        );
        assert!(root.read_dir().unwrap().flatten().any(|entry| entry
            .file_name()
            .to_string_lossy()
            .starts_with("ledger.restoring-")));
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn failed_displacement_leaves_original_canonical_and_staging_recoverable() {
        let root = test_root("restore-displacement-fails");
        let backup = root.join("backup");
        let live = root.join("ledger");
        write_state(&backup, "backup");
        write_state(&live, "original");
        let mut rename =
            |_from: &Path, _to: &Path| Err(std::io::Error::other("injected displacement failure"));

        assert!(restore_component_with_rename(&backup, &live, "ledger", &mut rename).is_err());
        assert_eq!(
            std::fs::read_to_string(live.join("state.txt")).unwrap(),
            "original"
        );
        assert!(root.read_dir().unwrap().flatten().any(|entry| entry
            .file_name()
            .to_string_lossy()
            .starts_with("ledger.restoring-")));
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn double_rename_failure_keeps_two_recovery_copies_then_recovers() {
        let root = test_root("restore-recoverable");
        let backup = root.join("backup");
        let live = root.join("ledger");
        write_state(&backup, "backup");
        write_state(&live, "original");
        let calls = Cell::new(0_u8);
        let mut rename = |from: &Path, to: &Path| {
            calls.set(calls.get() + 1);
            if calls.get() == 2 || calls.get() == 3 {
                return Err(std::io::Error::other("injected rename failure"));
            }
            std::fs::rename(from, to)
        };

        assert!(restore_component_with_rename(&backup, &live, "ledger", &mut rename).is_err());
        assert!(!live.exists());
        let names = root
            .read_dir()
            .unwrap()
            .flatten()
            .map(|entry| entry.file_name().to_string_lossy().to_string())
            .collect::<Vec<_>>();
        assert!(names
            .iter()
            .any(|name| name.starts_with("ledger.restoring-")));
        assert!(names
            .iter()
            .any(|name| name.starts_with("ledger.pre-restore-")));

        assert!(recover_component(live.clone(), backup.clone(), "ledger", true).unwrap());
        assert_eq!(
            std::fs::read_to_string(live.join("state.txt")).unwrap(),
            "backup"
        );
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn interrupted_restore_uses_verified_backup_before_empty_creation() {
        let root = test_root("recover-from-backup");
        let backup = root.join("backup");
        let live = root.join("ledger");
        write_state(&backup, "backup");

        assert!(recover_component(live.clone(), backup, "ledger", true).unwrap());
        assert_eq!(
            std::fs::read_to_string(live.join("state.txt")).unwrap(),
            "backup"
        );
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn interrupted_restore_ignores_partial_staging_when_backup_is_available() {
        let root = test_root("recover-ignores-partial");
        let backup = root.join("backup");
        let live = root.join("ledger");
        let partial = root.join("ledger.restoring-partial");
        write_state(&backup, "verified");
        write_state(&partial, "partial");

        assert!(recover_component(live.clone(), backup, "ledger", true).unwrap());
        assert_eq!(
            std::fs::read_to_string(live.join("state.txt")).unwrap(),
            "verified"
        );
        assert_eq!(
            std::fs::read_to_string(partial.join("state.txt")).unwrap(),
            "partial"
        );
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn interrupted_restore_never_activates_unverifiable_staging() {
        let root = test_root("recover-refuses-unverified");
        let live = root.join("ledger");
        let partial = root.join("ledger.restoring-partial");
        write_state(&partial, "partial");

        assert!(recover_component(live.clone(), root.join("missing"), "ledger", true).is_err());
        assert!(!live.exists());
        assert_eq!(
            std::fs::read_to_string(partial.join("state.txt")).unwrap(),
            "partial"
        );
        std::fs::remove_dir_all(root).unwrap();
    }
}
