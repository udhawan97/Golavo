"""Read model-derived competition analytics from the active local match index."""

from __future__ import annotations

from typing import Any

from golavo_server import matches
from golavo_server.outlook import _minute

_ANALYTICS = matches.SnapshotReader("competition analytics", stamps_provenance=True)


def reset_cache() -> None:
    _ANALYTICS.reset()


def get_competition_analytics(
    competition_id: str, *, as_of_utc: str | None = None
) -> dict[str, Any]:
    # The core reads "now" when handed no as-of, so the cutoff is resolved to the
    # minute HERE and carried in the key: a memo keyed on a bare None would freeze
    # one moment's answer and serve it as if it were current.
    cutoff = _minute(as_of_utc)

    def compute(snapshot: matches.IndexSnapshot) -> dict[str, Any]:
        # Lazy core import preserves the sidecar's fast health/readiness startup.
        from golavo_core.analytics import competition_analytics

        return competition_analytics(snapshot.frame, competition_id, as_of_utc=cutoff)

    return _ANALYTICS.read(compute, key=(competition_id, cutoff))
