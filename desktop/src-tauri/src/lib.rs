//! Golavo desktop shell.
//!
//! Launch sequence:
//!   1. pick a free 127.0.0.1 port and mint a per-launch token;
//!   2. spawn the PyInstaller sidecar (`golavo-sidecar-<target-triple>`) with them;
//!   3. build the window IMMEDIATELY, injecting {apiBase, token, appVersion} so
//!      the UI renders a "starting" splash at once — the onefile sidecar takes
//!      ~30-40s to self-extract, and a blank window that whole time reads as
//!      broken;
//!   4. supervise /health OFF the main thread. On ready, finalize any pending
//!      update (retire backup, record success), record a successful launch, and
//!      emit `backend://ready` so the UI swaps the splash for the app. On failure,
//!      repair (restore the ledger if this is the first boot after an install) and
//!      emit `backend://failed`, KEEPING THE WINDOW ALIVE so the splash owns a
//!      calm, recoverable failure tier (the UI retries once silently, then offers
//!      a manual "Try again" that calls `restart_sidecar`) — never a dead-end
//!      dialog-and-exit. The health patience is wider on a slow first launch;
//!   5. on any exit, kill the sidecar (RunEvent::ExitRequested/Exit). Updates
//!      additionally stop it FIRST via stop_sidecar_for_install: the Windows
//!      installer path exits the process without firing those events, and the
//!      NSIS template only kills the main exe — never a live sidecar.

mod fallback_update;
mod health;
mod updater;

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use tauri::{AppHandle, Emitter, Manager, RunEvent, WebviewUrl, WebviewWindowBuilder};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

/// How long we wait for /health on a FIRST launch (no prior success recorded).
/// The onefile sidecar self-extracts to a fresh temp dir and antivirus rescans
/// the new binaries, which on a slow machine can legitimately take past 90s —
/// killing it there would abort a launch that was seconds from ready. This must
/// stay at or above the UI's first-launch reassurance threshold so the two never
/// contradict (UI "still working" vs shell "failed").
const HEALTH_TIMEOUT_FIRST: Duration = Duration::from_secs(150);

/// How long we wait for /health once the app has started successfully before:
/// extraction is warm and imports are quick, so a long wait now means something
/// is actually wrong and the recoverable failure tier should appear sooner.
const HEALTH_TIMEOUT_RETURNING: Duration = Duration::from_secs(90);

/// How long stop_sidecar_for_install waits for a graceful exit before the hard
/// kill. The sidecar's uvicorn + PyInstaller child normally exit in well under
/// a second after the shutdown POST.
#[cfg_attr(not(feature = "updater"), allow(dead_code))]
const SIDECAR_STOP_TIMEOUT: Duration = Duration::from_secs(10);

/// Everything needed to supervise, restart, and politely stop the sidecar.
/// `child` is `take()`-based so a double exit event kills exactly once.
/// `terminated` is the CURRENT generation's flag (swapped on restart), flipped by
/// the output-drain task when the process goes away — what the stop paths wait on.
/// The port and token are stable across restarts: a restart reuses them, and it
/// only respawns after the previous process is confirmed gone, so the loopback
/// port is free (no same-port bind race). `ledger_dir` lets a restart re-spawn
/// without re-deriving it; `restarting` serializes concurrent restart requests.
struct SidecarState {
    child: Mutex<Option<CommandChild>>,
    terminated: Mutex<Arc<AtomicBool>>,
    port: u16,
    token: String,
    ledger_dir: String,
    restarting: AtomicBool,
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

            // The GitHub-release fallback updater is always available (it works
            // in unsigned dev/source builds too); its engine is managed here.
            app.manage(fallback_update::FallbackEngine::default());

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
            let first_launch = !has_launched_ok(&handle);
            app.manage(SidecarState {
                child: Mutex::new(Some(child)),
                terminated: Mutex::new(terminated),
                port,
                token: token.clone(),
                ledger_dir: ledger_str,
                restarting: AtomicBool::new(false),
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

            // 4. Supervise the launch OFF the main thread so the window stays
            //    responsive and shows its splash. On ready, swap to the app; on a
            //    genuine failure, emit `backend://failed` and KEEP THE WINDOW ALIVE
            //    so the splash owns a calm, recoverable failure tier (the UI silently
            //    retries once, then offers a manual restart) — never a dead-end
            //    native dialog and exit. See supervise_launch.
            let bg = handle.clone();
            std::thread::spawn(move || supervise_launch(bg, port, token, first_launch));

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            restart_sidecar,
            updater::updater_status,
            updater::updater_check,
            updater::updater_download,
            updater::updater_cancel,
            updater::updater_install_and_restart,
            updater::updater_relaunch,
            fallback_update::fallback_check,
            fallback_update::fallback_download,
            fallback_update::fallback_cancel,
            fallback_update::fallback_open,
        ])
        .build(tauri::generate_context!())
        .expect("error building Golavo desktop shell")
        .run(|handle, event| match event {
            // 5. kill the sidecar on every exit path.
            RunEvent::ExitRequested { .. } | RunEvent::Exit => kill_sidecar(handle),
            _ => {}
        });
}

/// Wait for the current sidecar generation to become healthy and drive the UI.
///
/// One owner of the launch outcome. On success it records the launch, finalizes a
/// pending update, and emits `backend://ready`. On any failure — a crash before
/// /health (`Exited`) or a slow generation that never answered (`TimedOut`) — it
/// cleans up and emits `backend://failed` with a human message, then RETURNS,
/// leaving the window alive. It never kills a slow-but-alive sidecar to "retry",
/// and it never exits the process: recovery is the UI's job (a silent single
/// retry via `restart_sidecar`, then a manual "Try again"). `first_launch`
/// widens the patience because a cold self-extract + AV rescan is legitimately
/// slow the very first time.
fn supervise_launch(app: AppHandle, port: u16, token: String, first_launch: bool) {
    let Some(state) = app.try_state::<SidecarState>() else { return };
    let terminated = match state.terminated.lock() {
        Ok(guard) => guard.clone(),
        Err(_) => return,
    };
    let timeout = if first_launch {
        HEALTH_TIMEOUT_FIRST
    } else {
        HEALTH_TIMEOUT_RETURNING
    };
    match health::wait_for_health_or_exit(port, &token, &terminated, timeout) {
        health::HealthOutcome::Healthy(elapsed) => {
            eprintln!("[golavo] sidecar healthy on 127.0.0.1:{port} after {elapsed:?}");
            mark_launched_ok(&app);
            updater::finalize_update_if_pending(&app);
            let _ = app.emit("backend://ready", ());
        }
        outcome => {
            let why = match outcome {
                health::HealthOutcome::Exited => "the local engine stopped before it was ready",
                _ => "the local engine did not answer in time",
            };
            // Reap whatever is left so a later restart binds the port cleanly.
            kill_sidecar(&app);
            let message = updater::repair_failed_launch(&app, why);
            eprintln!("[golavo] launch not ready: {message}");
            let _ = app.emit("backend://failed", FailedPayload { message });
        }
    }
}

/// Payload for `backend://failed` — a UI-safe reason string (never provider
/// internals or secrets; repair_failed_launch already produces a friendly line).
#[derive(Clone, serde::Serialize)]
struct FailedPayload {
    message: String,
}

/// Restart the local engine on demand. Both the UI's silent one-shot retry and
/// its manual "Try again" call this. It stops the current generation cleanly
/// (so the loopback port is free), spawns a fresh one on the SAME port + token
/// (the webview already holds them, so no reload is needed), and re-supervises.
/// `restarting` serializes concurrent presses into a single in-flight restart.
#[tauri::command]
fn restart_sidecar(app: AppHandle) -> Result<(), String> {
    let Some(state) = app.try_state::<SidecarState>() else {
        return Err("no engine to restart".into());
    };
    if state.restarting.swap(true, Ordering::SeqCst) {
        return Ok(()); // a restart is already in flight; coalesce.
    }
    let result = (|| -> Result<(u16, String), String> {
        stop_current_sidecar(&app);
        let new_terminated = Arc::new(AtomicBool::new(false));
        let child = spawn_sidecar(
            &app,
            state.port,
            &state.token,
            &state.ledger_dir,
            new_terminated.clone(),
        )?;
        if let Ok(mut guard) = state.child.lock() {
            *guard = Some(child);
        }
        if let Ok(mut guard) = state.terminated.lock() {
            *guard = new_terminated;
        }
        Ok((state.port, state.token.clone()))
    })();
    state.restarting.store(false, Ordering::SeqCst);
    let (port, token) = result?;
    // A restart is by definition not a first launch — use the tighter patience.
    let bg = app.clone();
    std::thread::spawn(move || supervise_launch(bg, port, token, false));
    Ok(())
}

/// Stop the current sidecar generation and wait until it is fully gone, so a
/// same-port respawn can bind cleanly. Mirrors stop_sidecar_for_install (polite
/// token-gated shutdown of the whole process tree, bounded wait, hard-kill
/// backstop) but is scoped to a restart rather than an update.
fn stop_current_sidecar(app: &AppHandle) {
    if let Some(state) = app.try_state::<SidecarState>() {
        let terminated = state.terminated.lock().ok().map(|g| g.clone());
        let _ = health::post_shutdown(state.port, &state.token);
        if let Some(flag) = terminated {
            let deadline = Instant::now() + SIDECAR_STOP_TIMEOUT;
            while !flag.load(Ordering::SeqCst) && Instant::now() < deadline {
                std::thread::sleep(Duration::from_millis(100));
            }
        }
    }
    // Hard-kill backstop drops the (possibly already-dead) child handle.
    kill_sidecar(app);
}

/// A tiny per-user marker recording that Golavo has started successfully at least
/// once. Its presence tightens the health patience on later launches; its absence
/// widens it for a slow cold first run. Lives beside the ledger in app-data.
fn launched_ok_marker(app: &AppHandle) -> Option<std::path::PathBuf> {
    let ledger = updater::ledger_dir(app).ok()?;
    Some(ledger.parent().unwrap_or(&ledger).join("launched-ok"))
}

fn has_launched_ok(app: &AppHandle) -> bool {
    launched_ok_marker(app).is_some_and(|p| p.exists())
}

fn mark_launched_ok(app: &AppHandle) {
    if let Some(path) = launched_ok_marker(app) {
        let _ = std::fs::write(path, b"1");
    }
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
        // Snapshot the current generation's flag; a restart may swap it, but the
        // install path stops whatever is live right now.
        let terminated = state.terminated.lock().ok().map(|g| g.clone());
        if let Some(flag) = terminated {
            let deadline = Instant::now() + SIDECAR_STOP_TIMEOUT;
            while !flag.load(Ordering::SeqCst) && Instant::now() < deadline {
                std::thread::sleep(Duration::from_millis(100));
            }
            if flag.load(Ordering::SeqCst) {
                eprintln!("[golavo] sidecar exited gracefully for update install");
                // The process is gone; drop the stale child handle without kill().
                if let Ok(mut guard) = state.child.lock() {
                    guard.take();
                }
                return;
            }
        }
    }
    kill_sidecar(app);
}
