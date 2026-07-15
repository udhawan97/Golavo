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
