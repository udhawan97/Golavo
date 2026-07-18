"""Which bundled pack is current, for one source or for the whole index.

``packs/snapshots.json`` is an append-only registry: refreshing a source adds an
entry, it does not replace one. So "which pack is current" is a decision, and it
was made twice — once when building the search index, once when resolving the
pack a forward seal trains from. The second said "Mirrors
ingest.default_index_packs" in its docstring, which is the whole problem: search
and sealing resolving different packs is precisely what that sentence was
guarding against, and a sentence cannot guard anything.

The rule: group by source id and, for a club source, by the competition its
manifest declares; within a group the greatest snapshot anchor wins, ties broken
by pack path so a build is deterministic. The anchor prefers the upstream commit
time over our retrieval time — the data state was public from that moment,
independent of when we fetched it.

Where the pack directory *lives* differs by caller (a repo checkout nests them
under ``packs/``; a frozen build flattens them), so callers pass a ``resolve``
function. Returning ``None`` from it declines an entry, which is how a frozen
build shipping a subset skips what it does not carry — while the index build,
whose resolver never declines, still fails closed on a pack it cannot read.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .ingest.snapshot import snapshot_anchor_utc

__all__ = ["ActivePack", "active_pack", "active_packs"]

ResolvePack = Callable[[str], Path | None]


@dataclass(frozen=True)
class ActivePack:
    """The winning pack for one (source, competition) group."""

    source_id: str
    competition: str
    directory: Path


def active_packs(registry_path: Path, *, resolve: ResolvePack) -> list[ActivePack]:
    """The current pack for every (source, competition) in a snapshot registry.

    Ordered by pack path, so a caller feeding these to a deterministic build gets
    a stable build order. An absent registry yields nothing.
    """
    registry_path = Path(registry_path)
    if not registry_path.is_file():
        return []
    registry = json.loads(registry_path.read_text(encoding="utf-8"))

    best: dict[tuple[str, str], tuple[tuple[str, str], ActivePack]] = {}
    for entry in registry.get("snapshots", []):
        declared = str(entry["pack"])
        directory = resolve(declared)
        if directory is None:
            continue
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        competition = str(manifest.get("competition") or "")
        source_id = str(entry["source_id"])
        rank = (snapshot_anchor_utc(entry), declared)
        key = (source_id, competition)
        incumbent = best.get(key)
        if incumbent is None or rank > incumbent[0]:
            best[key] = (
                rank,
                ActivePack(source_id=source_id, competition=competition, directory=directory),
            )
    return sorted((pack for _rank, pack in best.values()), key=lambda p: str(p.directory))


def active_pack(
    registry_path: Path,
    *,
    resolve: ResolvePack,
    source_id: str,
    competition: str | None = None,
) -> Path | None:
    """The current pack directory for one source, or ``None``.

    ``competition`` is required to pick between club packs, because one club
    source id is shared across every league it publishes.
    """
    for pack in active_packs(registry_path, resolve=resolve):
        if pack.source_id != source_id:
            continue
        if competition is not None and pack.competition != competition:
            continue
        return pack.directory
    return None
