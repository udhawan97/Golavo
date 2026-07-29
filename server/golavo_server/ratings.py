"""Serve the Golavo Ratings Elo tables from the active local index.

Two scopes, one engine. National teams are ranked as a single pool because they
meet across confederations; club sides are ranked per competition, because the
leagues in the index meet only through the thin 2020+ UEFA fixtures and a pooled
table would rank a Bundesliga side against a La Liga side on almost no evidence
connecting them.
"""

from __future__ import annotations

from typing import Any

from golavo_server import matches
from golavo_server.outlook import _minute

_RATINGS = matches.SnapshotReader("international ratings", stamps_provenance=True)
_CLUB_RATINGS = matches.SnapshotReader("club ratings", stamps_provenance=True)


def reset_cache() -> None:
    _RATINGS.reset()
    _CLUB_RATINGS.reset()


def _floor(top_n: int) -> int:
    return max(1, min(int(top_n), 200))


def get_international_ratings(*, as_of_utc: str | None = None, top_n: int = 40) -> dict[str, Any]:
    """The men's international Elo table, cut off at ``as_of_utc`` (per-minute cached)."""
    cutoff = _minute(as_of_utc)
    floor = _floor(top_n)

    def compute(snapshot: matches.IndexSnapshot) -> dict[str, Any]:
        from golavo_core.ratings import INTERNATIONAL_SCOPE, elo_trajectory

        frame = snapshot.frame
        internationals = frame[frame["source_kind"].astype("string").eq("international")]
        return elo_trajectory(
            internationals, as_of_utc=cutoff, top_n=floor, scope=INTERNATIONAL_SCOPE
        )

    return _RATINGS.read(compute, key=(cutoff, floor))


def get_club_ratings(
    competition_id: str, *, as_of_utc: str | None = None, top_n: int = 40
) -> dict[str, Any]:
    """One club competition's Elo table, cut off at ``as_of_utc`` (per-minute cached).

    Raises ``LookupError`` for a competition the catalog does not declare and
    ``ValueError`` for one whose teams are not clubs — serving national sides
    under a route named 'club' would mislabel the table it returns.
    """
    from golavo_core.competitions import competition_by_id

    competition = competition_by_id(competition_id)
    if competition is None:
        raise LookupError(f"unknown competition_id: {competition_id!r}")
    if competition["team_scope"] != "club":
        raise ValueError(
            f"{competition_id!r} is a {competition['team_scope']} competition; "
            "club ratings cover club competitions only"
        )
    source_names = set(competition["source_competition_names"])
    cutoff = _minute(as_of_utc)
    floor = _floor(top_n)

    def compute(snapshot: matches.IndexSnapshot) -> dict[str, Any]:
        from golavo_core.ratings import elo_trajectory

        frame = snapshot.frame
        rows = frame[frame["competition"].isin(source_names)]
        return elo_trajectory(rows, as_of_utc=cutoff, top_n=floor, scope=competition_id)

    return _CLUB_RATINGS.read(compute, key=(competition_id, cutoff, floor))
