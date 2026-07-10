from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from golavo_server.main import app

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_read_only_forecast_and_eval_routes(monkeypatch) -> None:
    samples = REPO_ROOT / "data/fixtures/sample_artifacts"
    summary = REPO_ROOT / "docs/handoff/eval_summary.json"
    monkeypatch.setenv("GOLAVO_ARTIFACT_DIR", str(samples))
    monkeypatch.setenv("GOLAVO_EVAL_SUMMARY", str(summary))
    client = TestClient(app)

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
    assert client.get("/api/v1/eval/summary").json() == json.loads(summary.read_text())


def test_health_remains_available() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
