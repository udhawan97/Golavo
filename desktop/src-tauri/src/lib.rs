//! Golavo desktop shell.
//!
//! Launch sequence (all before any window is shown):
//!   1. pick a free 127.0.0.1 port and mint a per-launch token;
//!   2. spawn the PyInstaller sidecar (`golavo-sidecar-<target-triple>`) with them;
//!   3. block on the sidecar's /health until ready (bounded timeout);
//!   4. build the window, injecting {apiBase, token} so the bundled UI talks to
//!      the ephemeral port — nothing is hardcoded;
//!   5. on any exit, kill the sidecar (RunEvent::ExitRequested/Exit — Tauri v2's
//!      equivalent of the old on_before_exit; Windows installers force-exit too).

mod health;
mod updater;

use std::sync::Mutex;
use std::time::Duration;

use tauri::{AppHandle, Manager, RunEvent, WebviewUrl, WebviewWindowBuilder};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

/// Upper bound on how long we wait for the sidecar's /health. The frozen sidecar
/// answers /health in well under a second (heavy imports are deferred), but we
/// stay generous for cold disks, first-run extraction, and slower CI runners.
const HEALTH_TIMEOUT: Duration = Duration::from_secs(90);

/// Holds the running sidecar so we can kill it on exit. `take()`-based so a
/// double exit event (ExitRequested then Exit) kills exactly once.
struct SidecarState(Mutex<Option<CommandChild>>);

pub fn run() {
    let builder = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init());

    // Signed auto-update is gated behind the `updater` feature: only a maintainer
    // build that holds the key pair registers the plugin (see src/updater.rs).
    #[cfg(feature = "updater")]
    let builder = builder.plugin(tauri_plugin_updater::Builder::new().build());

    builder
        .setup(|app| {
            let handle = app.handle().clone();

            // 1. port + token.
            let port = health::pick_free_port()?;
            let token = health::generate_token();

            // The sidecar's writable ledger lives under the per-user app-data dir
            // so future sealing persists and the updater has state to back up.
            let ledger = updater::ledger_dir(&handle).map_err(std::io::Error::other)?;
            std::fs::create_dir_all(&ledger)?;
            let ledger_str = ledger.to_string_lossy().to_string();

            // 2. spawn the sidecar.
            let child = spawn_sidecar(&handle, port, &token, &ledger_str)
                .map_err(std::io::Error::other)?;
            app.manage(SidecarState(Mutex::new(Some(child))));

            // 3. readiness gate — block until /health is ok or we time out.
            match health::wait_for_health(port, &token, HEALTH_TIMEOUT) {
                Ok(elapsed) => {
                    eprintln!("[golavo] sidecar healthy on 127.0.0.1:{port} after {elapsed:?}");
                }
                Err(err) => {
                    // Never leave an orphan: kill before we bail.
                    kill_sidecar(&handle);
                    if let Some(note) = updater::rollback_user_state_if_backed_up(&handle) {
                        eprintln!("[golavo] {note}");
                    }
                    return Err(std::io::Error::other(format!(
                        "sidecar failed to become healthy: {err}"
                    ))
                    .into());
                }
            }

            // 4. build the window with the runtime config injected. The script runs
            //    before the page's own scripts, so window.__GOLAVO_RUNTIME__ is set
            //    by the time the UI's data layer reads it.
            let config = serde_json::json!({
                "apiBase": format!("http://127.0.0.1:{port}"),
                "token": token,
            });
            let init_script = format!("window.__GOLAVO_RUNTIME__ = {config};");

            WebviewWindowBuilder::new(&handle, "main", WebviewUrl::App("index.html".into()))
                .title("Golavo · Forecast Audit Workbench")
                .inner_size(1200.0, 820.0)
                .min_inner_size(880.0, 600.0)
                .initialization_script(&init_script)
                .build()?;

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![updater::check_for_update])
        .build(tauri::generate_context!())
        .expect("error building Golavo desktop shell")
        .run(|handle, event| match event {
            // 5. kill the sidecar on every exit path.
            RunEvent::ExitRequested { .. } | RunEvent::Exit => kill_sidecar(handle),
            _ => {}
        });
}

fn spawn_sidecar(
    app: &AppHandle,
    port: u16,
    token: &str,
    data_dir: &str,
) -> Result<CommandChild, String> {
    let command = app
        .shell()
        .sidecar("golavo-sidecar")
        .map_err(|e| format!("sidecar not found (did packaging copy it in?): {e}"))?
        .args([
            "--host",
            "127.0.0.1",
            "--port",
            &port.to_string(),
            "--token",
            token,
            "--data-dir",
            data_dir,
            // The sidecar exits if this shell dies. Belt-and-suspenders with the
            // explicit kill on exit: the PyInstaller onefile bootloader forks a
            // Python child that Tauri's kill can't reach, so the child watches us.
            "--parent-pid",
            &std::process::id().to_string(),
        ]);
    let (mut rx, child) = command.spawn().map_err(|e| e.to_string())?;

    // Drain the sidecar's output so its pipes never fill and we get diagnostics.
    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(bytes) => {
                    eprint!("[sidecar] {}", String::from_utf8_lossy(&bytes));
                }
                CommandEvent::Stderr(bytes) => {
                    eprint!("[sidecar:err] {}", String::from_utf8_lossy(&bytes));
                }
                CommandEvent::Terminated(payload) => {
                    eprintln!("[sidecar] terminated: {payload:?}");
                }
                _ => {}
            }
        }
    });

    Ok(child)
}

fn kill_sidecar(app: &AppHandle) {
    if let Some(state) = app.try_state::<SidecarState>() {
        if let Ok(mut guard) = state.0.lock() {
            if let Some(child) = guard.take() {
                let _ = child.kill();
                eprintln!("[golavo] sidecar killed on exit");
            }
        }
    }
}
