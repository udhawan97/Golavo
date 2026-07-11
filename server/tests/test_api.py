from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from golavo_server import main as server_main

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_read_only_forecast_and_eval_routes(monkeypatch) -> None:
    samples = REPO_ROOT / "data/fixtures/sample_artifacts"
    summary = REPO_ROOT / "docs/handoff/eval_summary.json"
    monkeypatch.setattr(server_main, "ARTIFACT_DIR", samples)
    monkeypatch.setattr(server_main, "EVAL_SUMMARY_PATHS", (summary,))
    client = TestClient(server_main.app)

    response = client.get(
        "/api/v1/forecasts", headers={"Origin": "http://127.0.0.1:5173"}
    )
    assert response.status_code == 200
    forecasts = response.json()
    assert len(forecasts) == 8
    created = [item["provenance"]["created_at_utc"] for item in forecasts]
    assert created == sorted(created, reverse=True)
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"

    artifact_id = forecasts[0]["artifact_id"]
    assert client.get(f"/api/v1/forecasts/{artifact_id}").json()["artifact_id"] == artifact_id
    assert client.get("/api/v1/forecasts/fa_missing00").status_code == 404
    combined = client.get("/api/v1/eval/summary").json()
    assert combined["folds"] == json.loads(summary.read_text())["folds"]
    assert combined["primary_metric"] == "log_loss"


def test_health_remains_available() -> None:
    response = TestClient(server_main.app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_eval_summary_merges_all_league_folds() -> None:
    """The default summary paths are the six committed evaluation files; the
    endpoint must serve their folds concatenated, in declared order."""
    expected_folds: list[str] = []
    for path in server_main.EVAL_SUMMARY_PATHS:
        assert path.is_file(), f"missing committed summary: {path}"
        expected_folds.extend(
            fold["fold_id"] for fold in json.loads(path.read_text())["folds"]
        )
    combined = TestClient(server_main.app).get("/api/v1/eval/summary").json()
    assert [fold["fold_id"] for fold in combined["folds"]] == expected_folds
    competitions = {fold["competition"] for fold in combined["folds"]}
    assert {
        "English Premier League", "La Liga", "Bundesliga", "Serie A", "Ligue 1",
    } <= competitions
    assert len(combined["sources"]) == len(server_main.EVAL_SUMMARY_PATHS)


def test_calibration_route_recomputes_from_the_ledger(monkeypatch, tmp_path) -> None:
    from golavo_core.artifacts import score_forecast, seal_forecast

    ledger = tmp_path / "ledger"
    sealed = seal_forecast(
        pack_dir=REPO_ROOT / "packs/martj42-internationals-273c731492df",
        output_dir=ledger,
        date="2026-07-09",
        home_team="France",
        away_team="Morocco",
        as_of_utc="2026-07-08T00:00:00Z",
    )
    score_forecast(
        artifact_path=sealed,
        newer_pack_dir=REPO_ROOT / "packs/martj42-internationals",
        output_dir=ledger,
    )
    monkeypatch.setattr(server_main, "ARTIFACT_DIR", ledger)
    client = TestClient(server_main.app)

    body = client.get("/api/v1/calibration").json()
    assert body["schema_version"] == "0.2.0"
    assert body["primary_metric"] == "log_loss"
    assert body["counts"] == {
        "sealed": 1,
        "abstained": 0,
        "scored": 1,
        "voided": 0,
        "pending": 0,
    }
    assert body["running"]["n_scored"] == 1
    chain = body["chains"][0]
    assert chain["match"]["home_team"] == "France"
    assert chain["resolution"]["status"] == "scored"
    assert chain["resolution"]["actual"] == {
        "home_goals": 2,
        "away_goals": 0,
        "outcome": "home",
    }


def test_calibration_route_is_honest_about_an_empty_ledger(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(server_main, "ARTIFACT_DIR", tmp_path / "empty")
    body = TestClient(server_main.app).get("/api/v1/calibration").json()
    assert body["counts"]["sealed"] == 0
    assert body["running"] is None
    assert body["chains"] == []
