"""Read model-derived competition analytics from the active local match index."""

from __future__ import annotations

from typing import Any

from golavo_server import matches


def get_competition_analytics(
    competition_id: str, *, as_of_utc: str | None = None
) -> dict[str, Any]:
    # Lazy core import preserves the sidecar's fast health/readiness startup.
    from golavo_core.analytics import competition_analytics

    for _attempt in range(3):
        snapshot = matches.index_snapshot()
        result = competition_analytics(
            snapshot.frame,
            competition_id,
            as_of_utc=as_of_utc,
        )
        if not matches.snapshot_is_current(snapshot):
            continue
        result["provenance"]["index_sha256"] = snapshot.fingerprint
        return result
    raise matches.MatchIndexUnavailable("verified match index changed during analytics; retry")
