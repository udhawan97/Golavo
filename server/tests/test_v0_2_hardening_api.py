"""Regression tests for the v0.2 hardening fixes (server side).

H1 — the read-only API must fail closed on a tampered artifact: never serve it,
and omit it from the list rather than presenting it as a genuine sealed forecast.

H3 — the sidecar parent-watch must not use POSIX-only semantics on Windows, where
``os.kill(pid, 0)`` is destructive and reparenting never happens.
"""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from golavo_core.artifacts import canonical_bytes, seal_forecast
from golavo_server import main as server_main
from golavo_server import sidecar

REPO_ROOT = Path(__file__).resolve().parents[2]


def _seal_genuine(ledger: Path) -> str:
    path = seal_forecast(
        pack_dir=REPO_ROOT / "packs/martj42-internationals-273c731492df",
        output_dir=ledger,
        date="2026-07-09",
        home_team="France",
        away_team="Morocco",
        as_of_utc="2026-07-08T00:00:00Z",
    )
    return path.stem


def _write_tampered(ledger: Path, genuine_path: Path) -> str:
    """A schema-valid artifact whose numbers were edited after sealing, saved
    under a stem that no longer matches its content id."""
    artifact = json.loads(genuine_path.read_text(encoding="utf-8"))
    tampered = copy.deepcopy(artifact)
    probs = tampered["forecast"]["probs"]
    probs["home"], probs["away"] = probs["away"], probs["home"]  # still sums to 1
    stem = "fa_tampered0000000000"
    (ledger / f"{stem}.json").write_bytes(canonical_bytes(tampered) + b"\n")
    return stem


def test_api_fails_closed_on_a_tampered_artifact(monkeypatch, tmp_path) -> None:
    # Run in source mode (no launch token) — sidecar._serve leaks GOLAVO_TOKEN into
    # the process env, so clear it defensively rather than depend on test order.
    monkeypatch.delenv("GOLAVO_TOKEN", raising=False)
    ledger = tmp_path / "ledger"
    genuine_id = _seal_genuine(ledger)
    tampered_id = _write_tampered(ledger, ledger / f"{genuine_id}.json")
    monkeypatch.setattr(server_main, "ARTIFACT_DIR", ledger)
    client = TestClient(server_main.app)

    listed = client.get("/api/v1/forecasts").json()
    ids = [item["artifact_id"] for item in listed]
    assert genuine_id in ids  # the genuine seal is served
    assert tampered_id not in ids  # the tampered file is omitted, not shown

    assert client.get(f"/api/v1/forecasts/{genuine_id}").status_code == 200
    # The tampered file exists on disk but must never be served as a forecast.
    assert client.get(f"/api/v1/forecasts/{tampered_id}").status_code == 500


def test_list_survives_a_schema_broken_artifact(monkeypatch, tmp_path) -> None:
    """A schema-invalid file raises jsonschema.ValidationError (not a ValueError);
    the list endpoint must omit it, not crash on the whole request."""
    monkeypatch.delenv("GOLAVO_TOKEN", raising=False)
    ledger = tmp_path / "ledger"
    genuine_id = _seal_genuine(ledger)
    broken = json.loads((ledger / f"{genuine_id}.json").read_text(encoding="utf-8"))
    del broken["match"]  # required field -> ValidationError on load
    (ledger / "fa_schemabroken000000.json").write_bytes(canonical_bytes(broken) + b"\n")
    monkeypatch.setattr(server_main, "ARTIFACT_DIR", ledger)
    client = TestClient(server_main.app)

    resp = client.get("/api/v1/forecasts")
    assert resp.status_code == 200
    ids = [item["artifact_id"] for item in resp.json()]
    assert ids == [genuine_id]  # broken file omitted, genuine still served
    assert client.get("/api/v1/forecasts/fa_schemabroken000000").status_code == 500


# --- H3: platform-correct sidecar parent-watch --------------------------------

def test_pid_alive_true_for_self() -> None:
    assert sidecar._pid_alive(os.getpid()) is True


def test_pid_alive_false_for_a_reaped_child() -> None:
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    assert sidecar._pid_alive(proc.pid) is False


def test_pid_alive_uses_a_nonkilling_windows_probe(monkeypatch) -> None:
    """On Windows, _pid_alive must route to the OpenProcess probe and never call
    os.kill (which on Windows signals/terminates rather than probes)."""
    seen: dict[str, int] = {}

    def _fake_windows(pid: int) -> bool:
        seen["pid"] = pid
        return True

    def _forbidden_kill(*args, **kwargs):
        raise AssertionError("os.kill must never run on the Windows path")

    monkeypatch.setattr(sidecar.os, "name", "nt")
    monkeypatch.setattr(sidecar, "_pid_alive_windows", _fake_windows)
    monkeypatch.setattr(sidecar.os, "kill", _forbidden_kill)
    assert sidecar._pid_alive(4321) is True
    assert seen["pid"] == 4321


def test_orphaned_posix_uses_reparent_and_liveness(monkeypatch) -> None:
    monkeypatch.setattr(sidecar, "_pid_alive", lambda pid: True)
    assert sidecar._orphaned(100, 1, 999, posix=True) is True    # reparented to init
    assert sidecar._orphaned(100, 200, 999, posix=True) is True  # ppid changed
    assert sidecar._orphaned(100, 100, 999, posix=True) is False  # stable, parent alive
    monkeypatch.setattr(sidecar, "_pid_alive", lambda pid: False)
    assert sidecar._orphaned(100, 100, 999, posix=True) is True   # parent gone


def test_orphaned_windows_ignores_stale_ppid(monkeypatch) -> None:
    """Windows never reparents, so a changed/stale ppid must NOT be read as
    orphaning; only the parent-liveness probe decides — else the watcher either
    misses the orphan (false negative) or self-exits early (false positive)."""
    monkeypatch.setattr(sidecar, "_pid_alive", lambda pid: True)
    assert sidecar._orphaned(100, 1, 999, posix=False) is False   # alive -> stay
    assert sidecar._orphaned(100, 200, 999, posix=False) is False
    monkeypatch.setattr(sidecar, "_pid_alive", lambda pid: False)
    assert sidecar._orphaned(100, 100, 999, posix=False) is True  # dead -> exit
