"""Serve competition Golden Boot and shootout boards from the active local index.

Scorer and shootout data ship only with the internationals side tables, so a
board is offered only for an international competition. A club competition is a
known id with no scorer coverage, which is reported as a typed unavailable board
rather than an error — the same "first-class unknown" the rest of the app uses.
"""

from __future__ import annotations

from typing import Any

from golavo_core.competitions import competition_by_id

from golavo_server import matches
from golavo_server.outlook import _minute

_SCORERS = matches.SnapshotReader("competition scorers", stamps_provenance=True)


def reset_cache() -> None:
    _SCORERS.reset()


def _resolve(competition_id: str) -> dict[str, Any]:
    entry = competition_by_id(competition_id)
    if entry is None:
        raise ValueError(f"unknown competition_id: {competition_id}")
    return entry


def _unavailable(entry: dict[str, Any], cutoff: str) -> dict[str, Any]:
    """A valid competition with no scorer coverage — honest, not an error."""
    return {
        "schema_version": "0.1.0",
        "competition_id": entry["competition_id"],
        "competition_name": entry["display_name"],
        "as_of_utc": cutoff,
        "scope": "unavailable",
        "reason": "Scorer and shootout data are available for international competitions only.",
        "matches_counted": 0,
        "scorers": [],
        "shootouts_counted": 0,
        "teams": [],
    }


def get_competition_scorers(
    competition_id: str, *, as_of_utc: str | None = None, min_goals: int = 1
) -> dict[str, Any]:
    """The competition's leading scorers and shootout ledger, cut off at ``as_of_utc``."""
    entry = _resolve(competition_id)
    cutoff = _minute(as_of_utc)

    if entry["team_scope"] != "international":
        return _unavailable(entry, cutoff)

    names = tuple(entry["source_competition_names"])
    floor = max(1, int(min_goals))

    def compute(snapshot: matches.IndexSnapshot) -> dict[str, Any]:
        from golavo_core.scorers import competition_shootout_ledger, competition_top_scorers

        # Read the side tables of THIS snapshot's generation, so a refreshed
        # index serves the refreshed scorers rather than the bundled ones.
        goalscorers, shootouts = matches._load_side_tables(
            snapshot.goalscorers_path, snapshot.shootouts_path
        )
        board = competition_top_scorers(
            snapshot.frame, goalscorers, competition=names, as_of_utc=cutoff, min_goals=floor
        )
        ledger = competition_shootout_ledger(
            snapshot.frame, shootouts, competition=names, as_of_utc=cutoff
        )
        return {
            "schema_version": board["schema_version"],
            "competition_id": entry["competition_id"],
            "competition_name": entry["display_name"],
            "as_of_utc": board["as_of_utc"],
            "scope": "internationals",
            "min_goals": board["min_goals"],
            "matches_counted": board["matches_counted"],
            "scorers": board["scorers"],
            "shootouts_counted": ledger["shootouts_counted"],
            "teams": ledger["teams"],
        }

    return _SCORERS.read(compute, key=(competition_id, cutoff, floor))
