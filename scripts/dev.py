#!/usr/bin/env python3
"""Run Golavo's local API and browser UI as one source-mode process."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Start Golavo locally and open the browser UI.",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="start both services without opening a browser tab",
    )
    return parser


def _stop(processes: list[subprocess.Popen[bytes]]) -> None:
    for process in processes:
        if process.poll() is None:
            process.terminate()
    deadline = time.monotonic() + 5
    for process in processes:
        if process.poll() is None:
            try:
                process.wait(timeout=max(0.1, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                process.kill()
    for process in processes:
        if process.poll() is None:
            process.wait()


def main() -> int:
    args = _parser().parse_args()
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if npm is None:
        raise SystemExit("npm was not found. Install Node 22+ and run `make setup` first.")

    env = os.environ.copy()
    env["VITE_GOLAVO_API"] = "http://127.0.0.1:8000"
    ui_command = [npm, "run", "dev", "--", "--host", "127.0.0.1"]
    if not args.no_open:
        ui_command.append("--open")

    commands = [
        (
            [
                sys.executable,
                "-m",
                "uvicorn",
                "golavo_server.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
                "--app-dir",
                "server",
            ],
            ROOT,
            env,
        ),
        (ui_command, ROOT / "ui", env),
    ]

    processes: list[subprocess.Popen[bytes]] = []
    try:
        for command, cwd, command_env in commands:
            processes.append(subprocess.Popen(command, cwd=cwd, env=command_env))
        print("Golavo is starting at http://127.0.0.1:5173", flush=True)
        print("Press Ctrl+C to stop both local services.", flush=True)
        while all(process.poll() is None for process in processes):
            time.sleep(0.25)
        return next(
            (process.returncode or 0 for process in processes if process.poll() is not None),
            0,
        )
    except KeyboardInterrupt:
        return 130
    finally:
        _stop(processes)


if __name__ == "__main__":
    raise SystemExit(main())
