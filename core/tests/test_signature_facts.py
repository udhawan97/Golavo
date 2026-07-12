"""The signature-stat templates fire on crafted history and stay disciplined.

These prove the new "unusual form" insights actually produce facts (not just that
the notebook still builds), and that each stays number-disciplined and cites only
digits it declares.
"""

from __future__ import annotations

import pandas as pd
from golavo_core.facts import signature
from golavo_core.facts._history import TemplateContext
from golavo_core.facts.guardrails import assert_number_discipline
from golavo_core.facts.registry import Template


def _ctx(matches: pd.DataFrame, home: str, away: str) -> TemplateContext:
    ko = pd.Timestamp("2025-06-01", tz="UTC")
    return TemplateContext(
        matches=matches,
        home_team=home,
        away_team=away,
        competition="Test League",
        neutral=False,
        as_of=ko - pd.Timedelta(seconds=1),
        kickoff=ko,
        source_ids=("test-source",),
    )


def _m(mid, date, home, away, hs, aws):
    return {
        "match_id": mid, "date": pd.Timestamp(date), "kickoff_utc": pd.Timestamp(date, tz="UTC"),
        "home_team": home, "away_team": away, "home_score": hs, "away_score": aws,
        "is_complete": True, "neutral": False, "tournament": "Test League",
    }


def _discipline_ok(candidate, template_id: str) -> None:
    """Assert the candidate's prose only states numbers it declares (the guard the
    served AI whitelist reuses)."""
    fact = {"id": template_id, "text": candidate.text, "numbers": candidate.numbers}
    assert_number_discipline(fact)


def _long_history(home: str, away: str) -> pd.DataFrame:
    """~18 completed matches for `home` with a clear late scoring surge, mixed
    both-scored / clean-sheet outcomes, plus several head-to-head meetings."""
    rows = []
    n = 0
    # 12 earlier matches: low-scoring, defensively tight for `home`.
    for i in range(12):
        n += 1
        rows.append(_m(f"m_e{n}", f"2024-0{1 + i % 6}-0{1 + i % 8}", home, f"Opp{i%4}", i % 2, 0))
    # 6 recent matches: a scoring surge and goals conceded (both-teams-score).
    for i in range(6):
        n += 1
        rows.append(_m(f"m_r{n}", f"2025-0{1 + i % 5}-1{i % 9}", home, f"Opp{i%3}", 3, 1))
    # head-to-head meetings, goal-heavy, both scoring.
    for i in range(5):
        n += 1
        rows.append(_m(f"m_h{n}", f"2023-0{1 + i}-15", home, away, 2, 2))
    return pd.DataFrame(rows)


def test_both_teams_scored_rate_fires_and_is_disciplined() -> None:
    df = _long_history("Alpha", "Beta")
    facts = signature.both_teams_scored_rate(_ctx(df, "Alpha", "Beta"))
    alpha = [c for c in facts if c.subject == "Alpha"]
    assert alpha, "expected a both-teams-scored fact for Alpha"
    c = alpha[0]
    assert c.base_rate is not None and 0.0 <= c.base_rate <= 1.0
    _discipline_ok(c, "both_teams_scored_rate")


def test_clean_sheet_rate_fires_and_is_disciplined() -> None:
    df = _long_history("Alpha", "Beta")
    facts = signature.clean_sheet_rate(_ctx(df, "Alpha", "Beta"))
    alpha = [c for c in facts if c.subject == "Alpha"]
    assert alpha
    _discipline_ok(alpha[0], "clean_sheet_rate")


def test_scoring_trend_detects_the_surge_and_is_disciplined() -> None:
    df = _long_history("Alpha", "Beta")
    facts = signature.scoring_trend(_ctx(df, "Alpha", "Beta"))
    alpha = [c for c in facts if c.subject == "Alpha"]
    assert alpha, "a clear late surge should surface a scoring-trend fact"
    assert alpha[0].values["rising"] is True
    _discipline_ok(alpha[0], "scoring_trend")


def test_scoring_trend_stays_silent_without_a_real_shift() -> None:
    # Flat scoring: no trend should be claimed.
    rows = [
        _m(f"m{i}", f"2024-0{1 + i % 6}-0{1 + i % 8}", "Flat", f"O{i % 4}", 1, 1)
        for i in range(18)
    ]
    facts = signature.scoring_trend(_ctx(pd.DataFrame(rows), "Flat", "Other"))
    assert [c for c in facts if c.subject == "Flat"] == []


def test_head_to_head_goals_reports_the_goal_character() -> None:
    df = _long_history("Alpha", "Beta")
    facts = signature.head_to_head_goals(_ctx(df, "Alpha", "Beta"))
    assert facts, "meetings exist, so a H2H goals fact should be produced"
    c = facts[0]
    assert c.values["meetings"] == 5
    assert c.values["avg_goals"] == 4.0  # 2+2 every meeting
    _discipline_ok(c, "head_to_head_goals")


def test_head_to_head_goals_silent_for_first_meeting() -> None:
    rows = [_m(f"m{i}", f"2024-0{1 + i % 6}-05", "Solo", f"O{i}", 1, 0) for i in range(6)]
    facts = signature.head_to_head_goals(_ctx(pd.DataFrame(rows), "Solo", "NeverPlayed"))
    assert facts == []


def test_all_signature_templates_are_registered() -> None:
    from golavo_core.facts.registry import REGISTRY

    ids = {t.id for t in REGISTRY if isinstance(t, Template)}
    new = ("both_teams_scored_rate", "clean_sheet_rate", "scoring_trend", "head_to_head_goals")
    for tid in new:
        assert tid in ids, f"{tid} must be pre-registered"
