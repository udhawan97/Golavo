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
    assert before["strength_trends"]["status"] == "available"
    assert all(
        team["current"]["sample_matches"] >= 8
        for team in before["strength_trends"]["teams"]
    )
    assert before["rest_congestion"]["coverage_note"].startswith("Counts include only")
    assert before["schedule_difficulty"]["status"] == "blocked"


def test_competition_analytics_rejects_unknown_identity() -> None:
    with pytest.raises(ValueError, match="unknown competition_id"):
        competition_analytics(_index_frame(), "premier-ish", as_of_utc="2025-04-15Z")


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
