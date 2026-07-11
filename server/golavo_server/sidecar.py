"""Frozen sidecar entrypoint: boot the read-only FastAPI server on loopback.

This is the module PyInstaller freezes into ``golavo-sidecar-<target-triple>``.
The desktop shell spawns it with a chosen port and per-launch token; CI and
developers can also run it directly.

Run modes:
  golavo-sidecar --host H --port P --token T   serve (blocks) on http://H:P
  golavo-sidecar --smoke                        boot on an ephemeral port, probe
                                                /health, print version, exit 0/1
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


def _pid_alive(pid: int) -> bool:
    """True if a process with this pid exists (signal 0 probes without killing)."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, just not ours to signal
    return True


def _watch_parent(parent_pid: int) -> None:
    """Exit the whole process when the launching shell goes away.

    Critical for the PyInstaller *onefile* sidecar: it runs as two processes — a
    bootloader that forks the real Python child. When the shell kills the child
    it spawned (the bootloader), this Python process is reparented and would
    otherwise linger, holding the port. We watch for either the shell dying or
    a reparent (PPID -> 1 or a changed PPID) and hard-exit. Only enabled when the
    shell passes --parent-pid, so manual and smoke runs are unaffected."""
    initial_ppid = os.getppid()
    while True:
        time.sleep(1.0)
        ppid = os.getppid()
        reparented = ppid == 1 or ppid != initial_ppid
        if reparented or not _pid_alive(parent_pid):
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
    uvicorn.run(app, host=host, port=port, log_level="warning")


def _smoke(timeout: float = SMOKE_TIMEOUT_S) -> int:
    """Boot the server on an ephemeral port in a background thread and assert
    that /health becomes ready. Returns 0 on success, 1 on timeout/failure."""
    from golavo_server import __version__

    host = "127.0.0.1"
    port = _free_loopback_port(host)
    token = "smoke-" + os.urandom(8).hex()
    thread = threading.Thread(
        target=_serve,
        kwargs={"host": host, "port": port, "token": token, "data_dir": None},
        daemon=True,
    )
    thread.start()

    url = f"http://{host}:{port}/health"
    deadline = time.monotonic() + timeout
    last_error = "server did not start"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2.0) as response:  # noqa: S310 (loopback only)
                body = json.loads(response.read().decode("utf-8"))
            if body.get("status") == "ok" and body.get("version") == __version__:
                print(f"golavo-sidecar {__version__}: smoke OK on {host}:{port} ({body})")
                return 0
            last_error = f"unexpected /health body: {body}"
        except Exception as exc:  # noqa: BLE001 (probe: any failure means not-ready-yet)
            last_error = str(exc)
        time.sleep(0.25)

    print(
        f"golavo-sidecar {__version__}: smoke FAILED after {timeout:.0f}s ({last_error})",
        file=sys.stderr,
    )
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="golavo-sidecar")
    parser.add_argument("--smoke", action="store_true", help="boot, probe /health, exit 0/1")
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
