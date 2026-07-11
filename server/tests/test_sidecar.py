"""Tests for the desktop sidecar surface: token gate, smoke mode, frozen paths."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from golavo_server import main as server_main
from golavo_server import runtime, sidecar


def test_api_is_open_when_no_token_is_configured(monkeypatch) -> None:
    monkeypatch.delenv("GOLAVO_TOKEN", raising=False)
    client = TestClient(server_main.app)
    assert client.get("/api/v1/eval/summary").status_code == 200


def test_token_gate_enforces_api_but_exempts_health_and_preflight(monkeypatch) -> None:
    monkeypatch.setenv("GOLAVO_TOKEN", "launch-token-xyz")
    client = TestClient(server_main.app)

    # /health is a liveness probe: always reachable so the shell's readiness gate
    # and CI smoke test never need the token.
    assert client.get("/health").status_code == 200

    # API routes require the exact token.
    assert client.get("/api/v1/eval/summary").status_code == 401
    assert (
        client.get("/api/v1/eval/summary", headers={runtime.TOKEN_HEADER: "wrong"}).status_code
        == 401
    )
    ok = client.get("/api/v1/eval/summary", headers={runtime.TOKEN_HEADER: "launch-token-xyz"})
    assert ok.status_code == 200

    # A CORS preflight (OPTIONS) carries no token and must not be rejected.
    preflight = client.options(
        "/api/v1/eval/summary",
        headers={
            "Origin": "tauri://localhost",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == "tauri://localhost"


def test_data_dir_honours_the_environment_override(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("GOLAVO_DATA_DIR", str(tmp_path))
    assert runtime.data_dir() == tmp_path
    monkeypatch.delenv("GOLAVO_DATA_DIR", raising=False)
    # Falls back to the bundled resource path (repo root in source mode).
    assert runtime.data_dir().name == "artifacts"


def test_sidecar_version_mode_prints_and_exits_zero(capsys) -> None:
    from golavo_server import __version__

    assert sidecar.main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == __version__


def test_sidecar_smoke_mode_boots_and_probes_health() -> None:
    # Boots a real uvicorn server on an ephemeral loopback port and asserts
    # /health reports ok before the bounded timeout (the probe self-bounds).
    assert sidecar._smoke(timeout=30.0) == 0


def test_schema_path_resolves_and_exists() -> None:
    from golavo_core.resources import schema_path

    assert schema_path().is_file()
    assert schema_path().name == "forecast_artifact.schema.json"


def test_frozen_resolver_uses_meipass(monkeypatch, tmp_path) -> None:
    from golavo_core import resources

    monkeypatch.setattr(resources.sys, "frozen", True, raising=False)
    monkeypatch.setattr(resources.sys, "_MEIPASS", str(tmp_path), raising=False)
    assert resources.resource_root() == Path(tmp_path)
    assert resources.schema_path() == tmp_path / "docs/contracts/forecast_artifact.schema.json"


# --- parent-pid watchdog -----------------------------------------------------


def test_pid_alive_true_for_own_process() -> None:
    import os

    assert sidecar._pid_alive(os.getpid()) is True


def test_pid_alive_false_for_exited_child() -> None:
    import subprocess
    import sys

    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()
    assert sidecar._pid_alive(child.pid) is False


def test_pid_alive_routes_to_windows_probe_on_nt(monkeypatch) -> None:
    # On Windows the POSIX path (os.kill) would TERMINATE the probed process;
    # the dispatcher must route to the OpenProcess-based probe instead.
    calls: list[int] = []
    monkeypatch.setattr(sidecar.os, "name", "nt")
    monkeypatch.setattr(sidecar, "_pid_alive_windows", lambda pid: calls.append(pid) or True)

    def _forbidden(*_args):  # pragma: no cover - fails the test if reached
        raise AssertionError("os.kill must never be used to probe on Windows")

    monkeypatch.setattr(sidecar.os, "kill", _forbidden)
    assert sidecar._pid_alive(4242) is True
    assert calls == [4242]


class _FakeKernel32:
    """Just enough of kernel32 for the probe: scripted OpenProcess/Wait results."""

    def __init__(self, open_result: int, wait_result: int | None = None) -> None:
        self.open_result = open_result
        self.wait_result = wait_result
        self.closed: list[int] = []

    def OpenProcess(self, _access, _inherit, _pid):  # noqa: N802 (WinAPI casing)
        return self.open_result

    def WaitForSingleObject(self, handle, _timeout):  # noqa: N802
        assert handle == self.open_result
        return self.wait_result

    def CloseHandle(self, handle):  # noqa: N802
        self.closed.append(handle)


def test_windows_probe_alive_while_wait_times_out() -> None:
    kernel32 = _FakeKernel32(open_result=1234, wait_result=sidecar._WIN_WAIT_TIMEOUT)
    assert sidecar._pid_alive_windows(1, _kernel32=kernel32) is True
    assert kernel32.closed == [1234]  # handle is never leaked


def test_windows_probe_dead_once_handle_is_signaled() -> None:
    kernel32 = _FakeKernel32(open_result=1234, wait_result=0)  # WAIT_OBJECT_0
    assert sidecar._pid_alive_windows(1, _kernel32=kernel32) is False
    assert kernel32.closed == [1234]


def test_windows_probe_maps_open_failures() -> None:
    denied = _FakeKernel32(open_result=0)
    assert (
        sidecar._pid_alive_windows(
            1, _kernel32=denied, _get_last_error=lambda: sidecar._WIN_ERROR_ACCESS_DENIED
        )
        is True
    )  # exists, just not ours
    gone = _FakeKernel32(open_result=0)
    assert sidecar._pid_alive_windows(1, _kernel32=gone, _get_last_error=lambda: 87) is False


# --- update-install shutdown endpoint ----------------------------------------


def test_shutdown_is_disabled_in_source_mode(monkeypatch) -> None:
    # No launch token => source mode => the route must not exist for callers:
    # browsers send cross-origin "simple" POSTs before CORS applies, so an open
    # shutdown route would let any webpage kill a dev server.
    monkeypatch.delenv("GOLAVO_TOKEN", raising=False)
    client = TestClient(server_main.app)
    assert client.post("/api/v1/shutdown").status_code == 404


def test_shutdown_requires_the_launch_token(monkeypatch) -> None:
    monkeypatch.setenv("GOLAVO_TOKEN", "launch-token-xyz")
    client = TestClient(server_main.app)
    assert client.post("/api/v1/shutdown").status_code == 401
    assert (
        client.post("/api/v1/shutdown", headers={runtime.TOKEN_HEADER: "wrong"}).status_code == 401
    )


def test_shutdown_schedules_exit_and_flushes_the_response(monkeypatch) -> None:
    import threading

    scheduled: list[tuple] = []

    class FakeTimer:
        def __init__(self, delay, fn, args=()):
            scheduled.append((delay, fn, args))

        def start(self):
            pass

    monkeypatch.setenv("GOLAVO_TOKEN", "launch-token-xyz")
    monkeypatch.setattr(threading, "Timer", FakeTimer)
    client = TestClient(server_main.app)
    response = client.post("/api/v1/shutdown", headers={runtime.TOKEN_HEADER: "launch-token-xyz"})
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    # os._exit is scheduled (not called inline — the 200 must flush first).
    import os

    assert scheduled and scheduled[0][1] is os._exit and scheduled[0][2] == (0,)
