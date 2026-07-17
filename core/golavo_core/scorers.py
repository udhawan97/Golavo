"""Leak-safe competition scorer and shootout boards from the vendored side tables.

The goalscorers and shootouts side tables ship only with the martj42
internationals pack (``golavo_core.facts.packs``), and neither carries a
competition column — a scorer row is (date, home, away, team, scorer, …). So a
board joins the side table to the match index on the same normalized
(date, home, away) key the rest of the codebase uses, which is what attaches the
competition and the kickoff instant.

Every board takes an explicit ``as_of_utc`` and counts only matches whose kickoff
is at or before it, so appending a later match can never rewrite an earlier
board — the same cutoff discipline the analytics and outlook readers use. Own
goals never credit the scorer, and ties break by name so the committed answer is
reproducible.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import pandas as pd

from golavo_core.ingest.match_index import normalize

SCORERS_SCHEMA_VERSION = "0.1.0"


def _competition_names(competition: str | Iterable[str]) -> list[str]:
    """One catalog competition can carry several source names (e.g. a tournament
    and its qualification), so a board accepts either a single name or a set."""
    if isinstance(competition, str):
        return [competition]
    return [str(name) for name in competition]


def _utc(value: str | pd.Timestamp) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    return stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")


def _iso(value: pd.Timestamp) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _competition_match_keys(
    index: pd.DataFrame, *, competition: str | Iterable[str], cutoff: pd.Timestamp
) -> set[tuple[str, str, str]]:
    """The (date, home_norm, away_norm) keys of one competition's matches ≤ cutoff.

    Restricted to completed matches whose kickoff is at or before the cutoff, so a
    side-table row joined against this set can never post-date the board's instant.
    """
    names = _competition_names(competition)
    if not names:
        return set()
    kickoff = pd.to_datetime(index["kickoff_utc"], utc=True)
    complete = index["is_complete"].astype("boolean").fillna(False)
    scoped = index.loc[
        index["competition"].astype("string").isin(names) & complete & (kickoff <= cutoff)
    ]
    return set(
        zip(
            pd.to_datetime(scoped["date"]).dt.strftime("%Y-%m-%d"),
            scoped["home_norm"].astype(str),
            scoped["away_norm"].astype(str),
            strict=True,
        )
    )


def _row_keys(frame: pd.DataFrame) -> pd.Series:
    return pd.Series(
        list(
            zip(
                pd.to_datetime(frame["date"]).dt.strftime("%Y-%m-%d"),
                frame["home_team"].map(normalize),
                frame["away_team"].map(normalize),
                strict=True,
            )
        ),
        index=frame.index,
    )


def competition_top_scorers(
    index: pd.DataFrame,
    goalscorers: pd.DataFrame | None,
    *,
    competition: str | Iterable[str],
    as_of_utc: str | pd.Timestamp | None,
    min_goals: int = 1,
) -> dict[str, Any]:
    """A competition's leading scorers as of ``as_of_utc`` — a leak-safe Golden Boot.

    Own goals never count toward a scorer. Ranking is goals descending, dense
    (tied scorers share a rank), with a name tie-break so the order is stable.
    Returns an honest empty board when no scorer data joins (e.g. a competition
    with no side-table coverage).
    """
    if as_of_utc is None:
        raise ValueError("competition_top_scorers requires an explicit as_of_utc cutoff")
    cutoff = _utc(as_of_utc)
    keys = _competition_match_keys(index, competition=competition, cutoff=cutoff)

    board: dict[str, Any] = {
        "schema_version": SCORERS_SCHEMA_VERSION,
        "competition_names": _competition_names(competition),
        "as_of_utc": _iso(cutoff),
        "scope": "internationals",
        "dataset": "goalscorers",
        "min_goals": int(min_goals),
        "matches_counted": 0,
        "scorers": [],
    }
    if goalscorers is None or goalscorers.empty or not keys:
        return board

    row_keys = _row_keys(goalscorers)
    scored = goalscorers.loc[row_keys.isin(keys)]
    scored = scored.loc[~scored["own_goal"].astype("boolean").fillna(False)]
    if scored.empty:
        return board

    # Count matches that actually contributed a goal, so an empty board reads as
    # "built from 0 matches" rather than implying a played match was goalless.
    board["matches_counted"] = int(_row_keys(scored).nunique())

    penalty = scored["penalty"].astype("boolean").fillna(False)
    grouped = scored.assign(_penalty=penalty).groupby(["scorer", "team"], dropna=True)
    tally = grouped.agg(
        goals=("scorer", "size"),
        penalties=("_penalty", "sum"),
        matches=("date", "nunique"),
        first_date=("date", "min"),
        last_date=("date", "max"),
    ).reset_index()
    tally = tally.loc[tally["goals"] >= int(min_goals)]
    if tally.empty:
        return board

    tally = tally.sort_values(
        ["goals", "scorer"], ascending=[False, True], kind="mergesort"
    ).reset_index(drop=True)

    rows: list[dict[str, Any]] = []
    previous_goals: int | None = None
    rank = 0
    for position, record in enumerate(tally.itertuples(index=False), start=1):
        goals = int(record.goals)
        if goals != previous_goals:
            rank = position
            previous_goals = goals
        rows.append(
            {
                "rank": rank,
                "scorer": str(record.scorer),
                "team": str(record.team),
                "goals": goals,
                "penalties": int(record.penalties),
                "matches_scored_in": int(record.matches),
                "first_date": pd.Timestamp(record.first_date).strftime("%Y-%m-%d"),
                "last_date": pd.Timestamp(record.last_date).strftime("%Y-%m-%d"),
            }
        )
    board["scorers"] = rows
    return board


def competition_shootout_ledger(
    index: pd.DataFrame,
    shootouts: pd.DataFrame | None,
    *,
    competition: str | Iterable[str],
    as_of_utc: str | pd.Timestamp | None,
) -> dict[str, Any]:
    """Per-team penalty-shootout wins and losses in one competition, as of the cutoff."""
    if as_of_utc is None:
        raise ValueError("competition_shootout_ledger requires an explicit as_of_utc cutoff")
    cutoff = _utc(as_of_utc)
    keys = _competition_match_keys(index, competition=competition, cutoff=cutoff)

    ledger: dict[str, Any] = {
        "schema_version": SCORERS_SCHEMA_VERSION,
        "competition_names": _competition_names(competition),
        "as_of_utc": _iso(cutoff),
        "scope": "internationals",
        "dataset": "shootouts",
        "shootouts_counted": 0,
        "teams": [],
    }
    if shootouts is None or shootouts.empty or not keys:
        return ledger

    played = shootouts.loc[_row_keys(shootouts).isin(keys)]
    if played.empty:
        return ledger

    records: dict[str, dict[str, int]] = {}
    for row in played.itertuples(index=False):
        winner = str(row.winner)
        loser = str(row.away_team) if winner == str(row.home_team) else str(row.home_team)
        records.setdefault(winner, {"won": 0, "lost": 0})["won"] += 1
        records.setdefault(loser, {"won": 0, "lost": 0})["lost"] += 1

    ledger["shootouts_counted"] = int(len(played))
    ledger["teams"] = [
        {"team": team, "won": tally["won"], "lost": tally["lost"]}
        for team, tally in sorted(
            records.items(), key=lambda kv: (-(kv[1]["won"] + kv[1]["lost"]), kv[0])
        )
    ]
    return ledger
