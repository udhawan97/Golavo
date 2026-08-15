from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from golavo_core.season_outlook import (
    IMPORTANCE_VOICE_ID,
    certify_schedule,
    fixture_importance,
    season_outlook,
)
from golavo_core.standings import LEAGUE_RULES, LeagueRule
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads(
    (ROOT / "docs" / "contracts" / "season_outlook.schema.json").read_text(encoding="utf-8")
)


def _row(
    match_id: str,
    date: str,
    home: str,
    away: str,
    *,
    complete: bool,
    home_score: int | None = None,
    away_score: int | None = None,
) -> dict[str, object]:
    return {
        "match_id": match_id,
        "date": pd.Timestamp(date),
        "kickoff_utc": pd.Timestamp(date, tz="UTC"),
        "home_team": home,
        "away_team": away,
        "home_score": home_score,
        "away_score": away_score,
        "is_complete": complete,
        "neutral": False,
        "competition": "Test League",
        "source_id": "test-open-source",
        "source_kind": "club",
    }


def _synthetic_frame() -> pd.DataFrame:
    teams = ["A", "B", "C", "D"]
    rows: list[dict[str, object]] = []
    for cycle in range(5):
        for home in teams:
            for away in teams:
                if home == away:
                    continue
                index = len(rows)
                rows.append(
                    _row(
                        f"history-{index}",
                        f"202{cycle}-01-{index % 27 + 1:02d}",
                        home,
                        away,
                        complete=True,
                        home_score=(index + cycle) % 3,
                        away_score=(index + 1) % 2,
                    )
                )
    schedule_pairs = [(home, away) for home in teams for away in teams if home != away]
    for index, (home, away) in enumerate(schedule_pairs):
        complete = index < 4
        rows.append(
            _row(
                f"season-{index}",
                f"2026-08-{index + 1:02d}" if complete else f"2027-02-{index + 1:02d}",
                home,
                away,
                complete=complete,
                home_score=(index % 3) if complete else None,
                away_score=(index % 2) if complete else None,
            )
        )
    return pd.DataFrame(rows)


@pytest.fixture(autouse=True)
def compact_test_rule(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(
        LEAGUE_RULES,
        "test-league",
        LeagueRule(
            "test-league",
            "Test League",
            "test-2026.1",
            4,
            4,
            1,
            ("points", "goal_difference", "goals_for"),
        ),
    )


def test_schedule_certificate_rejects_missing_and_duplicate_pairs() -> None:
    frame = _synthetic_frame()
    season = frame.loc[frame["match_id"].astype(str).str.startswith("season-")].copy()
    valid = certify_schedule(season, expected_teams=4, as_of_utc="2026-09-01T00:00:00Z")
    assert valid["complete_fixture_list"] is True
    malformed = pd.concat([season.iloc[:-1], season.iloc[[0]]], ignore_index=True)
    invalid = certify_schedule(malformed, expected_teams=4, as_of_utc="2026-09-01T00:00:00Z")
    assert invalid["complete_fixture_list"] is False
    assert invalid["duplicate_ordered_pairs"] == 1


def test_seeded_simulation_is_deterministic_conservative_and_not_a_seal() -> None:
    frame = _synthetic_frame()
    first = season_outlook(
        frame,
        "test-league",
        as_of_utc="2026-09-01T00:00:00Z",
        season="2026-27",
        iterations=1_000,
        seed=42,
    )
    second = season_outlook(
        frame,
        "test-league",
        as_of_utc="2026-09-01T00:00:00Z",
        season="2026-27",
        iterations=1_000,
        seed=42,
    )
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert first["status"] == "available"
    assert first["ledger_status"] == "never_persisted_or_scored_as_a_seal"
    for voice in first["voices"]:
        assert voice["totals"] == pytest.approx({"title": 1.0, "top_four": 4.0, "relegation": 1.0})
        assert sum(row["display_percent"]["title"] for row in voice["teams"]) == 100.0
        assert sum(row["display_percent"]["top_four"] for row in voice["teams"]) == 400.0
    contract_payload = json.loads(json.dumps(first))
    contract_payload["provenance"]["index_sha256"] = "0" * 64
    Draft202012Validator(SCHEMA, format_checker=FormatChecker()).validate(contract_payload)


def test_conditional_result_is_hypothetical_deterministic_and_never_mutates_input() -> None:
    frame = _synthetic_frame()
    original = frame.copy(deep=True)
    kwargs = {
        "as_of_utc": "2026-09-01T00:00:00Z",
        "season": "2026-27",
        "iterations": 250,
        "seed": 17,
        "forced_results": [
            {"match_id": "season-4", "home_score": 3, "away_score": 1},
            {"match_id": "season-5", "home_score": 0, "away_score": 0},
        ],
    }

    first = season_outlook(frame, "test-league", **kwargs)
    second = season_outlook(frame, "test-league", **kwargs)

    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert first["scenario"] == {
        "hypothetical_only": True,
        "persisted": False,
        "model_input": False,
        "forced_results": [
            {
                "match_id": "season-4",
                "home_team": "B",
                "away_team": "C",
                "home_score": 3,
                "away_score": 1,
            },
            {
                "match_id": "season-5",
                "home_team": "B",
                "away_team": "D",
                "home_score": 0,
                "away_score": 0,
            },
        ],
    }
    assert "season-4" in {fixture["match_id"] for fixture in first["remaining_fixtures"]}
    pd.testing.assert_frame_equal(frame, original)


def test_scenario_rejects_a_completed_or_unknown_fixture() -> None:
    frame = _synthetic_frame()
    common = {
        "as_of_utc": "2026-09-01T00:00:00Z",
        "season": "2026-27",
        "iterations": 50,
    }
    with pytest.raises(ValueError, match="not an unplayed future match"):
        season_outlook(
            frame,
            "test-league",
            **common,
            forced_results=[{"match_id": "season-0", "home_score": 1, "away_score": 0}],
        )
    with pytest.raises(ValueError, match="not in this season"):
        season_outlook(
            frame,
            "test-league",
            **common,
            forced_results=[{"match_id": "unknown", "home_score": 1, "away_score": 0}],
        )
    with pytest.raises(ValueError, match="scores must be integers"):
        season_outlook(
            frame,
            "test-league",
            **common,
            forced_results=[{"match_id": "season-4", "home_score": 1.5, "away_score": 0}],
        )
    with pytest.raises(ValueError, match="between 0 and 20"):
        season_outlook(
            frame,
            "test-league",
            **common,
            forced_results=[{"match_id": "season-4", "home_score": 21, "away_score": 0}],
        )
    with pytest.raises(ValueError, match="non-empty and unique"):
        season_outlook(
            frame,
            "test-league",
            **common,
            forced_results=[
                {"match_id": "season-4", "home_score": 1, "away_score": 0},
                {"match_id": "season-4", "home_score": 0, "away_score": 1},
            ],
        )
    with pytest.raises(ValueError, match="at most 12"):
        season_outlook(
            frame,
            "test-league",
            **common,
            forced_results=[
                {"match_id": "season-4", "home_score": 1, "away_score": 0}
                for _ in range(13)
            ],
        )


def test_missing_current_schedule_and_past_result_gaps_fail_closed() -> None:
    frame = _synthetic_frame()
    missing = season_outlook(
        frame,
        "test-league",
        as_of_utc="2026-07-15T00:00:00Z",
        season="2027-28",
    )
    assert (missing["status"], missing["reason_code"], missing["voices"]) == (
        "blocked",
        "fixtures_not_published",
        [],
    )
    stale = season_outlook(
        frame,
        "test-league",
        as_of_utc="2027-04-01T00:00:00Z",
        season="2026-27",
    )
    assert stale["reason_code"] == "past_result_gaps"


def test_future_completed_training_poison_outside_target_season_is_ignored() -> None:
    frame = _synthetic_frame()
    baseline = season_outlook(
        frame,
        "test-league",
        as_of_utc="2026-09-01T00:00:00Z",
        season="2026-27",
        iterations=250,
        seed=7,
    )
    poison = pd.DataFrame(
        [
            _row(
                "future-poison",
                "2028-01-01",
                "A",
                "B",
                complete=True,
                home_score=99,
                away_score=0,
            )
        ]
    )
    poisoned = season_outlook(
        pd.concat([frame, poison], ignore_index=True),
        "test-league",
        as_of_utc="2026-09-01T00:00:00Z",
        season="2026-27",
        iterations=250,
        seed=7,
    )
    assert json.dumps(baseline, sort_keys=True) == json.dumps(poisoned, sort_keys=True)


def _six_iteration_branches() -> dict[str, object]:
    """Six iterations: home wins {0,4}, draws {1,3}, away wins {2,5}."""
    return {
        "home_scores": np.array([2, 1, 0, 1, 3, 0]),
        "away_scores": np.array([0, 1, 2, 1, 1, 3]),
        "home_team": "A",
        "away_team": "B",
        "home_flags": {
            # Title in both home wins, in neither away win -> swing 1.0
            "title": np.array([True, True, False, False, True, False]),
            # Top four in both home wins and in one away win -> swing 0.5
            "top_four": np.array([True, True, True, False, True, False]),
            "relegation": np.zeros(6, dtype=bool),
        },
        "away_flags": {
            # Away club: wins on {2,5}, loses on {0,4}. Title in one win -> swing 0.5
            "title": np.array([False, False, True, False, False, False]),
            "top_four": np.zeros(6, dtype=bool),
            # Relegated in one of its two losses, never in a win -> swing 0.5
            "relegation": np.array([False, False, False, False, True, False]),
        },
    }


def test_fixture_importance_swings_match_hand_computation() -> None:
    result = fixture_importance(**_six_iteration_branches(), min_branch_runs=2)

    assert result["status"] == "ok"
    assert result["coverage"] == {"home_wins": 2, "draws": 2, "away_wins": 2}
    home, away = result["clubs"]
    assert (home["team"], home["side"]) == ("A", "home")
    assert home["swings"] == pytest.approx({"title": 1.0, "top_four": 0.5, "relegation": 0.0})
    assert home["score"] == pytest.approx(1.0)
    assert (away["team"], away["side"]) == ("B", "away")
    assert away["swings"] == pytest.approx({"title": 0.5, "top_four": 0.0, "relegation": 0.5})
    assert away["score"] == pytest.approx(0.5)
    # Fixture importance is the larger of the two clubs, never a blend.
    assert result["score"] == pytest.approx(1.0)


def test_fixture_importance_abstains_below_the_branch_floor() -> None:
    result = fixture_importance(**_six_iteration_branches(), min_branch_runs=3)

    assert result["status"] == "insufficient_coverage"
    assert result["score"] is None
    # Coverage stays reported so the abstention is auditable.
    assert result["coverage"] == {"home_wins": 2, "draws": 2, "away_wins": 2}
    assert [club["swings"] for club in result["clubs"]] == [None, None]
    assert [club["score"] for club in result["clubs"]] == [None, None]


def test_season_outlook_reports_importance_and_expected_points() -> None:
    frame = _synthetic_frame()
    kwargs = {
        "as_of_utc": "2026-09-01T00:00:00Z",
        "season": "2026-27",
        "iterations": 1_000,
        "seed": 42,
    }

    first = season_outlook(frame, "test-league", **kwargs)
    second = season_outlook(frame, "test-league", **kwargs)

    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)

    fixtures = first["remaining_fixtures"]
    assert fixtures, "the synthetic season must leave fixtures to simulate"
    for fixture in fixtures:
        importance = fixture["importance"]
        assert importance["voice_id"] == IMPORTANCE_VOICE_ID
        coverage = importance["coverage"]
        assert sum(coverage.values()) == 1_000
        clubs = importance["clubs"]
        assert [club["team"] for club in clubs] == [fixture["home_team"], fixture["away_team"]]
        if importance["status"] == "ok":
            assert 0.0 <= importance["score"] <= 1.0
            assert importance["score"] == pytest.approx(max(club["score"] for club in clubs))
            for club in clubs:
                assert set(club["swings"]) == {"title", "top_four", "relegation"}
                assert all(0.0 <= value <= 1.0 for value in club["swings"].values())

    for voice in first["voices"]:
        assert all(row["expected_points"] >= 0.0 for row in voice["teams"])

    # Point mass is conserved: every fixture pays 3 points on a decision and 2 on
    # a draw, so the coverage counts and the expected points must agree.  Only the
    # importance voice's runs produced those counts — voices are never blended.
    ratings_voice = next(
        voice for voice in first["voices"] if voice["voice_id"] == IMPORTANCE_VOICE_ID
    )
    assert sum(row["expected_points"] for row in ratings_voice["teams"]) == pytest.approx(
        sum(row["points"] for row in first["current_table"])
        + sum(3 - fixture["importance"]["coverage"]["draws"] / 1_000 for fixture in fixtures),
        abs=1e-6,
    )

    contract_payload = json.loads(json.dumps(first))
    contract_payload["provenance"]["index_sha256"] = "0" * 64
    Draft202012Validator(SCHEMA, format_checker=FormatChecker()).validate(contract_payload)


def test_forced_fixture_has_no_importance_to_report() -> None:
    frame = _synthetic_frame()
    result = season_outlook(
        frame,
        "test-league",
        as_of_utc="2026-09-01T00:00:00Z",
        season="2026-27",
        iterations=1_000,
        seed=42,
        forced_results=[{"match_id": "season-4", "home_score": 3, "away_score": 1}],
    )

    forced = next(
        fixture for fixture in result["remaining_fixtures"] if fixture["match_id"] == "season-4"
    )
    # Its outcome is fixed in this scenario, so one branch is empty and it abstains.
    assert forced["importance"]["status"] == "insufficient_coverage"
    assert forced["importance"]["coverage"] == {"home_wins": 1_000, "draws": 0, "away_wins": 0}


def test_completed_result_after_cutoff_is_rejected_without_entering_the_table() -> None:
    frame = _synthetic_frame()
    target = frame["match_id"].eq("season-4")
    frame.loc[target, ["is_complete", "home_score", "away_score"]] = [True, 99, 0]
    result = season_outlook(
        frame,
        "test-league",
        as_of_utc="2026-09-01T00:00:00Z",
        season="2026-27",
    )
    assert result["reason_code"] == "future_result_leak"
    assert result["fixture_certificate"]["future_completed_results"] == 1
    assert all(row["played"] <= 4 for row in result["current_table"])
