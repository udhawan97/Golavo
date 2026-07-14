"""Men's World Cup pedigree facts from the isolated Fjelstul pack."""

from __future__ import annotations

import pandas as pd

from ._history import Candidate, TemplateContext, clamp_unit
from .render import NumberBag


def _sides(ctx: TemplateContext) -> tuple[str, str]:
    return ctx.home_team, ctx.away_team


def _as_of(frame: pd.DataFrame, cutoff: pd.Timestamp) -> pd.DataFrame:
    return frame.loc[pd.to_datetime(frame["end_date"], utc=True) <= cutoff]


def wc_pedigree(ctx: TemplateContext) -> list[Candidate]:
    history = ctx.wc_history
    if history is None:
        return []
    appearances = _as_of(history.appearances, ctx.as_of)
    standings = _as_of(history.standings, ctx.as_of)
    out: list[Candidate] = []
    for team in _sides(ctx):
        team_apps = appearances.loc[appearances["team_name"].eq(team)].drop_duplicates(
            "tournament_id"
        )
        n = int(len(team_apps))
        if n == 0:
            continue
        finishes = standings.loc[standings["team_name"].eq(team)]
        titles_frame = finishes.loc[finishes["position"].eq(1)]
        titles = int(len(titles_frame))
        finals = int(finishes["position"].isin([1, 2]).sum())
        recent_ids = set(team_apps.nlargest(5, "year")["tournament_id"].astype(str))
        recent_finishes = finishes.loc[finishes["tournament_id"].isin(recent_ids)]
        best_recent = None
        if not recent_finishes.empty:
            best = recent_finishes.sort_values(
                ["position", "year"], ascending=[True, False], kind="mergesort"
            ).iloc[0]
            best_recent = {"position": int(best["position"]), "year": int(best["year"])}

        nb = NumberBag()
        apps_text = nb.count("appearances", n)
        titles_text = nb.count("titles", titles)
        out.append(
            Candidate(
                subject=team,
                text=(
                    f"{team} have appeared at {apps_text} World Cups in this data, "
                    f"winning the title {titles_text} times."
                ),
                values={
                    "titles": titles,
                    "title_years": sorted(int(year) for year in titles_frame["year"]),
                    "finals": finals,
                    "appearances": n,
                    "best_recent": best_recent,
                },
                numbers=nb.items(),
                sample_n=n,
                denominator=n,
                first_date=pd.Timestamp(team_apps["end_date"].min()),
                last_date=pd.Timestamp(team_apps["end_date"].max()),
                specificity=clamp_unit(0.25 + titles / max(n, 1)),
                extra={"source_ids": [history.source_id]},
            )
        )
    return out


def wc_awards(ctx: TemplateContext) -> list[Candidate]:
    history = ctx.wc_history
    if history is None:
        return []
    awards = _as_of(history.awards, ctx.as_of)
    out: list[Candidate] = []
    for team in _sides(ctx):
        won = awards.loc[awards["team_name"].eq(team)]
        n = int(len(won))
        if n == 0:
            continue
        won = won.sort_values(["year", "award_name", "player"], kind="mergesort")
        nb = NumberBag()
        count = nb.count("awards", n)
        out.append(
            Candidate(
                subject=team,
                text=f"{team}'s players have won {count} individual World Cup awards in this data.",
                values={
                    "awards": [
                        {
                            "award": str(row.award_name),
                            "player": str(row.player),
                            "year": int(row.year),
                        }
                        for row in won.itertuples()
                    ]
                },
                numbers=nb.items(),
                sample_n=n,
                denominator=n,
                first_date=pd.Timestamp(won["end_date"].min()),
                last_date=pd.Timestamp(won["end_date"].max()),
                specificity=clamp_unit(0.2 + n / 20),
                extra={"source_ids": [history.source_id]},
            )
        )
    return out
