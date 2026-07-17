"""Serve the Golavo Ratings national-team Elo table from the active local index."""

from __future__ import annotations

from typing import Any

from golavo_server import matches
from golavo_server.outlook import _minute

_RATINGS = matches.SnapshotReader("international ratings", stamps_provenance=True)


def reset_cache() -> None:
    _RATINGS.reset()


def get_international_ratings(*, as_of_utc: str | None = None, top_n: int = 40) -> dict[str, Any]:
    """The men's international Elo table, cut off at ``as_of_utc`` (per-minute cached)."""
    cutoff = _minute(as_of_utc)
    floor = max(1, min(int(top_n), 200))

    def compute(snapshot: matches.IndexSnapshot) -> dict[str, Any]:
        from golavo_core.ratings import elo_trajectory

        frame = snapshot.frame
        internationals = frame[frame["source_kind"].astype("string").eq("international")]
        return elo_trajectory(internationals, as_of_utc=cutoff, top_n=floor)

    return _RATINGS.read(compute, key=(cutoff, floor))
