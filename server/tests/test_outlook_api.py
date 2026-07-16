from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from golavo_server import main as server_main
from golavo_server import matches, outlook
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads(
    (ROOT / "docs" / "contracts" / "tournament_outlook.schema.json").read_text(
        encoding="utf-8"
    )
)


@pytest.fixture(autouse=True)
def _reset_shared_index_and_outlook_caches():
    matches.reset_cache()
    yield
    matches.reset_cache()


def test_world_cup_outlook_endpoint_validates_against_contract() -> None:
    body = TestClient(server_main.app).get(
        "/api/v1/tournaments/worldcup-2026/outlook",
        params={"as_of_utc": "2026-07-15T08:00:00Z"},
    ).json()
    Draft202012Validator(SCHEMA, format_checker=FormatChecker()).validate(body)
    assert body["status"] == "available"
    # The committed snapshot carries both semifinal results, so nothing this cutoff can
    # see is missing one. The later semifinal stays unresolved here because its kickoff
    # is still ahead at 08:00 — see core/tests/test_outlook.py for both cutoff branches.
    assert body["snapshot_status"] == "current_for_index"
    assert [row["status"] for row in body["semifinals"]] == ["complete", "unresolved"]
    assert [voice["voice_id"] for voice in body["voices"]] == [
        "elo_ordlogit",
        "dixon_coles",
        "equal-chance-baseline",
    ]
    assert body["provenance"]["fixture_source_id"] == "openfootball-worldcup-json"


def test_world_cup_outlook_unavailable_is_a_typed_200(monkeypatch) -> None:
    outlook.reset_cache()
    monkeypatch.setattr(
        outlook,
        "world_cup_2026",
        lambda **_: {
            "schema_version": "0.1.0",
            "status": "unavailable",
            "label": "Tournament outlook — not a seal.",
            "tournament_id": "worldcup-2026",
            "tournament_name": "2026 FIFA World Cup",
            "as_of_utc": "2026-07-15T08:00:00Z",
            "reason": "semifinals unresolved",
            "voices": [],
            "semifinals": [],
            "provenance": {"index_sha256": "0" * 64},
        },
    )
    response = TestClient(server_main.app).get("/api/v1/tournaments/worldcup-2026/outlook")
    assert response.status_code == 200
    assert response.json()["status"] == "unavailable"
