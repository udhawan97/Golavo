"""Read-only tournament and season outlooks over the active local index."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from golavo_server import matches

_WORLD_CUP = matches.SnapshotReader("tournament outlook", stamps_provenance=True)
_SEASON = matches.SnapshotReader("season outlook", stamps_provenance=True)


def reset_cache() -> None:
    """Kept for callers that reset this module by name; the readers own the memo."""
    _WORLD_CUP.reset()
    _SEASON.reset()


def _minute(value: str | None) -> str:
    if value is not None:
        return value
    return datetime.now(UTC).replace(second=0, microsecond=0).isoformat().replace("+00:00", "Z")


def world_cup_2026(*, as_of_utc: str | None = None) -> dict[str, Any]:
    """Current exact-enumeration World Cup outlook, never a ledger artifact."""
    from golavo_core.outlook import OutlookUnavailable, world_cup_2026_outlook

    cutoff = _minute(as_of_utc)

    def compute(snapshot: matches.IndexSnapshot) -> dict[str, Any]:
        try:
            return world_cup_2026_outlook(snapshot.frame, as_of_utc=cutoff)
        except OutlookUnavailable as exc:
            return {
                "schema_version": "0.1.0",
                "status": "unavailable",
                "label": (
                    "Tournament outlook — a simulation from current model fits. "
                    "Not a sealed forecast."
                ),
                "tournament_id": "worldcup-2026",
                "tournament_name": "2026 FIFA World Cup",
                "as_of_utc": cutoff,
                "reason": str(exc),
                "voices": [],
                "semifinals": [],
            }

    return _WORLD_CUP.read(compute, key=("worldcup-2026", cutoff))


def season(
    competition_id: str,
    *,
    as_of_utc: str | None = None,
    season_id: str | None = None,
    forced_results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Certified domestic season state, with simulation only when inputs pass."""
    from golavo_core.season_outlook import season_outlook

    cutoff = _minute(as_of_utc)

    def compute(snapshot: matches.IndexSnapshot) -> dict[str, Any]:
        return season_outlook(
            snapshot.frame,
            competition_id,
            as_of_utc=cutoff,
            season=season_id,
            forced_results=forced_results,
        )

    scenario_key = tuple(
        (str(item.get("match_id")), item.get("home_score"), item.get("away_score"))
        for item in (forced_results or [])
    )
    return _SEASON.read(
        compute,
        key=(f"season:{competition_id}:{season_id or 'current'}", cutoff, scenario_key),
    )
