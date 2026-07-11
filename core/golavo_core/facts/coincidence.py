"""Coincidence templates — patterns for the pub, never for the forecast.

These are calendar and pattern quirks with no forward signal. They are labelled
``coincidence``, capped, ranked by specificity (not by any significance test),
walled off in the UI, and NEVER folded into the AI evidence bundle. They exist
so the notebook can surface a fun quirk while being explicit that it is noise.
"""

from __future__ import annotations

import pandas as pd

from ._history import (
    Candidate,
    TemplateContext,
    as_date_iso,
    clamp_unit,
    head_to_head,
    team_perspective,
)
from .render import NumberBag

_WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def _sides(ctx: TemplateContext) -> tuple[str, str]:
    return ctx.home_team, ctx.away_team


def day_of_week_streak(ctx: TemplateContext) -> list[Candidate]:
    out: list[Candidate] = []
    for team in _sides(ctx):
        persp = team_perspective(ctx.matches, team)
        wins = persp.loc[persp["result"] == "W"]
        if len(wins) < 4:
            continue
        weekdays = pd.to_datetime(wins["date"]).dt.dayofweek.tolist()
        last_wd = weekdays[-1]
        run = 0
        for wd in reversed(weekdays):
            if wd == last_wd:
                run += 1
            else:
                break
        if run < 4:
            continue
        tail = wins.iloc[len(wins) - run :]
        nb = NumberBag()
        n = nb.count("wins", run)
        out.append(
            Candidate(
                subject=team,
                text=f"{team}'s last {n} wins all fell on a {_WEEKDAYS[last_wd]}.",
                values={"wins": run, "weekday": _WEEKDAYS[last_wd]},
                numbers=nb.items(),
                sample_n=run,
                denominator=run,
                first_date=tail["date"].iloc[0],
                last_date=tail["date"].iloc[-1],
                specificity=clamp_unit(run / 8.0),
            )
        )
    return out


def scoreline_repeat(ctx: TemplateContext) -> list[Candidate]:
    h2h = head_to_head(ctx.matches, ctx.home_team, ctx.away_team)
    meetings = int(len(h2h))
    if meetings < 4:
        return []
    last = h2h.iloc[-1]
    a, b = int(last["home_score"]), int(last["away_score"])
    target = tuple(sorted((a, b)))
    same = [
        tuple(sorted((int(r.home_score), int(r.away_score)))) == target
        for r in h2h.itertuples(index=False)
    ]
    count = int(sum(same))
    if count < 2:
        return []
    nb = NumberBag()
    a_d = nb.count("last_home_goals", a)
    b_d = nb.count("last_away_goals", b)
    c_d = nb.count("repeats", count)
    m_d = nb.count("meetings", meetings)
    return [
        Candidate(
            subject=f"{ctx.home_team} v {ctx.away_team}",
            text=(
                f"Their most recent meeting finished {a_d}–{b_d}; the same scoreline "
                f"(either way) has occurred in {c_d} of {m_d} meetings."
            ),
            values={"last_score": f"{a}-{b}", "repeats": count, "meetings": meetings},
            numbers=nb.items(),
            sample_n=count,
            denominator=meetings,
            first_date=h2h["date"].iloc[0],
            last_date=h2h["date"].iloc[-1],
            specificity=clamp_unit(count / meetings),
        )
    ]


def calendar_date_repeat(ctx: TemplateContext) -> list[Candidate]:
    month, day = int(ctx.kickoff.month), int(ctx.kickoff.day)
    out: list[Candidate] = []
    for team in _sides(ctx):
        persp = team_perspective(ctx.matches, team)
        if persp.empty:
            continue
        dates = pd.to_datetime(persp["date"])
        on_date = persp.loc[(dates.dt.month == month) & (dates.dt.day == day)]
        n = int(len(on_date))
        if n < 3:
            continue
        wins = int((on_date["result"] == "W").sum())
        nb = NumberBag()
        n_d = nb.count("appearances", n)
        w_d = nb.count("wins", wins)
        out.append(
            Candidate(
                subject=team,
                text=(
                    f"{team} have played on this calendar date {n_d} times before, "
                    f"winning {w_d}."
                ),
                values={"appearances": n, "wins": wins, "month": month, "day": day},
                numbers=nb.items(),
                sample_n=n,
                denominator=n,
                first_date=on_date["date"].iloc[0],
                last_date=on_date["date"].iloc[-1],
                specificity=clamp_unit(n / 6.0),
                extra={
                    "calendar_date": f"{month:02d}-{day:02d}",
                    "match_date": as_date_iso(on_date["date"].iloc[-1]),
                },
            )
        )
    return out
