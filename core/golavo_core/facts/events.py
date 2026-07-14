"""Event-derived templates from the vendored goalscorers/shootouts packs.

These read columns the engine loaded but never surfaced — goal minute, penalty
flag, own-goal flag, and the shootout first-taker — to add honest "hidden" stats.
Internationals only: each returns ``[]`` when its side table is absent (club
packs carry neither), exactly like ``top_scorer``/``shootout_record``. Every
template is a pure function of a :class:`TemplateContext`, number-disciplined, and
leak-safe (the side tables are already scoped to the as-of horizon upstream).
"""

from __future__ import annotations

import re

import pandas as pd

from ._history import Candidate, TemplateContext, clamp_unit, team_perspective
from .render import NumberBag

_MINUTE_RE = re.compile(r"^\s*(\d{1,3})")

# A 15-minute phase spans 15 of a nominal 90-minute match, so the uniform base
# rate for "goals in this phase" is 15/90. A team whose share of TIMED goals in a
# phase departs from this by at least _TIMING_DELTA is a genuine timing skew.
_PHASE_BASE = 15.0 / 90.0
_TIMING_DELTA = 0.12


def _minute(value: object) -> int | None:
    """Parse a goal minute ("45", "90+2", 73.0) to its base integer, else None."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    match = _MINUTE_RE.match(str(value))
    if not match:
        return None
    return int(match.group(1))


def _sides(ctx: TemplateContext) -> tuple[str, str]:
    return ctx.home_team, ctx.away_team


def _team_goals(scorers: pd.DataFrame, team: str) -> pd.DataFrame:
    """The team's own (non-own-goal) goals in the vendored data."""
    return scorers.loc[
        scorers["team"].eq(team) & (~scorers["own_goal"].astype("boolean").fillna(False))
    ]


def ht_comeback_record(ctx: TemplateContext) -> list[Candidate]:
    """Wins and draws after trailing at half-time, for rows with recorded HT."""
    if "ht_home_score" not in ctx.matches.columns:
        return []
    out: list[Candidate] = []
    for team in _sides(ctx):
        history = team_perspective(ctx.matches, team).dropna(subset=["ht_gf", "ht_ga"])
        deficits = history.loc[history["ht_gf"] < history["ht_ga"]]
        n = int(len(deficits))
        if n == 0:
            continue
        wins = int(deficits["result"].eq("W").sum())
        draws = int(deficits["result"].eq("D").sum())
        nb = NumberBag()
        d = nb.count("ht_deficits", n)
        w = nb.count("comeback_wins", wins)
        dr = nb.count("comeback_draws", draws)
        out.append(
            Candidate(
                subject=team,
                text=(
                    f"After trailing at half-time in {d} matches in this data, "
                    f"{team} recovered to win {w} and draw {dr}."
                ),
                values={
                    "ht_deficits": n,
                    "comeback_wins": wins,
                    "comeback_draws": draws,
                },
                numbers=nb.items(),
                sample_n=n,
                denominator=n,
                base_rate=(wins + draws) / n,
                first_date=pd.Timestamp(deficits["date"].min()),
                last_date=pd.Timestamp(deficits["date"].max()),
                specificity=clamp_unit((wins + draws) / n),
            )
        )
    return out


def ht_lead_conversion(ctx: TemplateContext) -> list[Candidate]:
    """Wins and draws after leading at half-time, for rows with recorded HT."""
    if "ht_home_score" not in ctx.matches.columns:
        return []
    out: list[Candidate] = []
    for team in _sides(ctx):
        history = team_perspective(ctx.matches, team).dropna(subset=["ht_gf", "ht_ga"])
        leads = history.loc[history["ht_gf"] > history["ht_ga"]]
        n = int(len(leads))
        if n == 0:
            continue
        wins = int(leads["result"].eq("W").sum())
        draws = int(leads["result"].eq("D").sum())
        nb = NumberBag()
        d = nb.count("ht_leads", n)
        w = nb.count("leads_won", wins)
        dr = nb.count("leads_drawn", draws)
        out.append(
            Candidate(
                subject=team,
                text=(
                    f"After leading at half-time in {d} matches in this data, "
                    f"{team} went on to win {w} and draw {dr}."
                ),
                values={"ht_leads": n, "leads_won": wins, "leads_drawn": draws},
                numbers=nb.items(),
                sample_n=n,
                denominator=n,
                base_rate=wins / n,
                first_date=pd.Timestamp(leads["date"].min()),
                last_date=pd.Timestamp(leads["date"].max()),
                specificity=clamp_unit(wins / n),
            )
        )
    return out


def goal_timing_profile(ctx: TemplateContext) -> list[Candidate]:
    """When a team scores: a skew toward the opening or closing stages of matches.

    Emits at most one fact per team — the phase (opening ≤15' or closing ≥76')
    whose share of the team's TIMED goals departs most from the 15/90 baseline,
    and only when that departure clears ``_TIMING_DELTA``. The minute column is
    sparse for older matches, so the denominator is timed goals only, stated as
    such.
    """
    scorers = ctx.goalscorers
    if scorers is None or scorers.empty:
        return []
    out: list[Candidate] = []
    for team in _sides(ctx):
        goals = _team_goals(scorers, team)
        minutes = [m for m in (_minute(v) for v in goals["minute"].tolist()) if m is not None]
        total = len(minutes)
        if total < 20:
            continue
        opening = sum(1 for m in minutes if m <= 15)
        closing = sum(1 for m in minutes if m >= 76)
        # Pick the more extreme phase relative to the 15/90 baseline.
        phases = [
            ("closing", closing, "in the closing stages"),
            ("opening", opening, "in the opening stages"),
        ]
        key, count, phrase = max(phases, key=lambda p: abs(p[1] / total - _PHASE_BASE))
        share = count / total
        if abs(share - _PHASE_BASE) < _TIMING_DELTA:
            continue
        nb = NumberBag()
        n = nb.count("phase_goals", count)
        d = nb.count("timed_goals", total)
        pct = nb.percent("phase_share", share)
        timed = goals.loc[goals["minute"].map(lambda v: _minute(v) is not None)]
        out.append(
            Candidate(
                subject=team,
                text=(
                    f"{team} have scored {n} of their {d} timed goals in this data "
                    f"{phrase} ({pct})."
                ),
                values={"phase": key, "phase_goals": count, "timed_goals": total},
                numbers=nb.items(),
                sample_n=total,
                denominator=total,
                base_rate=_PHASE_BASE,
                first_date=pd.Timestamp(timed["date"].min()),
                last_date=pd.Timestamp(timed["date"].max()),
                specificity=clamp_unit(abs(share - _PHASE_BASE) * 3),
            )
        )
    return out


def penalty_goal_share(ctx: TemplateContext) -> list[Candidate]:
    """How much of a team's scoring is penalties (SCORED penalties only).

    The source records only scored goals, so this can never speak to penalties
    won or a conversion rate — the text says "were penalties", never "converted".
    """
    scorers = ctx.goalscorers
    if scorers is None or scorers.empty:
        return []
    out: list[Candidate] = []
    for team in _sides(ctx):
        goals = _team_goals(scorers, team)
        total = int(len(goals))
        if total < 30:  # too few goals for a share to be meaningful
            continue
        pens = int(goals["penalty"].astype("boolean").fillna(False).sum())
        if pens < 5:
            continue
        nb = NumberBag()
        p = nb.count("penalties", pens)
        d = nb.count("goals", total)
        pct = nb.percent("penalty_share", pens / total)
        out.append(
            Candidate(
                subject=team,
                text=f"{p} of {team}'s {d} goals in this data were penalties ({pct}).",
                values={"penalties": pens, "goals": total},
                numbers=nb.items(),
                sample_n=pens,
                denominator=total,
                base_rate=pens / total,
                first_date=pd.Timestamp(goals["date"].min()),
                last_date=pd.Timestamp(goals["date"].max()),
                specificity=clamp_unit(pens / total * 2),
            )
        )
    return out


def own_goal_quirk(ctx: TemplateContext) -> list[Candidate]:
    """A coincidence: how many own goals a team has benefited from in this data.

    Own-goal rows are credited to the beneficiary team, so these are goals the
    OPPONENT put through their own net. Labelled coincidence and capped — a
    curio, never a signal.
    """
    scorers = ctx.goalscorers
    if scorers is None or scorers.empty:
        return []
    out: list[Candidate] = []
    for team in _sides(ctx):
        own = scorers.loc[
            scorers["team"].eq(team) & scorers["own_goal"].astype("boolean").fillna(False)
        ]
        n = int(len(own))
        if n < 3:
            continue
        nb = NumberBag()
        c = nb.count("own_goals", n)
        out.append(
            Candidate(
                subject=team,
                text=f"{team} have benefited from {c} own goals in this data.",
                values={"own_goals": n},
                numbers=nb.items(),
                sample_n=n,
                denominator=n,
                first_date=pd.Timestamp(own["date"].min()),
                last_date=pd.Timestamp(own["date"].max()),
                specificity=clamp_unit(n / 12.0),
            )
        )
    return out


def shootout_first_shooter_edge(ctx: TemplateContext) -> list[Candidate]:
    """Competition-wide: does the side taking the first penalty tend to win?

    A single labelled base rate over every recorded shootout with a known first
    taker — the "shooting first" edge, against a 0.5 coin-flip baseline.
    """
    shootouts = ctx.shootouts
    if shootouts is None or shootouts.empty or "first_shooter" not in shootouts.columns:
        return []
    known = shootouts.loc[shootouts["first_shooter"].notna()]
    known = known.loc[known["first_shooter"].astype("string").str.strip().ne("")]
    n = int(len(known))
    if n == 0:
        return []
    first_won = int(
        (
            known["winner"].astype("string")
            == known["first_shooter"].astype("string")
        ).sum()
    )
    rate = first_won / n
    nb = NumberBag()
    n_d = nb.count("shootouts", n)
    pct = nb.percent("first_shooter_win_rate", rate)
    return [
        Candidate(
            subject=ctx.competition or "penalty shootouts",
            text=(
                f"Across {n_d} penalty shootouts with a recorded first taker in this data, "
                f"the side shooting first went on to win ({pct})."
            ),
            values={"shootouts": n, "first_shooter_wins": first_won},
            numbers=nb.items(),
            sample_n=n,
            denominator=n,
            base_rate=0.5,
            first_date=pd.Timestamp(known["date"].min()),
            last_date=pd.Timestamp(known["date"].max()),
            specificity=clamp_unit(abs(rate - 0.5) * 3),
        )
    ]
