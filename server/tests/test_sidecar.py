"""Tests for the desktop sidecar surface: token gate, smoke mode, frozen paths."""

from __future__ import annotations

import os
import socket
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from golavo_server import main as server_main
from golavo_server import runtime, sidecar

# Environment variables the real sidecar entrypoint (``_serve``) writes directly
# to ``os.environ`` when it boots. That is correct for the standalone sidecar
# PROCESS, but ``test_sidecar_smoke_mode_boots_and_probes_health`` boots ``_serve``
# IN-PROCESS (via ``_smoke``), so those writes land in this pytest process and are
# never undone — unlike the ``monkeypatch``-based env changes elsewhere in this
# file, which self-restore. A leaked ``GOLAVO_TOKEN`` then turns the token gate on
# for every later test: run this file before ``test_ai_gateway`` and its
# unauthenticated endpoint requests all 401. (CI's alphabetical order hides it —
# ``test_ai_gateway`` runs first there.) See golavo_server.sidecar._serve.
_SIDECAR_ENV_VARS = ("GOLAVO_TOKEN", "GOLAVO_DATA_DIR", "SSL_CERT_FILE")


@pytest.fixture(autouse=True)
def _restore_sidecar_env() -> Iterator[None]:
    """Snapshot and restore ``_serve``'s env vars around every test in this file
    so an in-process sidecar boot can never leak its launch token (or data dir)
    across a test boundary."""
    saved = {name: os.environ.get(name) for name in _SIDECAR_ENV_VARS}
    try:
        yield
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


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


def test_serve_refuses_a_non_loopback_host() -> None:
    # The sidecar is local-only; binding a routable interface must be refused, not
    # silently exposed. Loopback hosts are accepted.
    for host in ("127.0.0.1", "localhost", "::1"):
        sidecar._assert_loopback(host)  # no raise
    for host in ("0.0.0.0", "192.168.1.10", "::"):
        with pytest.raises(SystemExit):
            sidecar._assert_loopback(host)


def test_sidecar_configures_bundled_tls_trust_without_overriding_operator(
    monkeypatch,
) -> None:
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    monkeypatch.setattr(sidecar.certifi, "where", lambda: "/bundle/certifi/cacert.pem")
    sidecar._configure_tls_trust()
    assert os.environ["SSL_CERT_FILE"] == "/bundle/certifi/cacert.pem"

    monkeypatch.setenv("SSL_CERT_FILE", "/operator/custom-ca.pem")
    sidecar._configure_tls_trust()
    assert os.environ["SSL_CERT_FILE"] == "/operator/custom-ca.pem"


def test_free_loopback_port_ipv4_default() -> None:
    port = sidecar._free_loopback_port("127.0.0.1")
    assert 0 < port < 65536


def test_free_loopback_port_binds_ipv6_family_for_ipv6_host() -> None:
    # A1/A11: ``_assert_loopback`` accepts ``::1`` but the port helper used to bind
    # AF_INET, which cannot bind an IPv6 address at all. It must now pick the
    # matching AF_INET6 family so a ``--host ::1`` run gets a real, bindable port.
    if not socket.has_ipv6:
        pytest.skip("IPv6 not supported on this host")
    try:
        port = sidecar._free_loopback_port("::1")
    except OSError:
        pytest.skip("IPv6 loopback not bindable in this environment")
    assert 0 < port < 65536


def test_sidecar_version_mode_prints_and_exits_zero(capsys) -> None:
    from golavo_server import __version__

    assert sidecar.main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == __version__


def test_sidecar_smoke_mode_boots_and_probes_health() -> None:
    # Boots a real uvicorn server on an ephemeral loopback port and asserts
    # /health reports ok before the bounded timeout (the probe self-bounds),
    # then that /matches/search answers and one on-demand notebook computes
    # (available: true) — the probes that catch dropped frozen datas entries.
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


def test_pyinstaller_spec_bundles_every_runtime_schema() -> None:
    # Every ``*schema_path`` resolver in golavo_core.resources is a schema the
    # server may read at runtime; one missing from the PyInstaller datas ships a
    # desktop build where the dependent surface silently fails closed (v0.2.3:
    # facts.schema.json was absent, so every on-demand notebook came back
    # ``available: false``). The frozen smoke probe catches this at build time;
    # this test catches it already at PR time, in source mode.
    import inspect

    from golavo_core import resources

    spec = Path(__file__).resolve().parents[2] / "packaging" / "golavo-sidecar.spec"
    spec_text = spec.read_text(encoding="utf-8")
    schema_names = [
        fn().name
        for name, fn in inspect.getmembers(resources, inspect.isfunction)
        if name.endswith("schema_path")
    ]
    assert schema_names, "no schema resolvers found in golavo_core.resources"
    for schema_name in schema_names:
        assert schema_name in spec_text, f"{schema_name} missing from the sidecar spec datas"


def test_pyinstaller_spec_bundles_display_context_runtime_files() -> None:
    spec = Path(__file__).resolve().parents[2] / "packaging" / "golavo-sidecar.spec"
    spec_text = spec.read_text(encoding="utf-8")
    for name in ("manifest.json", "venue_entities.json", "venue_assignments.json"):
        assert name in spec_text, f"data/context/{name} missing from sidecar datas"


def test_pyinstaller_spec_bundles_certifi_ca_store() -> None:
    spec = Path(__file__).resolve().parents[2] / "packaging" / "golavo-sidecar.spec"
    spec_text = spec.read_text(encoding="utf-8")
    assert 'collect_data_files("certifi")' in spec_text


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
