//! Golavo desktop shell.
//!
//! Launch sequence:
//!   1. pick a free 127.0.0.1 port and mint a per-launch token;
//!   2. spawn the PyInstaller sidecar (`golavo-sidecar-<target-triple>`) with them;
//!   3. build the window IMMEDIATELY, injecting {apiBase, token, appVersion} so
//!      the UI renders a "starting" splash at once — the onefile sidecar takes
//!      ~30-40s to self-extract, and a blank window that whole time reads as
//!      broken;
//!   4. wait for /health OFF the main thread. On ready, finalize any pending
//!      update (retire backup, record success) and emit `backend://ready` so the
//!      UI swaps the splash for the app. On failure, repair (restore the ledger
//!      if this is the first boot after an install) and show a native dialog
//!      instead of dying as an invisible panic, then exit;
//!   5. on any exit, kill the sidecar (RunEvent::ExitRequested/Exit). Updates
//!      additionally stop it FIRST via stop_sidecar_for_install: the Windows
//!      installer path exits the process without firing those events, and the
//!      NSIS template only kills the main exe — never a live sidecar.

mod health;
mod updater;

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use tauri::{AppHandle, Emitter, Manager, RunEvent, WebviewUrl, WebviewWindowBuilder};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

/// Show a native error dialog and BLOCK until the user dismisses it. Called from
/// the launch path's background health thread (see run()); the CALLER marshals
/// the non-macOS branch onto the main thread because rfd touches native UI.
///
/// macOS uses `osascript` (a subprocess), which blocks until dismissed and is
/// safe to invoke from any thread — and it also sidesteps the empirically-
/// verified issue that `NSAlert.runModal` does NOT block when the app isn't a
/// fully-activated foreground app, flashing the dialog and orphaning the window.
/// rfd is retained for Windows/Linux, where MessageBox-style dialogs block
/// correctly — but must run on the main thread (GTK on Linux), hence the caller's
/// run_on_main_thread for that branch.
fn show_fatal_dialog(title: &str, message: &str) {
    #[cfg(target_os = "macos")]
    {
        let script = format!(
            "display alert {} message {} as critical buttons {{\"OK\"}} default button \"OK\"",
            applescript_string(title),
            applescript_string(message),
        );
        // If osascript itself can't run, the eprintln at the call site is the
        // remaining record — but we tried the reliable path first.
        let _ = std::process::Command::new("osascript")
            .arg("-e")
            .arg(script)
            .status();
    }
    #[cfg(not(target_os = "macos"))]
    {
        rfd::MessageDialog::new()
            .set_level(rfd::MessageLevel::Error)
            .set_title(title)
            .set_description(message)
            .set_buttons(rfd::MessageButtons::Ok)
            .show();
    }
}

/// Wrap a string as an AppleScript string literal, escaping the characters that
/// would otherwise break the `-e` script (backslash, quote) or its parsing
/// (raw newlines aren't allowed inside a literal; `\n` is).
#[cfg(target_os = "macos")]
fn applescript_string(s: &str) -> String {
    let escaped = s
        .replace('\\', "\\\\")
        .replace('"', "\\\"")
        .replace('\n', "\\n");
    format!("\"{escaped}\"")
}

/// Upper bound on how long we wait for the sidecar's /health. The frozen sidecar
/// answers /health in well under a second (heavy imports are deferred), but we
/// stay generous for cold disks, first-run extraction, and slower CI runners.
const HEALTH_TIMEOUT: Duration = Duration::from_secs(90);

/// How long stop_sidecar_for_install waits for a graceful exit before the hard
/// kill. The sidecar's uvicorn + PyInstaller child normally exit in well under
/// a second after the shutdown POST.
#[cfg_attr(not(feature = "updater"), allow(dead_code))]
const SIDECAR_STOP_TIMEOUT: Duration = Duration::from_secs(10);

/// Everything needed to supervise (and politely stop) the running sidecar.
/// `child` is `take()`-based so a double exit event kills exactly once;
/// `terminated` is flipped by the output-drain task when the process actually
/// goes away, which is what the pre-install stop waits on.
#[cfg_attr(not(feature = "updater"), allow(dead_code))] // stop-for-install reads the extras
struct SidecarState {
    child: Mutex<Option<CommandChild>>,
    terminated: Arc<AtomicBool>,
    port: u16,
    token: String,
}

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

            #[cfg(feature = "updater")]
            app.manage(updater::UpdaterEngine::default());

            // 1. port + token.
            let port = health::pick_free_port()?;
            let token = health::generate_token();

            // The sidecar's writable ledger lives under the per-user app-data dir
            // so future sealing persists and the updater has state to back up.
            // Finish any restore that a crash interrupted mid-swap BEFORE creating
            // the dir, so we never fabricate an empty ledger over a real one.
            let ledger = updater::ledger_dir(&handle).map_err(std::io::Error::other)?;
            updater::recover_interrupted_restore(&handle);
            std::fs::create_dir_all(&ledger)?;
            let ledger_str = ledger.to_string_lossy().to_string();

            // 2. spawn the sidecar.
            let terminated = Arc::new(AtomicBool::new(false));
            let child = spawn_sidecar(&handle, port, &token, &ledger_str, terminated.clone())
                .map_err(std::io::Error::other)?;
            app.manage(SidecarState {
                child: Mutex::new(Some(child)),
                terminated,
                port,
                token: token.clone(),
            });

            // 3. Build the window IMMEDIATELY with the runtime config injected —
            //    the port and token are already known, so the UI can render a
            //    "starting" splash right away instead of the user staring at a
            //    blank screen for ~30-40s while the onefile sidecar self-extracts.
            //    The script runs before the page's own scripts, so
            //    window.__GOLAVO_RUNTIME__ is set by the time the UI reads it.
            let config = serde_json::json!({
                "apiBase": format!("http://127.0.0.1:{port}"),
                "token": token,
                "appVersion": handle.package_info().version.to_string(),
            });
            let init_script = format!("window.__GOLAVO_RUNTIME__ = {config};");

            WebviewWindowBuilder::new(&handle, "main", WebviewUrl::App("index.html".into()))
                .title("Golavo · Forecast Audit Workbench")
                .inner_size(1200.0, 820.0)
                .min_inner_size(880.0, 600.0)
                .initialization_script(&init_script)
                .build()?;

            // 4. Wait for the sidecar's /health OFF the main thread so the window
            //    stays responsive and shows its loading state. On ready, tell the
            //    UI to swap the splash for the app; on failure, repair and show the
            //    fatal dialog (osascript, safe from any thread) then exit.
            let bg = handle.clone();
            std::thread::spawn(move || {
                match health::wait_for_health(port, &token, HEALTH_TIMEOUT) {
                    Ok(elapsed) => {
                        eprintln!("[golavo] sidecar healthy on 127.0.0.1:{port} after {elapsed:?}");
                        updater::finalize_update_if_pending(&bg);
                        let _ = bg.emit("backend://ready", ());
                    }
                    Err(err) => {
                        kill_sidecar(&bg);
                        let message = updater::repair_failed_launch(&bg, &err);
                        eprintln!("[golavo] launch failed: {message}");
                        // macOS shows the dialog via osascript (a subprocess),
                        // which is safe from this background thread and keeps the
                        // window responsive. Elsewhere rfd touches native UI that
                        // must run on the main thread, so marshal the dialog there.
                        #[cfg(target_os = "macos")]
                        {
                            show_fatal_dialog("Golavo could not start", &message);
                            std::process::exit(1);
                        }
                        #[cfg(not(target_os = "macos"))]
                        {
                            // If marshaling fails (event loop already gone), still
                            // exit — never leave a windowed process with a dead
                            // sidecar and no dialog.
                            if bg
                                .run_on_main_thread(move || {
                                    show_fatal_dialog("Golavo could not start", &message);
                                    std::process::exit(1);
                                })
                                .is_err()
                            {
                                std::process::exit(1);
                            }
                        }
                    }
                }
            });

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            updater::updater_status,
            updater::updater_check,
            updater::updater_download,
            updater::updater_cancel,
            updater::updater_install_and_restart,
            updater::updater_relaunch,
        ])
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
    terminated: Arc<AtomicBool>,
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
            "--data-dir",
            data_dir,
            // The sidecar exits if this shell dies. Belt-and-suspenders with the
            // explicit kill on exit: the PyInstaller onefile bootloader forks a
            // Python child that Tauri's kill can't reach, so the child watches us.
            "--parent-pid",
            &std::process::id().to_string(),
        ])
        // Hand the launch token to the sidecar through the environment, never as a
        // --token CLI argument: argv is readable by any same-user process via
        // `ps`/pgrep. The sidecar's --token defaults to GOLAVO_TOKEN, so this is the
        // exact same per-launch secret, just no longer exposed in the process list.
        .env("GOLAVO_TOKEN", token);
    let (mut rx, child) = command.spawn().map_err(|e| e.to_string())?;

    // Drain the sidecar's output so its pipes never fill and we get diagnostics;
    // flip `terminated` when it actually exits so the update path can wait on it.
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
                    terminated.store(true, Ordering::SeqCst);
                    eprintln!("[sidecar] terminated: {payload:?}");
                }
                _ => {}
            }
        }
        // Channel closed — the process is gone even if no Terminated event came.
        terminated.store(true, Ordering::SeqCst);
    });

    Ok(child)
}

fn kill_sidecar<R: tauri::Runtime>(app: &AppHandle<R>) {
    if let Some(state) = app.try_state::<SidecarState>() {
        if let Ok(mut guard) = state.child.lock() {
            if let Some(child) = guard.take() {
                let _ = child.kill();
                eprintln!("[golavo] sidecar killed on exit");
            }
        }
    }
}

/// Stop the sidecar BEFORE an update installs. A plain kill only reaches the
/// PyInstaller onefile BOOTLOADER — the forked Python child would keep running
/// and keep `golavo-sidecar.exe` locked, failing the Windows installer with
/// file-in-use. So: polite token-gated shutdown POST (the whole tree exits
/// itself), bounded wait for the drain task to confirm, hard kill as backstop.
#[cfg_attr(not(feature = "updater"), allow(dead_code))]
pub(crate) fn stop_sidecar_for_install<R: tauri::Runtime>(app: &AppHandle<R>) {
    if let Some(state) = app.try_state::<SidecarState>() {
        if let Err(e) = health::post_shutdown(state.port, &state.token) {
            eprintln!("[golavo] sidecar shutdown request failed ({e}); will hard-kill");
        }
        let deadline = Instant::now() + SIDECAR_STOP_TIMEOUT;
        while !state.terminated.load(Ordering::SeqCst) && Instant::now() < deadline {
            std::thread::sleep(Duration::from_millis(100));
        }
        if state.terminated.load(Ordering::SeqCst) {
            eprintln!("[golavo] sidecar exited gracefully for update install");
            // The process is gone; drop the stale child handle without kill().
            if let Ok(mut guard) = state.child.lock() {
                guard.take();
            }
            return;
        }
    }
    kill_sidecar(app);
}
