"""Server wrapper for the World Cup retrospective — cached, never persisted.

Two layers, one snapshot — CHECKED here, never assumed. The STORY layer replays
every 2026 World Cup match at its own kickoff-1s cutoff, reading the index
Parquet; the TRUST layer answers "did these models have skill?" by recomputing
the WC2026 evaluation fold against the pack directory. Those two resolve
INDEPENDENTLY: ``matches._resolve_index_paths()`` falls back to the committed
bundle index when the active generation's index meta carries a superseded
``schema_version``, while ``seal.resolve_pack_dir()`` returns that generation's
pack unconditionally. So "both layers describe one snapshot" is not free, and
reconciling their match counts cannot buy it either — after the tournament, two
different datasets both plausibly carry 104 completed matches.

``build()`` therefore earns the claim instead of asserting it: the pack's own
manifest digest is compared against the digest the index meta records for the
same source, and the verdict is stamped in ``provenance.snapshot_agreement`` as
a typed state — verified, mismatched, or unverified with a cause. A check that
could not run never reads as agreement.

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

    # No coverage: the contract makes it optional precisely so this envelope can
    # omit it. Emitting scored/pending zeros would hand a UI the fact-shaped
    # "0 of 0 played" that this envelope exists to refuse.
    return {
        "schema_version": RETROSPECTIVE_SCHEMA_VERSION,
        "status": "unavailable",
        "label": RETROSPECTIVE_LABEL,
        "tournament_id": "worldcup-2026",
        "tournament_name": "2026 FIFA World Cup",
        "ledger_status": "never_persisted_or_scored_as_a_seal",
        "reason": reason,
        "biggest_surprises": [],
    }


def _trust_unavailable(cause: str, reason: str) -> dict[str, Any]:
    """A missing trust layer is a typed state with a machine-readable cause.

    Never a bare null: "we could not measure skill" and "skill was measured and
    it is poor" must never look alike, and the three ways trust can go missing
    must stay distinguishable without parsing prose.
    """
    return {"status": "unavailable", "cause": cause, "reason": reason}


def _pack_identity(pack_dir: Any) -> tuple[str, str | None]:
    """``(stamp, digest)`` for the pack snapshot both layers were handed.

    pack_dir.name is not an identity: every refreshed generation's pack is named
    "internationals", so the name cannot tell one generation's pack from another,
    nor from the committed bundle's. The stamp is for a reader; the digest is what
    makes the claim checkable — it is the sha256 of the pack's own manifest.json,
    the identical value the index meta records per source as ``manifest_sha256``,
    so the two layers' snapshots can be compared rather than merely stamped.

    Never raises: the descriptor reads and validates the pack off disk. Provenance
    degrading to a stated reason is honest; a 500 is not. A ``None`` digest means
    the pack could not be identified — unknown, never "it agrees".
    """
    if pack_dir is None:
        return "unresolved: no sourcepack resolved for this index", None

    from golavo_core.ingest import snapshot_descriptor

    try:
        descriptor = snapshot_descriptor(pack_dir)
    except Exception as exc:  # noqa: BLE001 (provenance degrades; the request must not fail)
        return f"unidentified: {exc}", None
    digest = str(descriptor["sha256"])
    return f"{descriptor['snapshot_id']}@{digest}", digest


def _index_pack_digest(meta_path: Any) -> str | None:
    """The martj42 pack digest THIS index frame's meta records it was built from.

    ``built_from[].manifest_sha256`` and ``snapshot_descriptor()["sha256"]`` are the
    same quantity computed the same way (the sha256 of the pack's manifest.json
    bytes), which is what makes them directly comparable.

    Never raises, and never guesses: an absent, unreadable or martj42-less meta
    returns None, which the caller must treat as "could not check" — not as
    agreement. The meta is legitimately absent in some test and source layouts.
    """
    if meta_path is None:
        return None

    import json
    from pathlib import Path

    try:
        meta = json.loads(Path(meta_path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(meta, dict):
        return None
    for entry in meta.get("built_from", []):
        if isinstance(entry, dict) and entry.get("source_id") == _MARTJ42:
            digest = entry.get("manifest_sha256")
            return str(digest) if digest else None
    return None


def _snapshot_agreement(index_digest: str | None, pack_digest: str | None) -> dict[str, Any]:
    """Whether the story's index and the trust layer's pack are provably one snapshot.

    This is the check the module docstring's claim rests on. It is deliberately a
    typed three-state and not a boolean: "the digests differ" and "we could not
    read a digest" are different facts, and collapsing the second into "false"
    would make an unverifiable page look identical to a caught mismatch — while
    collapsing it into "true" would assert exactly what could not be shown.
    """
    if pack_digest is None:
        return {
            "status": "unverified",
            "cause": "pack_unidentified",
            "reason": (
                "the active sourcepack could not be identified, so the matches and the "
                "skill fold could not be shown to come from one snapshot."
            ),
        }
    if index_digest is None:
        return {
            "status": "unverified",
            "cause": "index_provenance_unreadable",
            "reason": (
                f"the match index does not record which {_MARTJ42} pack it was built "
                "from, so the matches and the skill fold could not be shown to come "
                "from one snapshot."
            ),
            "pack_sha256": pack_digest,
        }
    if index_digest != pack_digest:
        return {
            "status": "mismatched",
            "cause": "pack_index_mismatch",
            "reason": (
                f"the backtested matches were read from an index built on pack "
                f"{index_digest}, but the skill fold was computed on pack "
                f"{pack_digest}: the two layers describe different datasets."
            ),
            "index_pack_sha256": index_digest,
            "pack_sha256": pack_digest,
        }
    return {"status": "verified", "index_pack_sha256": index_digest, "pack_sha256": pack_digest}


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
        pack, pack_digest = _pack_identity(pack_dir)
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
        # The digests are read from THIS snapshot's own meta, not the module
        # global, so a repoint racing this compute cannot make a retired index
        # vouch for the active pack.
        result["provenance"] = {
            "index_sha256": snapshot.fingerprint,
            "pack": pack,
            "snapshot_agreement": _snapshot_agreement(
                _index_pack_digest(snapshot.meta_path), pack_digest
            ),
        }

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
