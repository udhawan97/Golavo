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
    (ROOT / "docs" / "contracts" / "season_outlook.schema.json").read_text(encoding="utf-8")
)


@pytest.fixture(autouse=True)
def _reset_shared_index_and_outlook_caches():
    """Each API scenario starts on the committed index, not another test's frame."""
    matches.reset_cache()
    yield
    matches.reset_cache()


def test_current_domestic_season_outlook_is_an_honest_typed_block() -> None:
    response = TestClient(server_main.app).get(
        "/api/v1/analytics/competitions/england-premier-league/season-outlook",
        params={"as_of_utc": "2026-07-15T08:00:00Z"},
    )
    assert response.status_code == 200
    body = response.json()
    Draft202012Validator(SCHEMA, format_checker=FormatChecker()).validate(body)
    assert body["status"] == "blocked"
    assert body["season"] == "2026-27"
    assert body["reason_code"] == "fixtures_not_published"
    assert body["voices"] == []
    assert body["fixture_certificate"]["observed_matches"] == 0


def test_unsupported_competition_does_not_fake_a_league_simulation() -> None:
    response = TestClient(server_main.app).get(
        "/api/v1/analytics/competitions/uefa-champions-league/season-outlook",
        params={"as_of_utc": "2026-07-15T08:00:00Z"},
    )
    assert response.status_code == 404
    assert "no verified standings rule" in response.json()["detail"]


def test_incomplete_historical_capture_is_a_result_gap_not_a_final_table() -> None:
    response = TestClient(server_main.app).get(
        "/api/v1/analytics/competitions/spain-la-liga/season-outlook",
        params={"as_of_utc": "2026-07-15T08:00:00Z", "season": "2024-25"},
    )
    body = response.json()
    Draft202012Validator(SCHEMA, format_checker=FormatChecker()).validate(body)
    assert body["reason_code"] == "past_result_gaps"
    assert body["fixture_certificate"]["past_result_gaps"] == 10
    assert {row["played"] for row in body["current_table"]} == {37}


def test_outlook_cache_changes_with_index_fingerprint(monkeypatch) -> None:
    from golavo_core import season_outlook as core_season

    state = {"fingerprint": "a" * 64, "marker": "first"}
    frame = object()
    monkeypatch.setattr(
        matches,
        "index_snapshot",
        lambda: matches.IndexSnapshot(frame, state["fingerprint"], 1),
    )
    monkeypatch.setattr(matches, "snapshot_is_current", lambda snapshot: True)
    monkeypatch.setattr(
        matches,
        "apply_if_snapshot_current",
        lambda snapshot, operation: (operation() or True),
    )
    monkeypatch.setattr(
        core_season,
        "season_outlook",
        lambda *_args, **_kwargs: {
            "marker": state["marker"],
            "provenance": {},
        },
    )
    first = outlook.season("england-premier-league", as_of_utc="2026-07-15T08:00:00Z")
    state.update(fingerprint="b" * 64, marker="second")
    second = outlook.season("england-premier-league", as_of_utc="2026-07-15T08:00:00Z")
    assert (first["marker"], second["marker"]) == ("first", "second")
