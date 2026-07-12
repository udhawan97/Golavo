"""Signature-stat templates — the unusual form insights a good commentator knows
but most scoreboards never show.

Same rules as every other template: pure functions of a :class:`TemplateContext`,
number-disciplined text (every digit is a declared number), and only the
fixture's own two teams and competition named in prose. These deliberately go
beyond streaks and win/draw/loss records — both-teams-to-score reliability,
scoring momentum, clean-sheet rate, and the goal character of the head-to-head —
so the notebook says something a reader could not already read off the scoreline
or the model council.
"""

from __future__ import annotations

from ._history import Candidate, TemplateContext, clamp_unit, head_to_head, team_perspective
from .render import NumberBag


def _sides(ctx: TemplateContext) -> tuple[str, str]:
    return ctx.home_team, ctx.away_team


def both_teams_scored_rate(ctx: TemplateContext) -> list[Candidate]:
    """How often both teams find the net in a side's recent matches (last 20)."""
    window = 20
    out: list[Candidate] = []
    for team in _sides(ctx):
        persp = team_perspective(ctx.matches, team).tail(window)
        n = int(len(persp))
        if n == 0:
            continue
        btts = int(((persp["gf"] > 0) & (persp["ga"] > 0)).sum())
        frac = btts / n
        nb = NumberBag()
        m = nb.count("both_scored", btts)
        n_d = nb.count("matches", n)
        rate = nb.percent("rate", frac)
        out.append(
            Candidate(
                subject=team,
                text=f"Both teams have scored in {m} of {team}'s last {n_d} matches ({rate}).",
                values={"both_scored": btts, "matches": n},
                numbers=nb.items(),
                sample_n=n,
                denominator=n,
                base_rate=frac,
                first_date=persp["date"].iloc[0],
                last_date=persp["date"].iloc[-1],
                # Extremes (very high or very low) are the interesting cases.
                specificity=clamp_unit(abs(frac - 0.5) * 2.0),
            )
        )
    return out


def clean_sheet_rate(ctx: TemplateContext) -> list[Candidate]:
    """A side's clean-sheet RATE over its recent matches (distinct from the current
    clean-sheet streak) — how reliably its defence shuts the door."""
    window = 20
    out: list[Candidate] = []
    for team in _sides(ctx):
        persp = team_perspective(ctx.matches, team).tail(window)
        n = int(len(persp))
        if n == 0:
            continue
        clean = int((persp["ga"] == 0).sum())
        frac = clean / n
        nb = NumberBag()
        c = nb.count("clean_sheets", clean)
        n_d = nb.count("matches", n)
        rate = nb.percent("rate", frac)
        out.append(
            Candidate(
                subject=team,
                text=f"{team} have kept a clean sheet in {c} of their last {n_d} matches ({rate}).",
                values={"clean_sheets": clean, "matches": n},
                numbers=nb.items(),
                sample_n=n,
                denominator=n,
                base_rate=frac,
                first_date=persp["date"].iloc[0],
                last_date=persp["date"].iloc[-1],
                specificity=clamp_unit(abs(frac - 0.3) * 1.6),
            )
        )
    return out


def scoring_trend(ctx: TemplateContext) -> list[Candidate]:
    """Attacking momentum: goals-per-game over a side's last 6 matches versus the
    stretch before that. Emitted only when the shift is clear, so it never dresses
    up noise as a trend."""
    recent_n = 6
    baseline_n = 18
    min_shift = 0.5  # goals per game
    out: list[Candidate] = []
    for team in _sides(ctx):
        persp = team_perspective(ctx.matches, team)
        if len(persp) < recent_n + 6:
            continue
        recent = persp.tail(recent_n)
        baseline = persp.iloc[:-recent_n].tail(baseline_n)
        if len(baseline) < 6:
            continue
        recent_gpg = float(recent["gf"].mean())
        base_gpg = float(baseline["gf"].mean())
        if abs(recent_gpg - base_gpg) < min_shift:
            continue
        nb = NumberBag()
        r = nb.goals("recent_per_game", recent_gpg)
        rn = nb.count("recent_matches", recent_n)
        b = nb.goals("baseline_per_game", base_gpg)
        direction = "up from" if recent_gpg > base_gpg else "down from"
        out.append(
            Candidate(
                subject=team,
                text=(
                    f"{team} are scoring {r} goals a game over their last {rn} matches — "
                    f"{direction} {b} in the run before."
                ),
                values={
                    "recent_per_game": round(recent_gpg, 3),
                    "baseline_per_game": round(base_gpg, 3),
                    "recent_matches": recent_n,
                    "rising": recent_gpg > base_gpg,
                },
                numbers=nb.items(),
                sample_n=int(len(persp)),
                denominator=int(len(persp)),
                first_date=baseline["date"].iloc[0],
                last_date=recent["date"].iloc[-1],
                specificity=clamp_unit(abs(recent_gpg - base_gpg) / 2.0),
            )
        )
    return out


def head_to_head_goals(ctx: TemplateContext) -> list[Candidate]:
    """The goal CHARACTER of the head-to-head — average goals and how often both
    teams have scored in it — the dimension the win/draw/loss record leaves out."""
    h2h = head_to_head(ctx.matches, ctx.home_team, ctx.away_team)
    n = int(len(h2h))
    if n == 0:
        return []
    totals = (h2h["home_score"] + h2h["away_score"]).astype(int)
    avg = float(totals.mean())
    btts = int(((h2h["home_score"] > 0) & (h2h["away_score"] > 0)).sum())
    nb = NumberBag()
    a = nb.goals("avg_goals", avg)
    m = nb.count("meetings", n)
    b = nb.count("both_scored", btts)
    return [
        Candidate(
            subject=f"{ctx.home_team} v {ctx.away_team}",
            text=(
                f"Meetings between {ctx.home_team} and {ctx.away_team} have averaged "
                f"{a} goals across {m} games — both teams scoring in {b} of them."
            ),
            values={"avg_goals": round(avg, 3), "meetings": n, "both_scored": btts},
            numbers=nb.items(),
            sample_n=n,
            denominator=n,
            base_rate=btts / n,
            first_date=h2h["date"].iloc[0],
            last_date=h2h["date"].iloc[-1],
            # A famine (<2) or a glut (>3.2) is the notable case.
            specificity=clamp_unit(abs(avg - 2.6) / 2.0),
        )
    ]
