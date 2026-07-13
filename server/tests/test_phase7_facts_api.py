"""Phase 7 — the read-only facts endpoint and the notebook → AI fold.

The endpoint serves a precomputed notebook next to an artifact; it never touches
a pack at request time and never fabricates facts when none were computed.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from golavo_core.artifacts import seal_forecast
from golavo_core.cli import _write_notebook
from golavo_server import main as server_main

REPO_ROOT = Path(__file__).resolve().parents[2]
T0_PACK = REPO_ROOT / "packs/martj42-internationals-273c731492df"


def _seal(ledger: Path) -> str:
    path = seal_forecast(
        pack_dir=T0_PACK,
        output_dir=ledger,
        date="2026-07-09",
        home_team="France",
        away_team="Morocco",
        as_of_utc="2026-07-08T00:00:00Z",
    )
    return path.stem


def test_facts_endpoint_serves_a_precomputed_notebook(monkeypatch, tmp_path) -> None:
    ledger = tmp_path / "ledger"
    artifact_id = _seal(ledger)
    _write_notebook(ledger / f"{artifact_id}.json", T0_PACK, None)  # -> ledger/notebooks/

    monkeypatch.setattr(server_main, "ARTIFACT_DIR", ledger)
    client = TestClient(server_main.app)

    body = client.get(f"/api/v1/forecasts/{artifact_id}/facts").json()
    assert body["available"] is True
    notebook = body["notebook"]
    assert notebook["facts"], "expected facts for this fixture"
    assert notebook["family_size"] >= 1
    labels = {fact["label"] for fact in notebook["facts"]}
    assert labels <= {"predictive", "context", "coincidence"}

    # The notebook file lives in a subdir and must NOT leak into the artifact list.
    listed = client.get("/api/v1/forecasts").json()
    assert len(listed) == 1 and listed[0]["artifact_id"] == artifact_id


def test_facts_endpoint_is_honest_when_no_notebook_exists(monkeypatch, tmp_path) -> None:
    ledger = tmp_path / "ledger"
    artifact_id = _seal(ledger)  # no notebook written
    monkeypatch.setattr(server_main, "ARTIFACT_DIR", ledger)
    client = TestClient(server_main.app)

    body = client.get(f"/api/v1/forecasts/{artifact_id}/facts").json()
    assert body == {"artifact_id": artifact_id, "available": False, "notebook": None}


def test_facts_endpoint_404_for_unknown_artifact(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(server_main, "ARTIFACT_DIR", tmp_path / "empty")
    client = TestClient(server_main.app)
    assert client.get("/api/v1/forecasts/fa_missing00/facts").status_code == 404


def test_corrupt_notebook_does_not_500_the_narrative_route(monkeypatch, tmp_path) -> None:
    # The notebook sidecar is not integrity-verified. A truncated/corrupt file
    # (partial write, hand-edit, older schema after an update) must fail closed:
    # the route still returns a normal envelope, treating it as no notebook.
    ledger = tmp_path / "ledger"
    artifact_id = _seal(ledger)
    notebook_path = ledger / "notebooks" / f"{artifact_id}.json"
    notebook_path.parent.mkdir(parents=True, exist_ok=True)
    notebook_path.write_text('{"facts": [ {"label": "context"', encoding="utf-8")  # truncated JSON

    monkeypatch.setattr(server_main, "ARTIFACT_DIR", ledger)
    client = TestClient(server_main.app)

    res = client.post(f"/api/v1/forecasts/{artifact_id}/narrative", json={})
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "disabled"  # provider off, but the bundle still built
    number_ids = {number["id"] for number in body["numbers"]}
    assert {"prob_home", "prob_draw", "prob_away"} <= number_ids  # engine numbers intact
    assert not any(nid.startswith("nb_") for nid in number_ids)  # corrupt notebook skipped


def test_narrative_folds_notebook_numbers_into_the_whitelist(monkeypatch, tmp_path) -> None:
    ledger = tmp_path / "ledger"
    artifact_id = _seal(ledger)
    _write_notebook(ledger / f"{artifact_id}.json", T0_PACK, None)

    monkeypatch.setattr(server_main, "ARTIFACT_DIR", ledger)
    client = TestClient(server_main.app)

    # Provider defaults to off: no model is called, but the bundle (with folded
    # notebook numbers) is still built and its whitelist is returned.
    body = client.post(f"/api/v1/forecasts/{artifact_id}/narrative", json={}).json()
    number_ids = {number["id"] for number in body["numbers"]}
    assert any(nid.startswith("nb_") for nid in number_ids), "notebook numbers must be folded"
    assert {"prob_home", "prob_draw", "prob_away"} <= number_ids  # engine numbers preserved
