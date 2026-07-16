"""Server wrapper for the World Cup retrospective — cached, never persisted.

Two layers, one snapshot. The STORY layer replays every 2026 World Cup match at
its own kickoff-1s cutoff; the TRUST layer answers "did these models have skill?"
by recomputing the WC2026 evaluation fold against the pack directory. They must
never silently describe different data — that is the whole reason the feature is
built this way, so both layers resolve the SAME active pack and the response
stamps that pack's own snapshot digest for a reader to audit against.

The trust layer is the WC2026 FOLD, never evaluate()'s "FIFA World Cup" REPORT
CARD. report_cards are grouped per COMPETITION and evaluation.FOLDS carries two
World Cup folds, so that card aggregates WC2022 and WC2026 into a single
161-match, 2022-11-20..2026-07-19 verdict. The story is exclusively 2026;
attaching a two-tournament card to it would overclaim. Reading the committed
eval summary instead would be stale for the same class of reason.

v1 caching is L1 (in-process memo) only. It is an accelerator, never a
dependency: a miss always recomputes, and a failed publish never fails the
request. The trust layer is an accelerator in the same sense — no failure there
may fail the request, only downgrade trust to a typed unavailable state. There
is deliberately no disk cache here — the story layer costs minutes per family
fit, which is the L1 bound below, and evaluate() costs ~30s; neither is cheap
enough to recompute per request, but persisting either across restarts is
Task 3+'s to reconsider, not v1's.
"""

from __future__ import annotations

from typing import Any

from golavo_server import matches, seal

_CACHE: dict[tuple[Any, ...], dict[str, Any]] = {}
_CACHE_ORDER: list[tuple[Any, ...]] = []
_CACHE_MAX = 4  # each entry costs minutes to build; keep a few generations

_MARTJ42 = "martj42-international-results"

# The story layer is exclusively this fold's tournament, so the trust layer must
# be exactly this fold — not its competition, which spans two World Cups.
_TRUST_FOLD_ID = "WC2026"

# Refresh activation is infrequent and serialized, so three generation retries
# are ample while keeping a pathological repoint loop fail-closed. The window a
# repoint can strand work in is minutes wide here (the story layer's cost), far
# wider than on the analysis path, so the retry matters more, not less.
_MAX_ATTEMPTS = 3


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


def _unavailable_story(reason: str) -> dict[str, Any]:
    """The typed no-story envelope. Version and label come from core.

    Hardcoding them here would let a core bump move core and the schema while
    this surface silently kept emitting the old version.
    """
    from golavo_core.retrospective import RETROSPECTIVE_LABEL, RETROSPECTIVE_SCHEMA_VERSION

    return {
        "schema_version": RETROSPECTIVE_SCHEMA_VERSION,
        "status": "unavailable",
        "label": RETROSPECTIVE_LABEL,
        "tournament_id": "worldcup-2026",
        "tournament_name": "2026 FIFA World Cup",
        "ledger_status": "never_persisted_or_scored_as_a_seal",
        "reason": reason,
        "coverage": {"status": "partial", "scored": 0, "pending": 0, "note": reason},
        "matches": [],
        "biggest_surprises": [],
    }


def _trust_unavailable(cause: str, reason: str) -> dict[str, Any]:
    """A missing trust layer is a typed state with a machine-readable cause.

    Never a bare null: "we could not measure skill" and "skill was measured and
    it is poor" must never look alike, and the three ways trust can go missing
    must stay distinguishable without parsing prose.
    """
    return {"status": "unavailable", "cause": cause, "reason": reason}


def _pack_stamp(pack_dir: Any) -> str:
    """A string that identifies WHICH pack snapshot both layers were handed.

    pack_dir.name is not an identity: every refreshed generation's pack is named
    "internationals", so the name cannot tell one generation's pack from another,
    nor from the committed bundle's. That is the case this stamp exists to catch
    — when the active generation's index meta schema_version mismatches,
    _resolve_index_paths() falls back to the committed bundle index while
    resolve_pack_dir() still returns the generation's pack, so story and trust
    would describe different snapshots with nothing in the response to show it.

    Never raises: the descriptor reads and validates the pack off disk. Provenance
    degrading to a stated reason is honest; a 500 is not.
    """
    if pack_dir is None:
        return "unresolved: no sourcepack resolved for this index"

    from golavo_core.ingest import snapshot_descriptor

    try:
        descriptor = snapshot_descriptor(pack_dir)
    except Exception as exc:  # noqa: BLE001 (provenance degrades; the request must not fail)
        return f"unidentified: {exc}"
    return f"{descriptor['snapshot_id']}@{descriptor['sha256']}"


def _trust(pack_dir: Any) -> dict[str, Any]:
    """The WC2026 evaluation fold, recomputed on the active pack.

    Selected out of summary["folds"] by fold_id, NOT out of summary["report_cards"]
    by competition: report_cards group per competition and FOLDS holds both WC2022
    and WC2026, so the "FIFA World Cup" card is a 161-match blend of two
    tournaments. The fold's n_matches is what lets a reader reconcile trust
    against the story's coverage.scored.

    Never raises. evaluate() legitimately raises ValueError on a pre-tournament
    snapshot (the WC2026 window has no completed rows) — precisely when the story
    layer is unavailable too, so an unguarded call here would 500 exactly the
    request the typed-unavailable envelope was built to answer. validate_pack /
    load_matches can raise on a corrupt pack for the same reason.
    """
    if pack_dir is None:
        return _trust_unavailable("no_pack", "no sourcepack resolved for this index")

    from golavo_core.evaluation import evaluate

    try:
        summary = evaluate(pack_dir)
    except Exception as exc:  # noqa: BLE001 (trust degrades; the request must not fail)
        return _trust_unavailable(
            "evaluation_failed", f"the {_TRUST_FOLD_ID} fold could not be recomputed: {exc}"
        )

    for fold in summary.get("folds", []):
        if fold.get("fold_id") == _TRUST_FOLD_ID:
            # status is the reader's discriminator and must win over any field
            # evaluation.py might ever add to a fold under the same name.
            return {**fold, "status": "available"}
    return _trust_unavailable(
        "fold_absent", f"this snapshot's evaluation carries no {_TRUST_FOLD_ID} fold"
    )


def build(
    *,
    progress: Any = None,
    is_cancelled: Any = None,
) -> dict[str, Any]:
    """The full two-layer retrospective for the active index and pack."""
    from golavo_core.retrospective import RetrospectiveUnavailable

    for _attempt in range(_MAX_ATTEMPTS):
        snapshot = matches.index_snapshot()
        pack_dir = seal.resolve_pack_dir(_MARTJ42, "international")
        # The pack's digest — not its directory name — is the third key
        # component, so the memo self-invalidates when the active pack changes
        # under an otherwise unchanged index fingerprint and epoch.
        pack = _pack_stamp(pack_dir)
        key = (snapshot.fingerprint, snapshot.epoch, pack)

        cached = _CACHE.get(key)
        if cached is not None:
            if matches.snapshot_is_current(snapshot):
                return cached
            continue

        try:
            story = _story(snapshot.frame, progress, is_cancelled)
        except RetrospectiveUnavailable as exc:
            story = _unavailable_story(str(exc))

        result = dict(story)
        result["trust"] = _trust(pack_dir)
        result["provenance"] = {"index_sha256": snapshot.fingerprint, "pack": pack}

        # Publish under the same _CACHE_LOCK that guards the epoch bump, so no
        # entry from a retired generation can survive a concurrent reset_cache().
        # A refused publish means the index moved during the minutes this took:
        # retry against the new generation rather than return retired work.
        if matches.apply_if_snapshot_current(
            snapshot, lambda key=key, result=result: _remember(key, result)
        ):
            return result

    # Exhausted. No trust or provenance is stamped: there is no settled snapshot
    # or pack left to honestly describe, and a stale stamp would be worse than none.
    return _unavailable_story(
        "retrospective paused because the verified match index changed; retry"
    )
