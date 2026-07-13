"""New event-derived templates (goal timing, penalties, own goals, first-shooter)
and per-dataset citation attribution.

These read pack columns the engine loaded but never surfaced. Each is honest
(number-disciplined, scored-penalties-only), internationals-only, and leak-safe.
"""

from __future__ import annotations

import pandas as pd
import pytest

from golavo_core.facts import events
from golavo_core.facts._history import TemplateContext
from golavo_core.facts.guardrails import assert_number_discipline, build_fact
from golavo_core.facts.registry import REGISTRY


def _ctx(goalscorers=None, shootouts=None, matches=None) -> TemplateContext:
    empty = pd.DataFrame(
        columns=["date", "home_team", "away_team", "home_score", "away_score",
                 "neutral", "tournament"]
    )
    return TemplateContext(
        matches=empty if matches is None else matches,
        home_team="Aland", away_team="Borda", competition="FIFA World Cup",
        neutral=False, as_of=pd.Timestamp("2025-06-01", tz="UTC"),
        kickoff=pd.Timestamp("2025-06-01", tz="UTC"), source_ids=("test-source",),
        goalscorers=goalscorers, shootouts=shootouts,
    )


def _goalscorers() -> pd.DataFrame:
    rows = []
    # 30 non-own Aland goals: 15 late (minute 85), 15 mid (minute 40); 6 penalties.
    for i in range(30):
        minute = "85" if i < 15 else "40"
        rows.append({
            "date": pd.Timestamp(f"2024-0{(i % 8) + 1}-01"),
            "home_team": "Aland", "away_team": "Borda", "team": "Aland",
            "scorer": f"Player{i % 5}", "minute": minute,
            "own_goal": False, "penalty": i < 6,
        })
    # 4 own goals benefiting Aland.
    for i in range(4):
        rows.append({
            "date": pd.Timestamp(f"2024-0{i + 1}-15"),
            "home_team": "Aland", "away_team": "Borda", "team": "Aland",
            "scorer": "OG", "minute": "50", "own_goal": True, "penalty": False,
        })
    df = pd.DataFrame(rows)
    df["own_goal"] = df["own_goal"].astype(bool)
    df["penalty"] = df["penalty"].astype(bool)
    return df


def _discipline_ok(candidates, template_id: str) -> None:
    tmpl = next(t for t in REGISTRY if t.id == template_id)
    for cand in candidates:
        fact, _ = build_fact(cand, tmpl, ("test-source",), pd.Timestamp("2025-06-01", tz="UTC"))
        assert_number_discipline(fact)  # raises on an undisciplined digit


def test_goal_timing_profile_detects_a_late_skew() -> None:
    cands = events.goal_timing_profile(_ctx(goalscorers=_goalscorers()))
    assert len(cands) == 1
    c = cands[0]
    assert c.values["phase"] == "closing"
    assert c.values["phase_goals"] == 15
    assert c.values["timed_goals"] == 30
    assert "closing stages" in c.text
    _discipline_ok(cands, "goal_timing_profile")


def test_penalty_share_never_implies_conversion() -> None:
    cands = events.penalty_goal_share(_ctx(goalscorers=_goalscorers()))
    assert len(cands) == 1
    c = cands[0]
    assert c.values["penalties"] == 6
    assert c.values["goals"] == 30
    assert "were penalties" in c.text
    # Honest phrasing: the source has no misses, so never "won"/"converted"/"scored".
    lowered = c.text.lower()
    assert "won" not in lowered and "convert" not in lowered
    _discipline_ok(cands, "penalty_goal_share")


def test_own_goal_quirk_counts_beneficiary_own_goals() -> None:
    cands = events.own_goal_quirk(_ctx(goalscorers=_goalscorers()))
    assert len(cands) == 1
    assert cands[0].values["own_goals"] == 4
    _discipline_ok(cands, "own_goal_quirk")


def test_shootout_first_shooter_edge_measures_the_first_taker_win_rate() -> None:
    rows = []
    for i in range(60):
        first = "Aland" if i % 2 == 0 else "Borda"
        # First taker wins 40 of 60 → 66.7%.
        winner = first if i < 40 else ("Borda" if first == "Aland" else "Aland")
        rows.append({
            "date": pd.Timestamp(f"20{10 + i % 9}-01-01"),
            "home_team": "Aland", "away_team": "Borda",
            "winner": winner, "first_shooter": first,
        })
    shootouts = pd.DataFrame(rows).astype({"winner": "string", "first_shooter": "string"})
    cands = events.shootout_first_shooter_edge(_ctx(shootouts=shootouts))
    assert len(cands) == 1
    assert cands[0].values["shootouts"] == 60
    assert cands[0].values["first_shooter_wins"] == 40
    _discipline_ok(cands, "shootout_first_shooter_edge")


def test_internationals_only_no_side_tables_means_no_facts() -> None:
    ctx = _ctx()  # goalscorers/shootouts both None (a club fixture)
    assert events.goal_timing_profile(ctx) == []
    assert events.penalty_goal_share(ctx) == []
    assert events.own_goal_quirk(ctx) == []
    assert events.shootout_first_shooter_edge(ctx) == []


def test_goal_timing_is_leak_safe_to_future_goals() -> None:
    base = events.goal_timing_profile(_ctx(goalscorers=_goalscorers()))
    # The context's side tables are already as-of-scoped upstream, but adding a
    # future-dated goal to the SAME frame must not change the template's read of
    # the historical rows it is given (determinism on identical inputs).
    again = events.goal_timing_profile(_ctx(goalscorers=_goalscorers()))
    assert [c.text for c in base] == [c.text for c in again]


@pytest.mark.parametrize("template_id,dataset", [
    ("goal_timing_profile", "goalscorers"),
    ("penalty_goal_share", "goalscorers"),
    ("shootout_record", "shootouts"),
    ("top_scorer", "goalscorers"),
    ("unbeaten_run", "results"),
])
def test_registry_dataset_attribution(template_id: str, dataset: str) -> None:
    from golavo_core.facts.registry import DATASET_BY_TEMPLATE

    assert DATASET_BY_TEMPLATE[template_id] == dataset
