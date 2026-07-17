"""Golavo Ratings — an in-house Elo table for national teams, computed from CC0 results.

There is no lawful open source for the official FIFA ranking, so Golavo computes
its own rating from the same public-domain results it already trains on, using
the exact Elo update the forecast model uses (``golavo_core.models.candidates``).
It is leak-safe by construction: the table at an instant is a pure replay of the
completed matches at or before that instant, so appending later results can never
change an earlier rating.

The engine also snapshots each team's rating at monthly checkpoints in a single
pass, giving a trajectory for the trend sparkline without re-fitting per month.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from golavo_core.ingest.snapshot import _order_instants
from golavo_core.models.candidates import ELO_INITIAL, elo_match_delta

RATINGS_SCHEMA_VERSION = "0.1.0"
RATINGS_METHOD = "elo-goal-weighted-v1"
RATINGS_LABEL = (
    "Golavo Ratings — model-estimated strength from public results. "
    "Not the FIFA ranking and not an official rating."
)
DEFAULT_TOP_N = 40
TREND_CHECKPOINTS = 12


def _utc(value: str | pd.Timestamp) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    return stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")


def _iso(value: pd.Timestamp) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _month_end_checkpoints(anchor: pd.Timestamp) -> list[pd.Timestamp]:
    """Eleven prior month ends plus the exact latest-data anchor (mirrors analytics)."""
    month_start = anchor.normalize().replace(day=1)
    previous_month_end = month_start - pd.Timedelta(seconds=1)
    prior = list(pd.date_range(end=previous_month_end, periods=TREND_CHECKPOINTS - 1, freq="ME"))
    return [*prior, anchor]


def elo_trajectory(
    rows: pd.DataFrame,
    *,
    as_of_utc: str | pd.Timestamp | None,
    top_n: int = DEFAULT_TOP_N,
) -> dict[str, Any]:
    """The national-team Elo table as of ``as_of_utc`` plus each top team's history.

    Replays the shared Elo update over completed matches whose date is at or before
    the cutoff, in a single chronological pass, snapshotting ratings at monthly
    checkpoints. Returns the ranked current table (top ``top_n``) with a per-team
    checkpoint trajectory. Ties break by team name so the order is reproducible.
    """
    if as_of_utc is None:
        raise ValueError("elo_trajectory requires an explicit as_of_utc cutoff")
    cutoff = _utc(as_of_utc)

    table: dict[str, Any] = {
        "schema_version": RATINGS_SCHEMA_VERSION,
        "method": RATINGS_METHOD,
        "label": RATINGS_LABEL,
        "as_of_utc": _iso(cutoff),
        "scope": "internationals",
        "matches_counted": 0,
        "teams": [],
    }
    if rows.empty:
        return table

    # Cut off on the sharpest instant each row carries — an exact kickoff where an
    # overlay supplied one, else the date's midnight. Filtering by calendar date
    # alone would fold in a late kickoff that crosses into the next UTC day but
    # has not happened yet at the cutoff. This is the same rule training uses.
    complete = rows["is_complete"].astype("boolean").fillna(False)
    instants = _order_instants(rows)
    kept = rows.loc[complete & (instants <= cutoff)].copy()
    if kept.empty:
        return table
    kept["order_instant"] = _order_instants(kept)

    ordered = kept.sort_values(
        ["order_instant", "home_team", "away_team", "match_id"], kind="mergesort"
    )
    anchor = ordered["order_instant"].max()
    checkpoints = _month_end_checkpoints(anchor)

    ratings: dict[str, float] = {}
    counts: dict[str, int] = {}
    last_seen: dict[str, pd.Timestamp] = {}
    snapshots: list[dict[str, float]] = []
    checkpoint_index = 0

    for row in ordered.itertuples(index=False):
        instant = pd.Timestamp(row.order_instant)
        while checkpoint_index < len(checkpoints) and checkpoints[checkpoint_index] < instant:
            snapshots.append(dict(ratings))
            checkpoint_index += 1
        home, away = str(row.home_team), str(row.away_team)
        home_rating = ratings.get(home, ELO_INITIAL)
        away_rating = ratings.get(away, ELO_INITIAL)
        delta = elo_match_delta(
            home_rating, away_rating, row.home_score, row.away_score, bool(row.neutral)
        )
        ratings[home] = home_rating + delta
        ratings[away] = away_rating - delta
        for team in (home, away):
            counts[team] = counts.get(team, 0) + 1
            last_seen[team] = instant
    while checkpoint_index < len(checkpoints):
        snapshots.append(dict(ratings))
        checkpoint_index += 1

    ranked = sorted(ratings.items(), key=lambda kv: (-kv[1], kv[0]))[: max(0, top_n)]
    checkpoint_iso = [_iso(_utc(cp)) for cp in checkpoints]
    teams: list[dict[str, Any]] = []
    for rank, (team, rating) in enumerate(ranked, start=1):
        history = [
            {"as_of_utc": iso, "rating": round(float(snapshot.get(team, ELO_INITIAL)), 1)}
            for iso, snapshot in zip(checkpoint_iso, snapshots, strict=True)
        ]
        teams.append(
            {
                "rank": rank,
                "team": team,
                "rating": round(float(rating), 1),
                "matches": counts.get(team, 0),
                "last_match_date": last_seen[team].strftime("%Y-%m-%d"),
                "history": history,
            }
        )

    table["matches_counted"] = int(len(ordered))
    table["data_through_utc"] = _iso(_utc(anchor))
    table["teams"] = teams
    return table
