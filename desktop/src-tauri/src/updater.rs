//! Signed auto-update — wired, but gated.
//!
//! A signed update requires the Tauri updater key pair. The public key is
//! embedded in the app at build time; the private key signs release artifacts in
//! CI. We hold neither in a default build, so the whole path is gated behind the
//! `updater` Cargo feature:
//!
//!   * default build (local + CI):   the plugin is NOT registered; `check_for_update`
//!                                    returns `disabled` honestly.
//!   * `--features updater` build:    the plugin is registered against the
//!                                    endpoints in tauri.conf.json and the flow
//!                                    below (backup → check → install → rollback)
//!                                    runs for real.
//!
//! What is NOT gated is protecting the user's data: `backup_user_state` /
//! `restore_backup` are always compiled and are what makes an update reversible.
//! Reverting the *executable* itself still requires reinstalling the prior
//! version — see docs/updates-rollback.md.

use std::path::{Path, PathBuf};

use serde::Serialize;
use tauri::{AppHandle, Manager, Runtime};

#[derive(Serialize, Clone)]
pub struct UpdateStatus {
    /// One of: "disabled", "up-to-date", "updated", "error".
    pub status: String,
    pub detail: String,
    /// Where the pre-update backup of user state was written, when one was made.
    pub backup_path: Option<String>,
}

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

/// Copy the ledger (the only mutable user state today) into a fresh backup dir,
/// returning that dir. Called before any update is installed (updater feature).
#[cfg_attr(not(feature = "updater"), allow(dead_code))]
pub fn backup_user_state<R: Runtime>(app: &AppHandle<R>) -> Result<PathBuf, String> {
    let backup = backup_root(app)?;
    if backup.exists() {
        std::fs::remove_dir_all(&backup).map_err(|e| e.to_string())?;
    }
    std::fs::create_dir_all(&backup).map_err(|e| e.to_string())?;
    let ledger = ledger_dir(app)?;
    if ledger.exists() {
        copy_dir(&ledger, &backup.join("ledger")).map_err(|e| e.to_string())?;
    }
    Ok(backup)
}

/// Restore a previously captured backup over the live ledger. Used when a freshly
/// installed update fails its post-update health check.
pub fn restore_backup<R: Runtime>(app: &AppHandle<R>) -> Result<bool, String> {
    let backup_ledger = backup_root(app)?.join("ledger");
    if !backup_ledger.exists() {
        return Ok(false);
    }
    let ledger = ledger_dir(app)?;
    if ledger.exists() {
        std::fs::remove_dir_all(&ledger).map_err(|e| e.to_string())?;
    }
    copy_dir(&backup_ledger, &ledger).map_err(|e| e.to_string())?;
    Ok(true)
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

/// Frontend-invokable: check for and, if configured, install an update — backing
/// up user state first and rolling that state back on failure.
#[tauri::command]
pub async fn check_for_update<R: Runtime>(app: AppHandle<R>) -> Result<UpdateStatus, String> {
    #[cfg(not(feature = "updater"))]
    {
        let _ = &app;
        Ok(UpdateStatus {
            status: "disabled".into(),
            detail: "This build has no updater signing key configured. Signed auto-update is \
                     gated on the TAURI_SIGNING_PRIVATE_KEY / public-key secrets and a build with \
                     --features updater. See docs/updates-rollback.md."
                .into(),
            backup_path: None,
        })
    }

    #[cfg(feature = "updater")]
    {
        use tauri_plugin_updater::UpdaterExt;

        let backup = backup_user_state(&app)?;
        let backup_str = backup.display().to_string();

        let updater = app.updater().map_err(|e| e.to_string())?;
        match updater.check().await {
            Ok(Some(update)) => {
                match update.download_and_install(|_, _| {}, || {}).await {
                    Ok(()) => Ok(UpdateStatus {
                        status: "updated".into(),
                        detail: format!(
                            "Update {} installed. Restart to apply; if the new build fails its \
                             health check on launch, your data will be restored from the backup.",
                            update.version
                        ),
                        backup_path: Some(backup_str),
                    }),
                    Err(e) => {
                        // Install failed — the current binary is untouched, but roll the
                        // user's data back to the captured snapshot to be safe.
                        let _ = restore_backup(&app);
                        Ok(UpdateStatus {
                            status: "error".into(),
                            detail: format!("Update failed and user data was restored: {e}"),
                            backup_path: Some(backup_str),
                        })
                    }
                }
            }
            Ok(None) => Ok(UpdateStatus {
                status: "up-to-date".into(),
                detail: "No update available.".into(),
                backup_path: Some(backup_str),
            }),
            Err(e) => Ok(UpdateStatus {
                status: "error".into(),
                detail: format!("Update check failed: {e}"),
                backup_path: Some(backup_str),
            }),
        }
    }
}

/// Called from the launch health-gate failure path: if the previous run installed
/// an update (a backup exists), restore the user's data so a bad update cannot
/// strand them. Returns a human-readable note when it acted.
pub fn rollback_user_state_if_backed_up<R: Runtime>(app: &AppHandle<R>) -> Option<String> {
    match backup_root(app) {
        Ok(root) if root.join("ledger").exists() => match restore_backup(app) {
            Ok(true) => Some(format!(
                "Restored your ledger from the pre-update backup at {}.",
                root.display()
            )),
            _ => None,
        },
        _ => None,
    }
}
