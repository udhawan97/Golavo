from __future__ import annotations

import json

import pandas as pd
import pytest
from golavo_core.models.candidates import PoissonModel
from golavo_core.outlook import (
    OUTLOOK_RULE,
    enumerate_four_team_bracket,
    knockout_advance_probability,
    world_cup_2026_outlook,
)


def test_exact_bracket_conserves_probability_and_propagates_degenerate_paths() -> None:
    strengths = {"A": 4, "B": 3, "C": 2, "D": 1}

    def deterministic(home: str, away: str) -> float:
        return 1.0 if strengths[home] > strengths[away] else 0.0

    rows = enumerate_four_team_bracket(("A", "B"), ("C", "D"), advance=deterministic)
    by_team = {row["team"]: row for row in rows}
    assert by_team["A"]["champion"] == 1.0
    assert by_team["C"]["reach_final"] == 1.0
    assert by_team["B"]["third"] == 1.0
    assert sum(row["champion"] for row in rows) == pytest.approx(1.0)
    assert sum(row["third"] for row in rows) == pytest.approx(1.0)
    assert sum(row["reach_final"] for row in rows) == pytest.approx(2.0)


def test_knockout_rule_is_complementary_and_uses_shortened_goal_matrix() -> None:
    rows = pd.DataFrame(
        [
            {
                "date": pd.Timestamp("2025-01-01", tz="UTC"),
                "match_id": f"m_{index}",
                "home_team": "A" if index % 2 else "B",
                "away_team": "B" if index % 2 else "A",
                "home_score": 2 if index % 3 else 1,
                "away_score": 0 if index % 3 else 1,
                "neutral": True,
                "is_complete": True,
            }
            for index in range(20)
        ]
    )
    model = PoissonModel("dixon_coles").fit(rows, "2026-01-01T00:00:00Z")
    a = knockout_advance_probability(model, "A", "B")
    b = knockout_advance_probability(model, "B", "A")
    assert a + b == pytest.approx(1.0, abs=1e-9)
    shortened = model.predict_duration("A", "B", True, fraction=1 / 3)
    assert shortened.params["duration_fraction"] == pytest.approx(1 / 3)
    assert shortened.expected_goals is not None


def test_world_cup_outlook_is_deterministic_leak_safe_and_rule_stamped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    history = []
    teams = ("France", "Spain", "England", "Argentina")
    for index in range(80):
        home = teams[index % 4]
        away = teams[(index + 1) % 4]
        history.append(
            {
                "match_id": f"m_hist_{index:03d}",
                "date": pd.Timestamp("2025-01-01", tz="UTC") + pd.Timedelta(days=index),
                "kickoff_utc": pd.Timestamp("2025-01-01", tz="UTC")
                + pd.Timedelta(days=index),
                "home_team": home,
                "away_team": away,
                "home_score": index % 3,
                "away_score": (index + 1) % 2,
                "is_complete": True,
                "neutral": True,
                "competition": "Friendly",
                "source_id": "martj42-international-results",
                "source_kind": "international",
            }
        )
    semifinals = [
        {
            "match_id": "m_semi_1",
            "date": pd.Timestamp("2026-07-14", tz="UTC"),
            "kickoff_utc": pd.Timestamp("2026-07-14T19:00:00Z"),
            "home_team": "France",
            "away_team": "Spain",
            "home_score": None,
            "away_score": None,
            "is_complete": False,
            "neutral": True,
            "competition": "FIFA World Cup",
            "source_id": "martj42-international-results",
            "source_kind": "international",
        },
        {
            "match_id": "m_semi_2",
            "date": pd.Timestamp("2026-07-15", tz="UTC"),
            "kickoff_utc": pd.Timestamp("2026-07-15T19:00:00Z"),
            "home_team": "England",
            "away_team": "Argentina",
            "home_score": None,
            "away_score": None,
            "is_complete": False,
            "neutral": True,
            "competition": "FIFA World Cup",
            "source_id": "martj42-international-results",
            "source_kind": "international",
        },
    ]
    frame = pd.DataFrame([*history, *semifinals])
    first = world_cup_2026_outlook(frame, as_of_utc="2026-07-13T12:00:00Z")
    poisoned = pd.concat(
        [
            frame,
            pd.DataFrame(
                [
                    {
                        **history[0],
                        "match_id": "m_future_poison",
                        "date": pd.Timestamp("2026-08-01", tz="UTC"),
                        "kickoff_utc": pd.Timestamp("2026-08-01", tz="UTC"),
                        "home_score": 99,
                        "away_score": 0,
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    second = world_cup_2026_outlook(poisoned, as_of_utc="2026-07-13T12:00:00Z")
    assert first == second
    assert first["outlook_rule"] == OUTLOOK_RULE
    assert first["ledger_status"] == "never_persisted_or_scored_as_a_seal"
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    for voice in first["voices"]:
        assert voice["totals"]["champion"] == pytest.approx(1.0, abs=1e-8)
        assert voice["totals"]["third"] == pytest.approx(1.0, abs=1e-8)


def _played_bracket_frame(*, second_semifinal: tuple[int, int] | None = (1, 2)) -> pd.DataFrame:
    """Enough history to fit, plus both semifinals carrying their real results.

    ``second_semifinal=None`` leaves the later semifinal unscored, standing in for a
    snapshot whose upstream has not published the result yet.
    """
    teams = ("France", "Spain", "England", "Argentina")
    history = [
        {
            "match_id": f"m_hist_{index:03d}",
            "date": pd.Timestamp("2025-01-01", tz="UTC") + pd.Timedelta(days=index),
            "kickoff_utc": pd.Timestamp("2025-01-01", tz="UTC") + pd.Timedelta(days=index),
            "home_team": teams[index % 4],
            "away_team": teams[(index + 1) % 4],
            "home_score": index % 3,
            "away_score": (index + 1) % 2,
            "is_complete": True,
            "neutral": True,
            "competition": "Friendly",
            "source_id": "martj42-international-results",
            "source_kind": "international",
        }
        for index in range(80)
    ]
    semifinals = [
        {
            "match_id": "m_semi_1",
            "date": pd.Timestamp("2026-07-14", tz="UTC"),
            "kickoff_utc": pd.Timestamp("2026-07-14T19:00:00Z"),
            "home_team": "France",
            "away_team": "Spain",
            "home_score": 0,
            "away_score": 2,
            "is_complete": True,
            "neutral": True,
            "competition": "FIFA World Cup",
            "source_id": "martj42-international-results",
            "source_kind": "international",
        },
        {
            "match_id": "m_semi_2",
            "date": pd.Timestamp("2026-07-15", tz="UTC"),
            "kickoff_utc": pd.Timestamp("2026-07-15T19:00:00Z"),
            "home_team": "England",
            "away_team": "Argentina",
            "home_score": second_semifinal[0] if second_semifinal else None,
            "away_score": second_semifinal[1] if second_semifinal else None,
            "is_complete": second_semifinal is not None,
            "neutral": True,
            "competition": "FIFA World Cup",
            "source_id": "martj42-international-results",
            "source_kind": "international",
        },
    ]
    return pd.DataFrame([*history, *semifinals])


def test_semifinal_result_after_the_cutoff_never_pins_the_bracket() -> None:
    """A semifinal that has not kicked off at ``as_of`` stays a probability.

    Once the index carries real results, every past-cutoff query can see them.
    Reading one back would report a future result as settled fact.
    """
    outlook = world_cup_2026_outlook(_played_bracket_frame(), as_of_utc="2026-07-15T08:00:00Z")
    reported = {row["match_id"]: row["status"] for row in outlook["semifinals"]}
    assert reported["m_semi_1"] == "complete"
    assert reported["m_semi_2"] == "unresolved"

    for voice in outlook["voices"]:
        reach = {row["team"]: row["reach_final"] for row in voice["teams"]}
        assert reach["Spain"] == 1.0
        assert reach["France"] == 0.0
        for team in ("England", "Argentina"):
            assert 0.0 < reach[team] < 1.0, f"{voice['voice_id']} leaked the {team} semifinal"
        assert voice["totals"]["champion"] == pytest.approx(1.0, abs=1e-8)


def test_both_semifinals_played_before_the_cutoff_pin_the_finalists() -> None:
    outlook = world_cup_2026_outlook(_played_bracket_frame(), as_of_utc="2026-07-16T00:00:00Z")
    assert outlook["snapshot_status"] == "current_for_index"
    assert [row["status"] for row in outlook["semifinals"]] == ["complete", "complete"]

    for voice in outlook["voices"]:
        reach = {row["team"]: row["reach_final"] for row in voice["teams"]}
        assert reach == {"Spain": 1.0, "Argentina": 1.0, "France": 0.0, "England": 0.0}


def test_passed_kickoff_without_a_result_reports_a_stale_snapshot() -> None:
    """A kicked-off semifinal the snapshot cannot score is refresh-needed, not 50/50."""
    frame = _played_bracket_frame(second_semifinal=None)
    outlook = world_cup_2026_outlook(frame, as_of_utc="2026-07-16T00:00:00Z")
    assert outlook["snapshot_status"] == "result_refresh_needed"
    assert [row["status"] for row in outlook["semifinals"]] == ["complete", "unresolved"]
    assert "not a live result" in outlook["snapshot_note"]
