"""Read model-derived competition analytics from the active local match index."""

from __future__ import annotations

from typing import Any

from golavo_server import matches


def get_competition_analytics(
    competition_id: str, *, as_of_utc: str | None = None
) -> dict[str, Any]:
    # Lazy core import preserves the sidecar's fast health/readiness startup.
    from golavo_core.analytics import competition_analytics

    result = competition_analytics(
        matches._load_index(),  # noqa: SLF001 - shared immutable in-process index cache
        competition_id,
        as_of_utc=as_of_utc,
    )
    result["provenance"]["index_sha256"] = matches.index_fingerprint()
    return result
