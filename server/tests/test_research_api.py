from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from golavo_server import main as server_main
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads(
    (ROOT / "docs/contracts/research_team_analytics.schema.json").read_text(encoding="utf-8")
)


def test_team_research_is_scoped_to_one_competition_and_era() -> None:
    response = TestClient(server_main.app).get(
        "/api/v1/research/competitions/england-premier-league"
    )
    assert response.status_code == 200
    body = response.json()
    Draft202012Validator(SCHEMA).validate(body)
    assert body["competition_id"] == "england-premier-league"
    assert body["era"] == "2017/18"
    assert body["team_scope"] == "team_aggregate_only"
    assert body["coverage"] == {"matches": 380, "events": 643150, "teams": 20}
    assert all("player" not in key for team in body["teams"] for key in team)


def test_uncovered_competition_is_an_explicit_404() -> None:
    response = TestClient(server_main.app).get(
        "/api/v1/research/competitions/uefa-champions-league"
    )
    assert response.status_code == 404
    assert "no historical research pack" in response.json()["detail"]


def test_bundled_artifacts_cover_the_published_corpus_totals() -> None:
    pack = ROOT / "packs/pappalardo-wyscout-research-2019"
    artifacts = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in pack.glob("*.json")
        if path.name != "manifest.json"
    ]
    assert len(artifacts) == 7
    assert sum(item["coverage"]["matches"] for item in artifacts) == 1941
    assert sum(item["coverage"]["events"] for item in artifacts) == 3251294
    for artifact in artifacts:
        Draft202012Validator(SCHEMA).validate(artifact)
