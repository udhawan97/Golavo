"""On-demand MatchAnalysis over the frozen index (read-only, leak-safe).

Wraps ``golavo_core.analysis.build_match_analysis`` for the API: it resolves a
match id in the committed index, scopes history to the fixture's own source (so a
shared team string cannot merge a club's form into an international fixture — the
same discipline the on-demand notebook uses), and returns a Replay (completed) or
Preview (scheduled) envelope. It never writes and never seals; the leak-safe
``kickoff - 1s`` cutoff lives in the core engine.

Results are memoised per ``(match_id, index-object-identity)``. The index frame is
immutable within a process (``matches._load_index`` caches it), so keying on its
object id means a runtime refresh — which rebuilds the frame — transparently
invalidates every cached analysis with no explicit cache-busting.
"""

from __future__ import annotations

from typing import Any

from golavo_server import matches

# Bounded per-process memo. ~64 fits is plenty for a session's cockpit browsing;
# the FIFO bound keeps a long session from growing without limit.
_CACHE: dict[tuple[str, int], dict[str, Any]] = {}
_CACHE_ORDER: list[tuple[str, int]] = []
_CACHE_MAX = 128


def _remember(key: tuple[str, int], value: dict[str, Any]) -> None:
    _CACHE[key] = value
    _CACHE_ORDER.append(key)
    while len(_CACHE_ORDER) > _CACHE_MAX:
        stale = _CACHE_ORDER.pop(0)
        _CACHE.pop(stale, None)


def reset_cache() -> None:
    """Drop the analysis memo (tests / after an index repoint)."""
    _CACHE.clear()
    _CACHE_ORDER.clear()


def match_analysis(match_id: str) -> dict[str, Any] | None:
    """MatchAnalysis envelope for one indexed match; None if the id is unknown.

    Returns ``{"available": True, "analysis": {...}}`` for a fixture we can model,
    or ``{"available": False, "reason": ...}`` when the fixture has no kickoff or
    the fit fails — always failing closed to an honest envelope rather than a 500.
    """
    from golavo_core.analysis import AnalysisUnavailable, build_match_analysis

    frame = matches._load_index()
    key = (str(match_id), id(frame))
    cached = _CACHE.get(key)
    if cached is not None:
        return cached

    sel = frame.loc[frame["match_id"].astype("string") == str(match_id)]
    if sel.empty:
        return None
    row = sel.iloc[0]

    source_id = matches._str_or_none(row["source_id"])
    scoped = frame
    if source_id is not None:
        scoped = frame.loc[frame["source_id"].astype("string") == source_id]

    match_row = {
        "match_id": str(row["match_id"]),
        "kickoff_utc": row["kickoff_utc"],
        "home_team": matches._str_or_none(row["home_team"]),
        "away_team": matches._str_or_none(row["away_team"]),
        "home_score": matches._int_or_none(row["home_score"]),
        "away_score": matches._int_or_none(row["away_score"]),
        "is_complete": bool(row["is_complete"]),
        "neutral": bool(matches._bool_or_none(row["neutral"])),
        "competition": matches._str_or_none(row["competition"]),
    }

    try:
        analysis = build_match_analysis(matches=scoped, match_row=match_row)
    except AnalysisUnavailable as exc:
        envelope: dict[str, Any] = {"available": False, "reason": str(exc), "analysis": None}
        _remember(key, envelope)
        return envelope
    except Exception as exc:  # noqa: BLE001 (fail closed; never 500 the cockpit)
        return {"available": False, "reason": f"analysis failed: {exc}", "analysis": None}

    envelope = {"available": True, "reason": None, "analysis": analysis}
    _remember(key, envelope)
    return envelope
