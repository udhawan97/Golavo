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


def test_current_domestic_season_outlook_runs_on_the_certified_schedule() -> None:
    """2026-27 is bundled and certifies, so the seeded outlook answers for real."""
    response = TestClient(server_main.app).get(
        "/api/v1/analytics/competitions/england-premier-league/season-outlook",
        params={"as_of_utc": "2026-08-20T08:00:00Z"},
    )
    assert response.status_code == 200
    body = response.json()
    Draft202012Validator(SCHEMA, format_checker=FormatChecker()).validate(body)
    assert body["status"] == "available"
    assert body["season"] == "2026-27"
    assert body["fixture_certificate"]["complete_fixture_list"] is True
    assert body["fixture_certificate"]["observed_matches"] == 380
    # Separate voices, never blended, and never a seal.
    assert [voice["voice_id"] for voice in body["voices"]] == [
        "elo_ordlogit",
        "dixon_coles",
        "equal-chance-baseline",
    ]
    assert body["iterations"] == 10_000
    assert body["ledger_status"] == "never_persisted_or_scored_as_a_seal"
    for voice in body["voices"]:
        assert len(voice["teams"]) == 20
        # Exactly one side wins the league in every simulated season.
        assert sum(team["title"] for team in voice["teams"]) == pytest.approx(1.0, abs=1e-6)
        assert sum(team["top_four"] for team in voice["teams"]) == pytest.approx(4.0, abs=1e-6)
        assert sum(team["relegation"] for team in voice["teams"]) == pytest.approx(3.0, abs=1e-6)


def test_a_season_with_no_published_fixtures_still_fails_closed() -> None:
    """The certificate is enforced per request: an unpublished season gets no numbers."""
    response = TestClient(server_main.app).get(
        "/api/v1/analytics/competitions/england-premier-league/season-outlook",
        params={"as_of_utc": "2027-08-15T08:00:00Z"},
    )
    assert response.status_code == 200
    body = response.json()
    Draft202012Validator(SCHEMA, format_checker=FormatChecker()).validate(body)
    assert body["status"] == "blocked"
    assert body["season"] == "2027-28"
    assert body["reason_code"] == "fixtures_not_published"
    assert body["voices"] == []
    assert body["fixture_certificate"]["observed_matches"] == 0


def test_conditional_season_scenario_is_ephemeral_and_contract_valid() -> None:
    client = TestClient(server_main.app)
    path = "/api/v1/analytics/competitions/england-premier-league"
    params = {"as_of_utc": "2026-08-20T08:00:00Z"}
    base = client.get(f"{path}/season-outlook", params=params).json()
    fixture = base["remaining_fixtures"][0]

    response = client.post(
        f"{path}/season-scenario",
        params=params,
        json={
            "forced_results": [
                {"match_id": fixture["match_id"], "home_score": 2, "away_score": 0}
            ]
        },
    )

    assert response.status_code == 200
    scenario = response.json()
    Draft202012Validator(SCHEMA, format_checker=FormatChecker()).validate(scenario)
    assert scenario["scenario"]["hypothetical_only"] is True
    assert scenario["scenario"]["persisted"] is False
    assert scenario["scenario"]["model_input"] is False
    assert base["scenario"] is None
    # Re-reading the canonical outlook proves the scenario was not cached into it.
    assert client.get(f"{path}/season-outlook", params=params).json()["scenario"] is None


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
