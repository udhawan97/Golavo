"""Predictive templates — labelled base rates with genuine forward signal.

These are the ONLY facts that describe a tendency rather than pure background.
They are reported as historical base rates and are *never* fed to the forecast
model here: the model consumes signal solely through its own typed-feature gate.
A predictive fact in this notebook changes no probability — it is commentary that
happens to be forward-looking, clearly labelled so a reader is not misled.
"""

from __future__ import annotations

import pandas as pd

from ._history import Candidate, TemplateContext, as_date_iso, clamp_unit, team_perspective
from .render import NumberBag


def home_advantage_base_rate(ctx: TemplateContext) -> list[Candidate]:
    """Home-win base rate in this competition, over non-neutral completed matches."""
    comp = ctx.matches.loc[ctx.matches["tournament"].eq(ctx.competition)]
    non_neutral = comp.loc[~comp["neutral"].astype("boolean").fillna(False)]
    n = int(len(non_neutral))
    if n == 0:
        return []
    home_wins = int((non_neutral["home_score"] > non_neutral["away_score"]).sum())
    rate = home_wins / n
    nb = NumberBag()
    pct = nb.percent("home_win_rate", rate)
    n_d = nb.count("matches", n)
    return [
        Candidate(
            subject=ctx.competition,
            text=(
                f"In {ctx.competition}, the home side has won {pct} of {n_d} non-neutral "
                "matches in this data."
            ),
            values={"matches": n, "home_wins": home_wins},
            numbers=nb.items(),
            sample_n=n,
            denominator=n,
            base_rate=rate,
            first_date=non_neutral["date"].min(),
            last_date=non_neutral["date"].max(),
            specificity=clamp_unit(abs(rate - 1 / 3) * 2),
        )
    ]


def competition_debut_base_rate(ctx: TemplateContext) -> list[Candidate]:
    """First-year win rate for teams that genuinely arrive mid-dataset.

    A left-censoring guard excludes teams present from the first season (their
    "first appearance" is the data horizon, not a real debut). This is an honest
    proxy for the promoted-team base rate: the CC0 single-league packs carry no
    division tier, so true promotion cannot be detected and is not claimed.
    """
    comp = ctx.matches.loc[ctx.matches["tournament"].eq(ctx.competition)]
    if comp.empty:
        return []
    stacked = pd.concat(
        [
            comp[["home_team", "date"]].rename(columns={"home_team": "team"}),
            comp[["away_team", "date"]].rename(columns={"away_team": "team"}),
        ],
        ignore_index=True,
    )
    first_appearance = stacked.groupby("team")["date"].min()
    censor_cutoff = comp["date"].min() + pd.Timedelta(days=365)
    newcomers = first_appearance.loc[first_appearance > censor_cutoff]
    if newcomers.empty:
        return []

    total = 0
    wins = 0
    teams = 0
    first_dates: list[pd.Timestamp] = []
    last_dates: list[pd.Timestamp] = []
    for team, first_date in sorted(newcomers.items(), key=lambda kv: (kv[1], str(kv[0]))):
        persp = team_perspective(comp, team)
        window_end = first_date + pd.Timedelta(days=365)
        window = persp.loc[(persp["date"] >= first_date) & (persp["date"] <= window_end)]
        if window.empty:
            continue
        teams += 1
        total += int(len(window))
        wins += int((window["result"] == "W").sum())
        first_dates.append(pd.Timestamp(first_date))
        last_dates.append(pd.Timestamp(window["date"].max()))
    if total == 0 or teams < 3:
        return []

    rate = wins / total
    nb = NumberBag()
    pct = nb.percent("debut_win_rate", rate)
    n_d = nb.count("matches", total)
    k_d = nb.count("teams", teams)
    return [
        Candidate(
            subject=ctx.competition,
            text=(
                f"In {ctx.competition}, teams in their first year after arriving have won "
                f"{pct} of {n_d} matches (across {k_d} first-time teams) in this data."
            ),
            values={
                "matches": total,
                "wins": wins,
                "teams": teams,
                "note": "debut-window proxy; not promotion (no tier data in pack)",
            },
            numbers=nb.items(),
            sample_n=total,
            denominator=total,
            base_rate=rate,
            first_date=min(first_dates),
            last_date=max(last_dates),
            specificity=clamp_unit(abs(rate - 1 / 3) * 2),
            extra={"first_debut": as_date_iso(min(first_dates))},
        )
    ]
