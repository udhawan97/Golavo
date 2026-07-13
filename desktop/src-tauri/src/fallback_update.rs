//! GitHub-release fallback updater — the path that works in EVERY build.
//!
//! The signed updater (src/updater.rs) only runs in maintainer builds compiled
//! with `--features updater` (they hold the Ed25519 key). A source/dev build, or
//! anyone who declined the signed path, would otherwise dead-end on a "go to the
//! releases page" link. This module keeps the "download and update from Settings"
//! promise for those builds: it asks the public GitHub releases API for the
//! latest version, and — if newer — streams the correct platform installer to
//! disk and opens it. Trust is delegated to whatever the OS verifies when the
//! installer opens (Gatekeeper/notarization on macOS, SmartScreen/Authenticode
//! on Windows) *if the released installer is signed* — otherwise the anchor is
//! just TLS to github.com plus the user's own OS trust prompt. Either way Golavo
//! does NOT cryptographically verify the artifact itself here (that's the signed
//! updater's job), so this is a guided manual install, not an in-place swap. The
//! UI copy states this plainly.
//!
//! It is ALWAYS compiled (no feature gate) and is surfaced by the frontend only
//! when the signed updater is unavailable (`status.enabled === false`).
//!
//! Staged, one-at-a-time, and cancellable:
//!   fallback_check     GitHub API metadata only; picks this platform's asset
//!   fallback_download  streams the asset to app-data/updates/downloads,
//!                      emits `updater://fallback-progress`, returns the path
//!   fallback_cancel    flags an in-flight download to stop and clean up
//!   fallback_open      opens the downloaded installer with the OS handler

use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Duration;

use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Emitter, Manager, Runtime};

use crate::updater::{UpdateError, RELEASES_URL};

/// owner/repo for the releases API — kept in sync with `RELEASES_URL`.
const GITHUB_REPO: &str = "udhawan97/Golavo";
const USER_AGENT: &str = "Golavo-Updater";

/// Only assets under this exact prefix may be downloaded — the frontend can only
/// pass back a URL we ourselves returned from `fallback_check`, but validating it
/// here means a compromised/confused caller still can't turn this into an
/// arbitrary-URL fetcher.
const ASSET_URL_PREFIX: &str = "https://github.com/udhawan97/Golavo/releases/download/";

// ---------------------------------------------------------------------------
// Serializable surface shared with the frontend (camelCase)
// ---------------------------------------------------------------------------

#[derive(Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct FallbackRelease {
    /// Latest published version (tag with any leading `v` stripped).
    pub version: String,
    /// True when `version` is strictly newer than the running build.
    pub available: bool,
    pub notes: Option<String>,
    /// The installer asset for THIS platform, if the release published one.
    pub asset_name: Option<String>,
    pub asset_url: Option<String>,
    pub asset_size: Option<u64>,
    /// The human releases page — always offered as a manual last resort.
    pub releases_url: &'static str,
}

#[derive(Serialize, Clone)]
#[serde(rename_all = "camelCase")]
struct FallbackProgress {
    downloaded: u64,
    total: Option<u64>,
}

/// One download at a time; the flag is also the cancel channel.
#[derive(Default)]
pub struct FallbackEngine {
    downloading: AtomicBool,
    cancel: AtomicBool,
}

/// Resets the `downloading` slot AND clears the `cancel` flag on every exit path
/// of a download (including early `?` returns and panics), so a failed/stalled
/// download never wedges the engine and a leftover cancel can't abort the next.
struct DownloadGuard<'a>(&'a AtomicBool, &'a AtomicBool);
impl Drop for DownloadGuard<'_> {
    fn drop(&mut self) {
        self.0.store(false, Ordering::SeqCst); // downloading = false
        self.1.store(false, Ordering::SeqCst); // cancel = false
    }
}

// ---------------------------------------------------------------------------
// GitHub API shapes (only the fields we read)
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
struct GhRelease {
    tag_name: String,
    #[serde(default)]
    body: Option<String>,
    #[serde(default)]
    draft: bool,
    #[serde(default)]
    assets: Vec<GhAsset>,
}

#[derive(Deserialize)]
struct GhAsset {
    name: String,
    browser_download_url: String,
    #[serde(default)]
    size: u64,
}

// ---------------------------------------------------------------------------
// Error helpers
// ---------------------------------------------------------------------------

fn err(kind: &'static str, message: impl Into<String>) -> UpdateError {
    UpdateError {
        kind,
        message: message.into(),
    }
}

/// Map a transport-level reqwest failure to one of the frontend's error kinds.
fn classify_reqwest(e: &reqwest::Error) -> UpdateError {
    if e.is_timeout() || e.is_connect() {
        err(
            "unreachable",
            "Couldn’t reach GitHub — you may be offline or behind a firewall/proxy.",
        )
    } else if e.is_decode() {
        err(
            "bad_manifest",
            "GitHub returned an unexpected response — try again shortly.",
        )
    } else {
        err("other", e.to_string())
    }
}

/// Map a non-2xx HTTP status to a frontend error kind.
fn classify_status(status: u16) -> UpdateError {
    match status {
        403 | 429 => err(
            "rate_limited",
            "GitHub is rate-limiting update checks right now — try again in a little while.",
        ),
        404 => err(
            "bad_manifest",
            "No published release was found. Use the releases page to update manually.",
        ),
        _ => err("other", format!("GitHub responded with HTTP {status}.")),
    }
}

// ---------------------------------------------------------------------------
// Version + asset selection
// ---------------------------------------------------------------------------

fn strip_v(tag: &str) -> &str {
    tag.strip_prefix('v')
        .or_else(|| tag.strip_prefix('V'))
        .unwrap_or(tag)
}

/// True when `latest` is a strictly greater semver than `current`. If either
/// won't parse (shouldn't happen for our tags), fall back to a conservative
/// inequality so a real difference is still surfaced rather than silently hidden.
fn is_newer(latest: &str, current: &str) -> bool {
    use semver::Version;
    match (Version::parse(latest), Version::parse(current)) {
        (Ok(l), Ok(c)) => l > c,
        _ => latest != current,
    }
}

/// The installer asset a human should download on THIS OS *and* CPU arch. macOS
/// → the `.dmg` whose name carries the running arch (aarch64 / a universal
/// build); Windows → the NSIS `-setup.exe`, else the `.msi`. If nothing matches
/// the running arch we return None — better to send the user to the releases
/// page than to hand an Intel Mac an Apple-Silicon-only `.dmg` that won't launch.
/// Other OSes have no bundled installer, so the UI falls back to the releases link.
fn pick_asset(assets: &[GhAsset]) -> Option<&GhAsset> {
    let ends = |a: &&GhAsset, suffix: &str| a.name.to_lowercase().ends_with(suffix);
    let has = |a: &&GhAsset, token: &str| a.name.to_lowercase().contains(token);
    #[cfg(target_os = "macos")]
    {
        // Tauri names the dmg `Golavo_<v>_<arch>.dmg`; a universal build carries
        // "universal". Match the running arch first, then any universal build.
        let arch = std::env::consts::ARCH; // "aarch64" | "x86_64"
        assets
            .iter()
            .find(|a| ends(a, ".dmg") && (has(a, arch) || has(a, "universal")))
    }
    #[cfg(target_os = "windows")]
    {
        // Match the NSIS installer explicitly (`-setup.exe`), never just any
        // `.exe`, so a future portable/standalone exe asset can't be picked.
        assets
            .iter()
            .find(|a| ends(a, "-setup.exe"))
            .or_else(|| assets.iter().find(|a| ends(a, ".msi")))
    }
    #[cfg(not(any(target_os = "macos", target_os = "windows")))]
    {
        let _ = (assets, ends, has);
        None
    }
}

// ---------------------------------------------------------------------------
// Paths
// ---------------------------------------------------------------------------

fn downloads_dir<R: Runtime>(app: &AppHandle<R>) -> Result<PathBuf, UpdateError> {
    let dir = app
        .path()
        .app_local_data_dir()
        .map_err(|e| err("other", e.to_string()))?
        .join("updates")
        .join("downloads");
    std::fs::create_dir_all(&dir).map_err(|e| err("other", e.to_string()))?;
    Ok(dir)
}

/// Reduce an asset name to a safe basename — no separators, no traversal, no
/// hidden/empty names — so a download can only ever land inside `downloads_dir`.
fn safe_basename(name: &str) -> String {
    let base = Path::new(name)
        .file_name()
        .map(|s| s.to_string_lossy().to_string())
        .unwrap_or_default();
    let cleaned: String = base
        .chars()
        .filter(|c| c.is_ascii_alphanumeric() || matches!(c, '.' | '-' | '_'))
        .collect();
    let trimmed = cleaned.trim_matches('.');
    if trimmed.is_empty() {
        "golavo-update.bin".to_string()
    } else {
        trimmed.to_string()
    }
}

// ---------------------------------------------------------------------------
// GitHub fetch helpers
// ---------------------------------------------------------------------------

/// Build the shared HTTPS client. `connect_timeout` bounds the handshake and
/// `read_timeout` is a per-read IDLE timeout — a stalled body (flaky wifi,
/// captive proxy) errors out instead of parking a download forever. We do NOT
/// set an overall `.timeout`, which would kill legitimately slow large
/// downloads. `overall` is only used for the tiny metadata check.
fn http_client(overall: Option<Duration>) -> Result<reqwest::Client, UpdateError> {
    let mut builder = reqwest::Client::builder()
        .user_agent(USER_AGENT)
        .connect_timeout(Duration::from_secs(20))
        .read_timeout(Duration::from_secs(60));
    if let Some(t) = overall {
        builder = builder.timeout(t);
    }
    builder.build().map_err(|e| err("other", e.to_string()))
}

/// GET the latest published release from the GitHub API and parse it.
async fn fetch_latest_release(client: &reqwest::Client) -> Result<GhRelease, UpdateError> {
    let url = format!("https://api.github.com/repos/{GITHUB_REPO}/releases/latest");
    let resp = client
        .get(url)
        .header("Accept", "application/vnd.github+json")
        .send()
        .await
        .map_err(|e| classify_reqwest(&e))?;
    let status = resp.status();
    if !status.is_success() {
        return Err(classify_status(status.as_u16()));
    }
    let release: GhRelease = resp.json().await.map_err(|e| classify_reqwest(&e))?;
    if release.draft {
        // `releases/latest` never returns drafts, but be explicit rather than
        // offer an unpublished build.
        return Err(err(
            "bad_manifest",
            "The latest release is not published yet — try again shortly.",
        ));
    }
    Ok(release)
}

// ---------------------------------------------------------------------------
// Commands
// ---------------------------------------------------------------------------

/// Ask GitHub for the latest release and report whether it's newer than us.
/// Metadata only — nothing is written and nothing downloads.
#[tauri::command]
pub async fn fallback_check<R: Runtime>(app: AppHandle<R>) -> Result<FallbackRelease, UpdateError> {
    let client = http_client(Some(Duration::from_secs(20)))?;
    let release = fetch_latest_release(&client).await?;

    let latest = strip_v(&release.tag_name).to_string();
    let current = app.package_info().version.to_string();
    let available = is_newer(&latest, &current);

    let asset = pick_asset(&release.assets);
    Ok(FallbackRelease {
        version: latest,
        available,
        notes: release.body.filter(|b| !b.trim().is_empty()),
        asset_name: asset.map(|a| a.name.clone()),
        asset_url: asset.map(|a| a.browser_download_url.clone()),
        asset_size: asset.map(|a| a.size),
        releases_url: RELEASES_URL,
    })
}

/// Re-resolve THIS platform's installer from the current latest release and
/// stream it into the downloads dir, emitting `updater://fallback-progress`.
/// The download target is derived server-side (never taken from the caller), so
/// a compromised webview can't point this at an arbitrary asset. Resolves with
/// the saved path, or rejects — `kind:"cancelled"` if the user aborted.
#[tauri::command]
pub async fn fallback_download<R: Runtime>(app: AppHandle<R>) -> Result<String, UpdateError> {
    use std::io::Write;

    let engine = app.state::<FallbackEngine>();
    // Claim the single download slot; bail if one is already running.
    if engine
        .downloading
        .compare_exchange(false, true, Ordering::SeqCst, Ordering::SeqCst)
        .is_err()
    {
        return Err(err("busy", "A download is already in progress."));
    }
    // The guard resets `downloading` AND clears `cancel` on every exit path, so
    // a failed/stalled download never wedges the engine and a leftover cancel
    // flag can't abort the next download.
    let _guard = DownloadGuard(&engine.downloading, &engine.cancel);
    engine.cancel.store(false, Ordering::SeqCst);

    // Re-derive the target from a fresh check — do NOT trust a caller URL.
    let client = http_client(None)?;
    let release = fetch_latest_release(&client).await?;
    let asset = pick_asset(&release.assets).ok_or_else(|| {
        err(
            "bad_manifest",
            "That release has no installer for this platform. Use the releases page.",
        )
    })?;
    let url = asset.browser_download_url.clone();
    let name = asset.name.clone();
    // Belt-and-suspenders: the derived URL must still be a Golavo release asset.
    if !url.starts_with(ASSET_URL_PREFIX) {
        return Err(err(
            "other",
            "The release asset URL looked unexpected. Use the releases page instead.",
        ));
    }

    let dest = downloads_dir(&app)?.join(safe_basename(&name));

    let mut resp = client
        .get(&url)
        .send()
        .await
        .map_err(|e| classify_reqwest(&e))?;
    let status = resp.status();
    if !status.is_success() {
        return Err(classify_status(status.as_u16()));
    }

    let total = resp.content_length();
    // Write to a temp path, then rename into place, so a partial/cancelled
    // download can never masquerade as a complete installer on disk.
    let tmp = dest.with_extension("part");
    let mut file = std::fs::File::create(&tmp).map_err(|e| err("other", e.to_string()))?;
    let mut downloaded: u64 = 0;
    let mut last_emitted: u64 = 0;

    loop {
        if engine.cancel.load(Ordering::SeqCst) {
            drop(file);
            let _ = std::fs::remove_file(&tmp);
            return Err(err("cancelled", "Download cancelled."));
        }
        match resp.chunk().await {
            Ok(Some(chunk)) => {
                file.write_all(&chunk)
                    .map_err(|e| err("other", e.to_string()))?;
                downloaded += chunk.len() as u64;
                // Throttle IPC: every ~2 MB, plus whenever we reach the total.
                if downloaded - last_emitted >= 2 * 1024 * 1024
                    || total.is_some_and(|t| downloaded >= t)
                {
                    last_emitted = downloaded;
                    let _ = app.emit(
                        "updater://fallback-progress",
                        FallbackProgress { downloaded, total },
                    );
                }
            }
            Ok(None) => break,
            Err(e) => {
                drop(file);
                let _ = std::fs::remove_file(&tmp);
                return Err(classify_reqwest(&e));
            }
        }
    }

    file.flush().map_err(|e| err("other", e.to_string()))?;
    drop(file);

    // A late cancel (clicked as the last chunk landed) must still win — don't
    // present a file the user asked to abort.
    if engine.cancel.load(Ordering::SeqCst) {
        let _ = std::fs::remove_file(&tmp);
        return Err(err("cancelled", "Download cancelled."));
    }
    // Length integrity: if the server advertised a size, the stream must have
    // delivered exactly that. A short read (proxy closing on a chunk boundary)
    // would otherwise rename a TRUNCATED installer into place as if complete.
    if let Some(t) = total {
        if downloaded != t {
            let _ = std::fs::remove_file(&tmp);
            return Err(err(
                "bad_manifest",
                "The download ended early and looks incomplete — try again.",
            ));
        }
    }

    // Final rename; if a stale file sits at dest (a prior download of the same
    // name), replace it.
    if dest.exists() {
        let _ = std::fs::remove_file(&dest);
    }
    std::fs::rename(&tmp, &dest).map_err(|e| err("other", e.to_string()))?;

    // One last progress emit at 100% so a UI that missed the throttled final
    // chunk still lands on "done".
    let _ = app.emit(
        "updater://fallback-progress",
        FallbackProgress {
            downloaded,
            total: total.or(Some(downloaded)),
        },
    );

    Ok(dest.to_string_lossy().to_string())
}

/// Flag an in-flight download to stop. Safe to call when idle.
#[tauri::command]
pub fn fallback_cancel<R: Runtime>(app: AppHandle<R>) -> Result<(), UpdateError> {
    app.state::<FallbackEngine>()
        .cancel
        .store(true, Ordering::SeqCst);
    Ok(())
}

/// Open a downloaded installer with the OS handler. macOS mounts the DMG and
/// shows the drag-to-Applications window; Windows launches the installer. The
/// path MUST be one we wrote (inside the downloads dir) — never an arbitrary
/// caller-supplied path.
#[tauri::command]
pub fn fallback_open<R: Runtime>(app: AppHandle<R>, path: String) -> Result<(), UpdateError> {
    let dir = downloads_dir(&app)?;
    let requested = PathBuf::from(&path);
    // Canonicalize both sides so `..` or symlinks can't escape the dir. The file
    // must exist to open it anyway, so canonicalize failing is a real error.
    let canonical_dir = dir
        .canonicalize()
        .map_err(|e| err("other", e.to_string()))?;
    let canonical_file = requested.canonicalize().map_err(|_| {
        err(
            "other",
            "The downloaded file is missing — download it again.",
        )
    })?;
    if !canonical_file.starts_with(&canonical_dir) {
        return Err(err(
            "other",
            "Refusing to open a file outside the downloads folder.",
        ));
    }

    // Windows: the NSIS installer replaces Golavo's files in place. It kills the
    // main exe itself, but NOT the PyInstaller sidecar child — a still-running
    // sidecar keeps its exe file-locked and the install fails/orphans it. Stop
    // it first (same helper the signed path uses). macOS drags the .app aside
    // while the app runs, so no teardown is needed there.
    #[cfg(target_os = "windows")]
    crate::stop_sidecar_for_install(&app);

    open_with_os(&canonical_file)
}

/// Launch the platform's default handler for `file`, detached (we do not wait).
fn open_with_os(file: &Path) -> Result<(), UpdateError> {
    use std::process::Command;

    #[cfg(target_os = "macos")]
    let mut cmd = {
        let mut c = Command::new("open");
        c.arg(file);
        c
    };
    #[cfg(target_os = "windows")]
    let mut cmd = {
        // `cmd /C start "" <file>` launches the installer via the shell. The
        // empty "" is the (mandatory) window-title arg for `start`.
        let mut c = Command::new("cmd");
        c.args(["/C", "start", ""]).arg(file);
        c
    };
    #[cfg(not(any(target_os = "macos", target_os = "windows")))]
    let mut cmd = {
        let mut c = Command::new("xdg-open");
        c.arg(file);
        c
    };

    cmd.spawn()
        .map(|_| ())
        .map_err(|e| err("other", format!("Couldn’t open the installer: {e}")))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn asset(name: &str) -> GhAsset {
        GhAsset {
            name: name.into(),
            browser_download_url: format!("{ASSET_URL_PREFIX}v9.9.9/{name}"),
            size: 1,
        }
    }

    #[test]
    fn strip_v_handles_both_cases_and_bare_tags() {
        assert_eq!(strip_v("v0.5.2"), "0.5.2");
        assert_eq!(strip_v("V1.0.0"), "1.0.0");
        assert_eq!(strip_v("0.5.2"), "0.5.2");
    }

    #[test]
    fn is_newer_is_strict_semver() {
        assert!(is_newer("0.5.2", "0.5.1"));
        assert!(is_newer("1.0.0", "0.9.9"));
        assert!(!is_newer("0.5.1", "0.5.1")); // equal is not newer
        assert!(!is_newer("0.5.0", "0.5.1")); // older is not newer
                                              // Unparseable falls back to inequality (never panics, never hides).
        assert!(is_newer("weird", "0.5.1"));
        assert!(!is_newer("same", "same"));
    }

    #[test]
    fn safe_basename_blocks_traversal_and_separators() {
        assert_eq!(safe_basename("../../etc/passwd"), "passwd");
        assert_eq!(
            safe_basename("/abs/Golavo_1.0_aarch64.dmg"),
            "Golavo_1.0_aarch64.dmg"
        );
        assert_eq!(safe_basename("a/b/c.dmg"), "c.dmg");
        // Path separators / shell metacharacters are stripped, not just rejected.
        assert_eq!(safe_basename("na;me&.dmg"), "name.dmg");
        // Nothing usable left → a safe default, never an empty/hidden name.
        assert_eq!(safe_basename("..."), "golavo-update.bin");
        assert_eq!(safe_basename(""), "golavo-update.bin");
    }

    /// The exact asset set a real Golavo release publishes (verified live). The
    /// raw `golavo-sidecar*` binaries and every `.sig` must never be selected.
    fn real_release_assets() -> Vec<GhAsset> {
        [
            "golavo-sidecar",
            "golavo-sidecar.exe",
            "Golavo_0.5.2_aarch64.app.tar.gz",
            "Golavo_0.5.2_aarch64.app.tar.gz.sig",
            "Golavo_0.5.2_aarch64.dmg",
            "Golavo_0.5.2_x64-setup.exe",
            "Golavo_0.5.2_x64-setup.exe.sig",
            "Golavo_0.5.2_x64_en-US.msi",
            "Golavo_0.5.2_x64_en-US.msi.sig",
            "latest.json",
            "SHA256SUMS.txt",
        ]
        .iter()
        .map(|n| asset(n))
        .collect()
    }

    #[cfg(target_os = "macos")]
    #[test]
    fn pick_asset_macos_picks_the_arch_dmg_only() {
        let assets = real_release_assets();
        let chosen = pick_asset(&assets).expect("a dmg should match on aarch64");
        assert_eq!(chosen.name, "Golavo_0.5.2_aarch64.dmg");
    }

    #[cfg(target_os = "macos")]
    #[test]
    fn pick_asset_macos_returns_none_when_no_matching_arch_dmg() {
        // Only an x86_64 dmg present while running on aarch64 → no match, so the
        // UI sends the user to the releases page instead of a broken download.
        let assets = vec![asset("Golavo_0.5.2_x86_64.dmg"), asset("latest.json")];
        assert!(pick_asset(&assets).is_none());
    }

    #[cfg(target_os = "windows")]
    #[test]
    fn pick_asset_windows_picks_setup_exe_not_the_raw_sidecar() {
        let assets = real_release_assets();
        let chosen = pick_asset(&assets).expect("the NSIS setup should match");
        // Must be the installer, never the raw `golavo-sidecar.exe`.
        assert_eq!(chosen.name, "Golavo_0.5.2_x64-setup.exe");
    }
}
