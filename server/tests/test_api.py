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


def test_fresh_install_serves_sample_forecasts_from_the_empty_ledger(monkeypatch, tmp_path) -> None:
    # A fresh desktop install has an empty writable ledger. Rather than an empty
    # shell, the forecast surface falls back to the bundled synthetic samples so
    # the user sees how Golavo works. (Each sample carries its own synthetic
    # provenance in-app.)
    empty_ledger = tmp_path / "ledger"
    empty_ledger.mkdir()
    monkeypatch.setattr(server_main, "ARTIFACT_DIR", empty_ledger)
    client = TestClient(server_main.app)

    forecasts = client.get("/api/v1/forecasts").json()
    assert len(forecasts) == 8  # the bundled sample fixtures
    one = forecasts[0]["artifact_id"]
    assert client.get(f"/api/v1/forecasts/{one}").json()["artifact_id"] == one

    # But the FORWARD calibration must stay honest — samples never count.
    calib = client.get("/api/v1/calibration").json()
    assert calib.get("count", 0) == 0


def test_real_ledger_takes_precedence_over_the_samples(monkeypatch, tmp_path) -> None:
    # Once the user has a real sealed forecast, the samples give way entirely.
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    samples = REPO_ROOT / "data/fixtures/sample_artifacts"
    real = next(samples.glob("fa_*.json"))
    (ledger / real.name).write_text(real.read_text(), encoding="utf-8")
    monkeypatch.setattr(server_main, "ARTIFACT_DIR", ledger)
    client = TestClient(server_main.app)

    forecasts = client.get("/api/v1/forecasts").json()
    assert len(forecasts) == 1  # only the real ledger, not the 8 samples


def test_a_lone_corrupt_seal_does_not_blank_the_app(monkeypatch, tmp_path) -> None:
    # A crash could leave a single truncated fa_*.json. That must NOT switch us
    # off the samples into a blank Matchday — the source gate ignores unparseable
    # files, so we keep serving the samples.
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    (ledger / "fa_truncated.json").write_text("{ not valid json", encoding="utf-8")
    monkeypatch.setattr(server_main, "ARTIFACT_DIR", ledger)
    client = TestClient(server_main.app)

    assert len(client.get("/api/v1/forecasts").json()) == 8  # still the samples


def test_meta_signals_sample_vs_ledger_mode(monkeypatch, tmp_path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setattr(server_main, "ARTIFACT_DIR", empty)
    client = TestClient(server_main.app)
    assert client.get("/api/v1/meta").json()["forecast_source"] == "sample"

    samples = REPO_ROOT / "data/fixtures/sample_artifacts"
    real = next(samples.glob("fa_*.json"))
    (empty / real.name).write_text(real.read_text(), encoding="utf-8")
    assert client.get("/api/v1/meta").json()["forecast_source"] == "ledger"


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
