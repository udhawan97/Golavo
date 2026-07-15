from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from golavo_core.season_outlook import certify_schedule, season_outlook
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
