"""Server wrapper for the World Cup retrospective — cached, never persisted.

Both layers resolve the SAME active pack. The story layer reads the index frame;
the trust layer re-runs the evaluation fold against the pack directory. Reading
the committed eval summary instead would report a different match count than the
story layer computed, which is exactly the staleness this surface avoids.

v1 caching is L1 (in-process memo) only. It is an accelerator, never a
dependency: a miss always recomputes, and a failed publish never fails the
request. There is deliberately no disk cache here — the story layer costs
minutes per family fit, which is the L1 bound below, and evaluate() costs ~30s;
neither is cheap enough to recompute per request, but persisting either across
restarts is Task 3+'s to reconsider, not v1's.
"""

from __future__ import annotations

from typing import Any

from golavo_server import matches, seal

_CACHE: dict[tuple[Any, ...], dict[str, Any]] = {}
_CACHE_ORDER: list[tuple[Any, ...]] = []
_CACHE_MAX = 4  # each entry costs minutes to build; keep a few generations

_MARTJ42 = "martj42-international-results"


def reset_cache() -> None:
    """Drop the in-process memo (tests / after an index repoint)."""
    _CACHE.clear()
    _CACHE_ORDER.clear()


def _remember(key: tuple[Any, ...], value: dict[str, Any]) -> None:
    _CACHE[key] = value
    _CACHE_ORDER.append(key)
    while len(_CACHE_ORDER) > _CACHE_MAX:
        _CACHE.pop(_CACHE_ORDER.pop(0), None)


def _story(frame: Any, progress: Any, is_cancelled: Any) -> dict[str, Any]:
    from golavo_core.retrospective import world_cup_2026_retrospective

    return world_cup_2026_retrospective(frame, progress=progress, is_cancelled=is_cancelled)


def _trust(pack_dir: Any) -> dict[str, Any] | None:
    """The WC2026 fold's report card, recomputed on the active pack.

    report_cards holds one entry PER COMPETITION (today: FIFA World Cup and UEFA
    Euro) — the first entry is not guaranteed to be the World Cup, so the card is
    selected by its competition field rather than taken positionally.
    """
    from golavo_core.evaluation import evaluate

    summary = evaluate(pack_dir)
    for card in summary.get("report_cards", []):
        if card.get("competition") == "FIFA World Cup":
            return card
    return None


def build(
    *,
    progress: Any = None,
    is_cancelled: Any = None,
) -> dict[str, Any]:
    """The full two-layer retrospective for the active index and pack."""
    from golavo_core.retrospective import RetrospectiveUnavailable

    snapshot = matches.index_snapshot()
    pack_dir = seal.resolve_pack_dir(_MARTJ42, "international")
    pack_name = pack_dir.name if pack_dir is not None else "unknown"
    key = (snapshot.fingerprint, snapshot.epoch, pack_name)

    cached = _CACHE.get(key)
    if cached is not None and matches.snapshot_is_current(snapshot):
        return cached

    try:
        story = _story(snapshot.frame, progress, is_cancelled)
    except RetrospectiveUnavailable as exc:
        story = {
            "schema_version": "0.1.0",
            "status": "unavailable",
            "label": (
                "Tournament retrospective — every match backtested at its own pre-kickoff "
                "cutoff. A backtest, not a sealed record."
            ),
            "tournament_id": "worldcup-2026",
            "tournament_name": "2026 FIFA World Cup",
            "ledger_status": "never_persisted_or_scored_as_a_seal",
            "reason": str(exc),
            "coverage": {"status": "partial", "scored": 0, "pending": 0, "note": str(exc)},
            "matches": [],
            "biggest_surprises": [],
        }

    result = dict(story)
    result["trust"] = _trust(pack_dir) if pack_dir is not None else None
    result["provenance"] = {"index_sha256": snapshot.fingerprint, "pack": pack_name}

    matches.apply_if_snapshot_current(snapshot, lambda: _remember(key, result))
    return result
