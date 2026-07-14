"""Club half-time facts use only recorded, as-of-scoped history."""

from __future__ import annotations

import pandas as pd
from golavo_core.facts import events
from golavo_core.facts._history import TemplateContext, team_perspective
from golavo_core.facts.guardrails import assert_number_discipline, build_fact
from golavo_core.facts.registry import REGISTRY


def _matches() -> pd.DataFrame:
    rows = []
    for i in range(12):
        rows.append(
            {
                "date": pd.Timestamp("2025-01-01") + pd.Timedelta(days=i * 7),
                "kickoff_utc": pd.Timestamp("2025-01-01", tz="UTC") + pd.Timedelta(days=i * 7),
                "home_team": "Aland",
                "away_team": f"Rival {i}",
                "home_score": 2 if i < 4 else (1 if i < 7 else 3),
                "away_score": 1 if i < 7 else 2,
                "ht_home_score": 0 if i < 7 else 2,
                "ht_away_score": 1 if i < 7 else 0,
                "neutral": False,
                "tournament": "Example League",
            }
        )
    frame = pd.DataFrame(rows)
    score_columns = ["home_score", "away_score", "ht_home_score", "ht_away_score"]
    frame[score_columns] = frame[score_columns].astype("Int16")
    return frame


def _ctx(matches: pd.DataFrame | None = None) -> TemplateContext:
    return TemplateContext(
        matches=_matches() if matches is None else matches,
        home_team="Aland",
        away_team="Borda",
        competition="Example League",
        neutral=False,
        as_of=pd.Timestamp("2025-12-01", tz="UTC"),
        kickoff=pd.Timestamp("2025-12-02", tz="UTC"),
        source_ids=("test-source",),
    )


def _fact(candidate, template_id: str) -> dict:
    template = next(t for t in REGISTRY if t.id == template_id)
    fact, _ = build_fact(candidate, template, ("test-source",), _ctx().as_of)
    assert_number_discipline(fact)
    return fact


def test_team_perspective_exposes_nullable_oriented_ht_scores() -> None:
    perspective = team_perspective(_matches(), "Aland")
    assert perspective.loc[0, "ht_gf"] == 0
    assert perspective.loc[0, "ht_ga"] == 1
    assert str(perspective["ht_gf"].dtype) == "Int16"

    without_ht = _matches().drop(columns=["ht_home_score", "ht_away_score"])
    missing = team_perspective(without_ht, "Aland")
    assert missing["ht_gf"].isna().all()


def test_comeback_record_counts_wins_and_draws_from_deficits() -> None:
    candidates = events.ht_comeback_record(_ctx())
    assert len(candidates) == 1
    fact = _fact(candidates[0], "ht_comeback_record")
    assert fact["values"] == {
        "ht_deficits": 7,
        "comeback_wins": 4,
        "comeback_draws": 3,
    }


def test_lead_conversion_counts_only_recorded_half_times() -> None:
    candidates = events.ht_lead_conversion(_ctx())
    assert len(candidates) == 1
    fact = _fact(candidates[0], "ht_lead_conversion")
    assert fact["values"] == {"ht_leads": 5, "leads_won": 5, "leads_drawn": 0}


def test_half_time_templates_noop_without_ht_columns() -> None:
    ctx = _ctx(_matches().drop(columns=["ht_home_score", "ht_away_score"]))
    assert events.ht_comeback_record(ctx) == []
    assert events.ht_lead_conversion(ctx) == []
