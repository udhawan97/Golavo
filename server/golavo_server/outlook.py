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

    frame = matches._load_index()  # noqa: SLF001 - shared immutable index cache
    cutoff = _minute(as_of_utc)
    fingerprint = matches.index_fingerprint()
    # The content fingerprint protects production refreshes; the frame identity
    # also prevents a test/repointed loader from sharing a result with another
    # in-memory index that happens to use the same metadata file.
    key = ("worldcup-2026", fingerprint, id(frame), cutoff)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached
    try:
        result = world_cup_2026_outlook(frame, as_of_utc=cutoff)
    except OutlookUnavailable as exc:
        result = {
            "schema_version": "0.1.0",
            "status": "unavailable",
            "label": (
                "Tournament outlook — a simulation from current model fits. Not a sealed forecast."
            ),
            "tournament_id": "worldcup-2026",
            "tournament_name": "2026 FIFA World Cup",
            "as_of_utc": cutoff,
            "reason": str(exc),
            "voices": [],
            "semifinals": [],
            "provenance": {"index_sha256": fingerprint},
        }
    else:
        result["provenance"]["index_sha256"] = fingerprint
    if len(_CACHE) >= _CACHE_MAX:
        _CACHE.clear()
    _CACHE[key] = result
    return result


def season(
    competition_id: str,
    *,
    as_of_utc: str | None = None,
    season_id: str | None = None,
) -> dict[str, Any]:
    """Certified domestic season state, with simulation only when inputs pass."""
    from golavo_core.season_outlook import season_outlook

    frame = matches._load_index()  # noqa: SLF001 - shared immutable index cache
    cutoff = _minute(as_of_utc)
    fingerprint = matches.index_fingerprint()
    key = (
        f"season:{competition_id}:{season_id or 'current'}",
        fingerprint,
        id(frame),
        cutoff,
    )
    cached = _CACHE.get(key)
    if cached is not None:
        return cached
    result = season_outlook(
        frame,
        competition_id,
        as_of_utc=cutoff,
        season=season_id,
    )
    result["provenance"]["index_sha256"] = fingerprint
    if len(_CACHE) >= _CACHE_MAX:
        _CACHE.clear()
    _CACHE[key] = result
    return result
