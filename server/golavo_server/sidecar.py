"""Frozen sidecar entrypoint: boot the read-only FastAPI server on loopback.

This is the module PyInstaller freezes into ``golavo-sidecar-<target-triple>``.
The desktop shell spawns it with a chosen port and per-launch token; CI and
developers can also run it directly.

Run modes:
  golavo-sidecar --host H --port P --token T   serve (blocks) on http://H:P
  golavo-sidecar --smoke                        boot on an ephemeral port, probe
                                                /health + search + notebook,
                                                print version, exit 0/1
  golavo-sidecar --version                      print the version and exit

Args override the matching GOLAVO_* environment variables. When no port is given
the sidecar picks a free loopback port itself and prints it (useful for manual
runs); the shell always passes an explicit port.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import threading
import time
import urllib.request

SMOKE_TIMEOUT_S = 30.0


def _free_loopback_port(host: str = "127.0.0.1") -> int:
    """Ask the OS for a free TCP port on ``host`` and release it immediately."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


# Windows constants for the parent-liveness probe (ctypes, no extra deps).
_WIN_SYNCHRONIZE = 0x0010_0000
_WIN_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_WIN_ERROR_ACCESS_DENIED = 5
_WIN_WAIT_TIMEOUT = 0x102
_WIN_INFINITE = 0xFFFFFFFF


def _pid_alive(pid: int) -> bool:
    """True if a process with this pid is still running.

    On Windows ``os.kill(pid, 0)`` is NOT a probe: CPython maps every signal
    except CTRL_C/CTRL_BREAK to TerminateProcess, which would kill the very
    shell we are watching — so Windows probes via OpenProcess instead."""
    if os.name == "nt":
        return _pid_alive_windows(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, just not ours to signal
    except OSError:
        return False
    return True


def _pid_alive_windows(pid: int, _kernel32=None, _get_last_error=None) -> bool:
    """Windows probe: zero-timeout wait on the process handle. WAIT_TIMEOUT
    means still running; a signaled handle means it exited (the pid may linger
    as a zombie object while handles to it are held, so waiting beats polling
    the pid table). The ``_kernel32``/``_get_last_error`` hooks exist for tests."""
    import ctypes

    kernel32 = _kernel32 or ctypes.WinDLL("kernel32", use_last_error=True)
    access = _WIN_SYNCHRONIZE | _WIN_PROCESS_QUERY_LIMITED_INFORMATION
    handle = kernel32.OpenProcess(access, False, pid)
    if not handle:
        # Access denied => it exists but is not ours; any other failure
        # (invalid parameter etc.) => no such process. get_last_error is
        # resolved lazily — the attribute only exists on Windows.
        get_last_error = _get_last_error or ctypes.get_last_error
        return get_last_error() == _WIN_ERROR_ACCESS_DENIED
    try:
        return kernel32.WaitForSingleObject(handle, 0) == _WIN_WAIT_TIMEOUT
    finally:
        kernel32.CloseHandle(handle)


def _orphaned(initial_ppid: int, current_ppid: int, parent_pid: int, *, posix: bool) -> bool:
    """Whether the launching shell is gone and the sidecar should self-exit.

    On POSIX an orphaned child is reparented (PPID -> 1 or a changed PPID), the
    fast signal on a graceful quit. Windows does NOT reparent — ``os.getppid()``
    keeps returning the stale, now-dead value — so the reparent heuristic is
    disabled there (it would be both a false negative on quit and, if the PID
    were reused, a false positive). The parent-liveness probe is authoritative
    on every platform."""
    reparented = posix and (current_ppid == 1 or current_ppid != initial_ppid)
    return reparented or not _pid_alive(parent_pid)


def _watch_parent(parent_pid: int) -> None:
    """Exit the whole process when the launching shell goes away.

    Critical for the PyInstaller *onefile* sidecar: it runs as two processes — a
    bootloader that forks the real Python child. When the shell kills the child
    it spawned (the bootloader), this Python process is reparented and would
    otherwise linger, holding the port. Only enabled when the shell passes
    --parent-pid, so manual and smoke runs are unaffected.

    POSIX polls ``_orphaned`` (reparent + liveness). Windows pins the shell's
    process handle once and waits on it — immune to pid reuse. Any unexpected
    probe error counts as parent-gone: exiting beats orphaning the port."""
    if os.name == "nt":
        _watch_parent_windows(parent_pid)
        return
    initial_ppid = os.getppid()
    while True:
        time.sleep(1.0)
        try:
            if _orphaned(initial_ppid, os.getppid(), parent_pid, posix=True):
                os._exit(0)
        except OSError:
            os._exit(0)


def _watch_parent_windows(parent_pid: int, _kernel32=None) -> None:
    """Windows parent watch: hold a SYNCHRONIZE handle to the shell and block
    until it is signaled (the shell exited). Holding the handle pins the process
    identity, so a recycled pid can never fool the watchdog. Falls back to
    1s polling if the handle cannot be opened (already gone / access denied)."""
    import ctypes

    kernel32 = _kernel32 or ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.OpenProcess(_WIN_SYNCHRONIZE, False, parent_pid)
    if handle:
        try:
            kernel32.WaitForSingleObject(handle, _WIN_INFINITE)
        finally:
            kernel32.CloseHandle(handle)
        os._exit(0)
    while True:
        time.sleep(1.0)
        try:
            if not _pid_alive(parent_pid):
                os._exit(0)
        except OSError:
            os._exit(0)


def _warm_calibration() -> None:
    """Pre-import the scientific stack so the first /calibration request does not
    pay ~30s of numpy/pandas/scipy import time from the frozen bundle. Runs in a
    daemon thread the moment serving starts, overlapping with the user browsing
    the (dependency-light) eval summary. Best-effort: failures are swallowed and
    simply mean the first calibration call imports lazily as before."""
    try:
        import golavo_core.calibration  # noqa: F401
    except Exception:  # noqa: BLE001 (warm-up must never crash the server)
        pass


def _warm_search() -> None:
    """Pre-load the frozen match index so the first /matches/search request does
    not pay the ~25s pandas+parquet stall. Runs in a daemon thread the moment
    serving starts. Best-effort: a missing/corrupt index is swallowed and the
    first search fails closed (503) exactly as it would have anyway."""
    try:
        from golavo_server import matches

        matches._load_index()
    except Exception:  # noqa: BLE001 (warm-up must never crash the server)
        pass


def _serve(
    host: str,
    port: int,
    token: str | None,
    data_dir: str | None,
    parent_pid: int | None = None,
) -> None:
    """Run uvicorn (blocking). Env is set BEFORE importing the app so its
    module-level config (ledger dir) and the token gate see the right values."""
    if token:
        os.environ["GOLAVO_TOKEN"] = token
    if data_dir:
        os.environ["GOLAVO_DATA_DIR"] = data_dir
    import uvicorn

    from golavo_server.main import app

    if parent_pid:
        threading.Thread(
            target=_watch_parent, args=(parent_pid,), name="watch-parent", daemon=True
        ).start()
    threading.Thread(target=_warm_calibration, name="warm-calibration", daemon=True).start()
    threading.Thread(target=_warm_search, name="warm-search", daemon=True).start()
    uvicorn.run(app, host=host, port=port, log_level="warning")


def _smoke(timeout: float = SMOKE_TIMEOUT_S) -> int:
    """Boot the server on an ephemeral port in a background thread and assert
    that /health becomes ready AND the match-search AND on-demand-notebook
    surfaces answer. Returns 0 on success, 1 on timeout/failure.

    The extra probes are what catch a frozen build that dropped a datas entry:
    /health only proves the server booted, while a missing index makes
    /matches/search fail closed with a 503, and a missing runtime schema
    (docs/contracts) makes every on-demand /matches/{id}/notebook fail closed
    to ``available: false`` — the v0.2.3 desktop regression. Smoke runs with
    a token (see _serve), so the probes attach it — /health is exempt, the
    /api/* routes are not."""
    from golavo_server import __version__, runtime

    host = "127.0.0.1"
    port = _free_loopback_port(host)
    token = "smoke-" + os.urandom(8).hex()
    thread = threading.Thread(
        target=_serve,
        kwargs={"host": host, "port": port, "token": token, "data_dir": None},
        daemon=True,
    )
    thread.start()

    health_url = f"http://{host}:{port}/health"
    deadline = time.monotonic() + timeout
    last_error = "server did not start"
    healthy = False
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(health_url, timeout=2.0) as response:  # noqa: S310 (loopback only)
                body = json.loads(response.read().decode("utf-8"))
            if body.get("status") == "ok" and body.get("version") == __version__:
                healthy = True
                break
            last_error = f"unexpected /health body: {body}"
        except Exception as exc:  # noqa: BLE001 (probe: any failure means not-ready-yet)
            last_error = str(exc)
        time.sleep(0.25)

    if not healthy:
        print(
            f"golavo-sidecar {__version__}: smoke FAILED after {timeout:.0f}s ({last_error})",
            file=sys.stderr,
        )
        return 1

    # The bundled match index must be reachable through the real API route.
    search_url = f"http://{host}:{port}/api/v1/matches/search?q=br"
    request = urllib.request.Request(search_url)  # noqa: S310 (loopback only)
    if token:
        request.add_header(runtime.TOKEN_HEADER, token)  # the /api/* gate is on in smoke mode
    try:
        with urllib.request.urlopen(request, timeout=5.0) as response:  # noqa: S310 (loopback only)
            search_body = json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 (any failure => the search surface is broken)
        print(
            f"golavo-sidecar {__version__}: smoke FAILED — /matches/search probe error ({exc})",
            file=sys.stderr,
        )
        return 1
    if not isinstance(search_body.get("matches"), list) or not search_body["matches"]:
        print(
            f"golavo-sidecar {__version__}: smoke FAILED — search returned no matches "
            f"({search_body})",
            file=sys.stderr,
        )
        return 1

    # One real on-demand notebook exercises the facts engine end to end,
    # including the bundled facts.schema.json: the route fails closed to
    # available:false on any build/validate error, so a frozen build missing a
    # docs/contracts datas entry fails smoke here instead of shipping.
    match_id = search_body["matches"][0]["match_id"]
    notebook_url = f"http://{host}:{port}/api/v1/matches/{match_id}/notebook"
    request = urllib.request.Request(notebook_url)  # noqa: S310 (loopback only)
    if token:
        request.add_header(runtime.TOKEN_HEADER, token)
    try:
        with urllib.request.urlopen(request, timeout=30.0) as response:  # noqa: S310 (loopback only)
            notebook_body = json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 (any failure => the notebook surface is broken)
        print(
            f"golavo-sidecar {__version__}: smoke FAILED — notebook probe error for "
            f"{match_id} ({exc})",
            file=sys.stderr,
        )
        return 1
    if notebook_body.get("available") is not True:
        print(
            f"golavo-sidecar {__version__}: smoke FAILED — notebook unavailable for "
            f"{match_id}; a runtime schema is likely missing from the bundle "
            f"({notebook_body})",
            file=sys.stderr,
        )
        return 1

    n = len(search_body["matches"])
    print(
        f"golavo-sidecar {__version__}: smoke OK on {host}:{port} "
        f"(health + {n} search matches + notebook {match_id})"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="golavo-sidecar")
    parser.add_argument(
        "--smoke", action="store_true", help="boot, probe /health + search + notebook, exit 0/1"
    )
    parser.add_argument("--version", action="store_true", help="print version and exit")
    parser.add_argument("--host", default=os.environ.get("GOLAVO_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("GOLAVO_PORT") or 0))
    parser.add_argument("--token", default=os.environ.get("GOLAVO_TOKEN"))
    parser.add_argument("--data-dir", default=os.environ.get("GOLAVO_DATA_DIR"))
    parser.add_argument(
        "--parent-pid",
        type=int,
        default=int(os.environ.get("GOLAVO_PARENT_PID") or 0) or None,
        help="exit when this pid (the launching shell) goes away",
    )
    args = parser.parse_args(argv)

    from golavo_server import __version__

    if args.version:
        print(__version__)
        return 0
    if args.smoke:
        return _smoke()

    host = args.host
    port = args.port or _free_loopback_port(host)
    print(f"golavo-sidecar {__version__}: serving on http://{host}:{port}", flush=True)
    _serve(host, port, args.token, args.data_dir, args.parent_pid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
