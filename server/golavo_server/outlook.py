"""Read-only tournament and season outlooks over the active local index."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from golavo_server import matches

_CACHE: dict[tuple[str, str, int, str], dict[str, Any]] = {}
_CACHE_MAX = 32


def reset_cache() -> None:
    _CACHE.clear()


def _minute(value: str | None) -> str:
    if value is not None:
        return value
    return datetime.now(UTC).replace(second=0, microsecond=0).isoformat().replace("+00:00", "Z")


def world_cup_2026(*, as_of_utc: str | None = None) -> dict[str, Any]:
    """Current exact-enumeration World Cup outlook, never a ledger artifact."""
    from golavo_core.outlook import OutlookUnavailable, world_cup_2026_outlook

    cutoff = _minute(as_of_utc)
    for _attempt in range(3):
        snapshot = matches.index_snapshot()
        # The content fingerprint protects production refreshes; the epoch also
        # prevents a reset/repoint from accepting work begun on a retired frame.
        key = ("worldcup-2026", snapshot.fingerprint, snapshot.epoch, cutoff)
        cached = _CACHE.get(key)
        if cached is not None:
            if matches.snapshot_is_current(snapshot):
                return cached
            continue
        try:
            result = world_cup_2026_outlook(snapshot.frame, as_of_utc=cutoff)
        except OutlookUnavailable as exc:
            result = {
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
                "provenance": {"index_sha256": snapshot.fingerprint},
            }
        else:
            result["provenance"]["index_sha256"] = snapshot.fingerprint

        def publish(key=key, result=result) -> None:
            if len(_CACHE) >= _CACHE_MAX:
                _CACHE.clear()
            _CACHE[key] = result

        if matches.apply_if_snapshot_current(snapshot, publish):
            return result
    raise matches.MatchIndexUnavailable("verified match index changed during outlook; retry")


def season(
    competition_id: str,
    *,
    as_of_utc: str | None = None,
    season_id: str | None = None,
) -> dict[str, Any]:
    """Certified domestic season state, with simulation only when inputs pass."""
    from golavo_core.season_outlook import season_outlook

    cutoff = _minute(as_of_utc)
    for _attempt in range(3):
        snapshot = matches.index_snapshot()
        key = (
            f"season:{competition_id}:{season_id or 'current'}",
            snapshot.fingerprint,
            snapshot.epoch,
            cutoff,
        )
        cached = _CACHE.get(key)
        if cached is not None:
            if matches.snapshot_is_current(snapshot):
                return cached
            continue
        result = season_outlook(
            snapshot.frame,
            competition_id,
            as_of_utc=cutoff,
            season=season_id,
        )
        result["provenance"]["index_sha256"] = snapshot.fingerprint

        def publish(key=key, result=result) -> None:
            if len(_CACHE) >= _CACHE_MAX:
                _CACHE.clear()
            _CACHE[key] = result

        if matches.apply_if_snapshot_current(snapshot, publish):
            return result
    raise matches.MatchIndexUnavailable("verified match index changed during outlook; retry")
