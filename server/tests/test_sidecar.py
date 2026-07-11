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
