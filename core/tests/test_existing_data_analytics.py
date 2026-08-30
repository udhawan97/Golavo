from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from golavo_core.analytics import competition_analytics
from golavo_core.evaluation import _build_report_cards
from golavo_core.models import FAMILIES


def _index_frame() -> pd.DataFrame:
    teams = ("Alpha", "Bravo", "Charlie", "Delta")
    rows: list[dict[str, object]] = []
    for index in range(24):
        home = teams[index % len(teams)]
        away = teams[(index + 1 + index // len(teams)) % len(teams)]
        if home == away:
            away = teams[(teams.index(home) + 1) % len(teams)]
        date = pd.Timestamp("2025-01-01", tz="UTC") + pd.Timedelta(days=index * 4)
        rows.append(
            {
                "match_id": f"m_{index:02d}",
                "date": date.tz_localize(None),
                "kickoff_utc": date,
                "home_team": home,
                "away_team": away,
                "home_score": index % 4,
                "away_score": (index + 1) % 3,
                "is_complete": True,
                "competition": "English Premier League",
                "neutral": False,
                "source_id": "openfootball-football-json",
            }
        )
    return pd.DataFrame(rows)


def _current_season_frame() -> pd.DataFrame:
    rows = [
        ("m_1", "2026-08-01T15:00:00Z", "Alpha", "Bravo", 2, 1, True),
        ("m_2", "2026-08-05T15:00:00Z", "Charlie", "Alpha", 0, 0, True),
        ("m_3", "2026-08-10T15:00:00Z", "Bravo", "Charlie", 3, 0, True),
        # A past-dated unresolved row is a source gap, not a future fixture.
        ("m_gap", "2026-08-12T15:00:00Z", "Charlie", "Bravo", None, None, False),
        ("m_future", "2026-09-01T15:00:00Z", "Alpha", "Bravo", None, None, False),
    ]
    return pd.DataFrame([
        {
            "match_id": match_id,
            "date": pd.Timestamp(kickoff).tz_localize(None),
            "kickoff_utc": pd.Timestamp(kickoff),
            "home_team": home,
            "away_team": away,
            "home_score": home_score,
            "away_score": away_score,
            "is_complete": complete,
            "competition": "English Premier League",
            "neutral": False,
            "source_id": "openfootball-test",
            "identity_source_id": "identity-test",
            "result_source_id": "result-test" if complete else None,
            "kickoff_source_id": "kickoff-test",
            "training_source_id": "result-test" if complete else None,
        }
        for match_id, kickoff, home, away, home_score, away_score, complete in rows
    ])


def test_competition_analytics_is_cutoff_safe_and_scoped() -> None:
    frame = _index_frame()
    cutoff = "2025-04-15T00:00:00Z"
    before = competition_analytics(frame, "england-premier-league", as_of_utc=cutoff)

    future = frame.iloc[-1].copy()
    future["match_id"] = "m_future"
    future["date"] = pd.Timestamp("2030-01-01")
    future["kickoff_utc"] = pd.Timestamp("2030-01-01", tz="UTC")
    future["home_team"] = "Future FC"
    after = competition_analytics(
        pd.concat([frame, pd.DataFrame([future])], ignore_index=True),
        "england-premier-league",
        as_of_utc=cutoff,
    )

    assert after == before
    assert before["scope"]["strength_comparison"] == "this_competition_only"
    assert before["scope"]["model_input"] is False
    pulse = before["current_season"]
    assert pulse["season"] == "2024-25"
    assert pulse["matches_played"] == len(frame)
    assert pulse["goals"] == int(frame["home_score"].sum() + frame["away_score"].sum())
    assert pulse["home_wins"] + pulse["draws"] + pulse["away_wins"] == len(frame)
    assert pulse["teams"][0]["recent_form"]
    assert all(len(team["recent_form"]) <= 5 for team in pulse["teams"])
    assert before["strength_trends"]["status"] == "available"
    assert all(
        team["current"]["sample_matches"] >= 8 for team in before["strength_trends"]["teams"]
    )
    assert before["rest_congestion"]["coverage_note"].startswith("Counts include only")
    assert before["schedule_difficulty"]["status"] == "blocked"


def test_competition_analytics_rejects_unknown_identity() -> None:
    with pytest.raises(ValueError, match="unknown competition_id"):
        competition_analytics(_index_frame(), "premier-ish", as_of_utc="2025-04-15Z")


def test_current_season_pulse_has_exact_rates_form_provenance_and_gap_counts() -> None:
    value = competition_analytics(
        _current_season_frame(),
        "england-premier-league",
        as_of_utc="2026-08-20T00:00:00Z",
    )["current_season"]

    assert value == {
        "status": "available",
        "reason": None,
        "season": "2026-27",
        "data_through_utc": "2026-08-10T15:00:00Z",
        "fixture_list_complete": False,
        "observed_matches": 5,
        "matches_played": 3,
        "expected_matches": 380,
        "matches_remaining": 1,
        "past_result_gaps": 1,
        "goals": 6,
        "goals_per_match": 2.0,
        "home_wins": 2,
        "draws": 1,
        "away_wins": 0,
        "home_win_rate": 0.667,
        "draw_rate": 0.333,
        "away_win_rate": 0.0,
        "both_teams_scored": 1,
        "both_teams_scored_rate": 0.333,
        "over_2_5": 2,
        "over_2_5_rate": 0.667,
        "source_ids": [
            "identity-test", "kickoff-test", "openfootball-test", "result-test",
        ],
        "teams": [
            {
                "team": "Alpha", "played": 2, "won": 1, "drawn": 1, "lost": 0,
                "goals_for": 2, "goals_against": 1, "clean_sheets": 1,
                "both_teams_scored": 1, "recent_form": ["W", "D"],
                "points_per_game": 2.0, "goals_for_per_match": 1.0,
                "goals_against_per_match": 0.5,
            },
            {
                "team": "Bravo", "played": 2, "won": 1, "drawn": 0, "lost": 1,
                "goals_for": 4, "goals_against": 2, "clean_sheets": 1,
                "both_teams_scored": 1, "recent_form": ["L", "W"],
                "points_per_game": 1.5, "goals_for_per_match": 2.0,
                "goals_against_per_match": 1.0,
            },
            {
                "team": "Charlie", "played": 2, "won": 0, "drawn": 1, "lost": 1,
                "goals_for": 0, "goals_against": 3, "clean_sheets": 1,
                "both_teams_scored": 0, "recent_form": ["D", "L"],
                "points_per_game": 0.5, "goals_for_per_match": 0.0,
                "goals_against_per_match": 1.5,
            },
        ],
    }


def test_current_season_pulse_zero_played_stays_zero_and_counts_only_future() -> None:
    frame = _current_season_frame().loc[lambda rows: rows["match_id"].eq("m_future")]
    value = competition_analytics(
        frame,
        "england-premier-league",
        as_of_utc="2026-08-20T00:00:00Z",
    )["current_season"]

    assert value["matches_played"] == 0
    assert value["matches_remaining"] == 1
    assert value["past_result_gaps"] == 0
    assert value["goals_per_match"] == 0.0
    assert value["home_win_rate"] == 0.0
    assert value["teams"] == [
        {
            "team": "Alpha", "played": 0, "won": 0, "drawn": 0, "lost": 0,
            "goals_for": 0, "goals_against": 0, "clean_sheets": 0,
            "both_teams_scored": 0, "recent_form": [], "points_per_game": 0.0,
            "goals_for_per_match": 0.0, "goals_against_per_match": 0.0,
        },
        {
            "team": "Bravo", "played": 0, "won": 0, "drawn": 0, "lost": 0,
            "goals_for": 0, "goals_against": 0, "clean_sheets": 0,
            "both_teams_scored": 0, "recent_form": [], "points_per_game": 0.0,
            "goals_for_per_match": 0.0, "goals_against_per_match": 0.0,
        },
    ]


def test_report_cards_use_match_weighting_and_seeded_bootstrap() -> None:
    folds: list[dict[str, object]] = []
    losses: list[dict[str, object]] = []
    # One distinct synthetic loss per family; strict=True is the point — it fails
    # loudly when the registry grows so a new family cannot skip this card.
    factors = dict(zip(FAMILIES, (1.0, 0.8, 0.9, 0.7, 1.1, 0.75), strict=True))
    for fold_id, n_matches in (("TEST-A", 50), ("TEST-B", 100)):
        models = [
            {
                "family": family,
                "log_loss": factor,
                "brier": factor / 2,
                "ece": factor / 10,
                "rps": factor / 3,
            }
            for family, factor in factors.items()
        ]
        folds.append(
            {
                "fold_id": fold_id,
                "competition": "Test League",
                "window_start": "2024-01-01",
                "window_end": "2024-12-31",
                "n_matches": n_matches,
                "models": models,
            }
        )
        losses.append(
            {
                "fold_id": fold_id,
                "competition": "Test League",
                "families": {
                    family: np.full(n_matches, factor, dtype=float)
                    for family, factor in factors.items()
                },
            }
        )

    first = _build_report_cards(folds, losses)
    second = _build_report_cards(folds, losses)
    assert first == second
    card = first[0]
    elo = next(model for model in card["models"] if model["family"] == "elo_ordlogit")
    assert elo["n_matches"] == 150
    assert elo["skill_score"] == pytest.approx(0.2)
    assert elo["skill_ci_95"] == pytest.approx([0.2, 0.2])
    assert elo["sample_status"] == "available"
    assert card["bootstrap"]["replicates"] == 2000
