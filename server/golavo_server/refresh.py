"""Pull a fresh internationals snapshot into a writable location so a newly
published fixture becomes searchable AND sealable in-app — without losing the
bundled club history.

Golavo ships a complete, read-only match index (martj42 internationals + five
openfootball club leagues) and, for forward seals, only ONE refreshable source:
the martj42 internationals pack. It is the single source that (a) maps to one
pinned CC0 pack and (b) gains genuinely new *fixtures* upstream. A refresh
therefore rebuilds only the internationals side of the index from a fresh pack
and carries the club rows over from the bundled index verbatim — so the
refreshed index stays whole even though the frozen app bundles no club packs.

This module produces the refreshed *bytes* deterministically (same inputs ->
identical Parquet), so it is unit-testable with no process state and no network.
Pinning the upstream snapshot and repointing the live sidecar at the result are
the caller's job; keeping that split is what makes the hard part testable.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from golavo_core.ingest.match_index import (
    INDEX_COLUMNS,
    MATCH_INDEX_SCHEMA_VERSION,
    build_match_index,
)

_CLUB_KIND = "club"
_INTERNATIONAL_KIND = "international"


class RefreshError(Exception):
    """A refresh could not produce a complete, consistent index."""


def merge_refreshed_index(
    fresh_intl_pack: Path, bundled_index_path: Path, target_dir: Path
) -> Path:
    """Write a complete refreshed match index into ``target_dir``.

    Rebuilds the internationals index (rows + goalscorers/shootouts + aliases)
    from ``fresh_intl_pack`` straight into ``target_dir``, then splices in the
    club rows carried over verbatim from the bundled complete index at
    ``bundled_index_path``. The result is a single Parquet honouring the exact
    ``INDEX_COLUMNS`` contract, its match ids still unique across sources, and a
    meta sidecar whose digest matches the merged bytes. Deterministic: identical
    inputs yield byte-identical output.

    Raises ``RefreshError`` if the fresh pack is not an internationals source or
    if the merge would collide two sources' ids.
    """
    import pandas as pd

    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_index = target_dir / "matches_index.parquet"

    # 1. Fresh internationals index + its side tables/aliases, straight into
    #    target_dir. This is the only side that gains new fixtures upstream.
    build_match_index([Path(fresh_intl_pack)], target_index)
    intl = pd.read_parquet(target_index)
    if not (intl["source_kind"] == _INTERNATIONAL_KIND).all():
        raise RefreshError(
            "fresh pack is not a pure internationals source; refusing to refresh"
        )

    # 2. Carry the club history over from the bundled index, untouched — the
    #    frozen app bundles no club packs, so this is how it stays complete.
    bundled = pd.read_parquet(Path(bundled_index_path))
    club = bundled[bundled["source_kind"] == _CLUB_KIND]

    merged = (
        pd.concat([intl, club[INDEX_COLUMNS]], ignore_index=True)
        .sort_values(["kickoff_utc", "match_id"], kind="mergesort")
        .reset_index(drop=True)[INDEX_COLUMNS]
    )
    dups = merged["match_id"][merged["match_id"].duplicated(keep=False)]
    if not dups.empty:
        raise RefreshError(
            "match_id collision merging refreshed internationals with club "
            f"history: {sorted(dups.unique())[:10]}"
        )

    # 3. Overwrite the intl-only Parquet with the merged whole + honest meta.
    #    build_match_index already left the fresh internationals side tables and
    #    alias map in target_dir; those are intl-only, so the fresh copies stand.
    merged.to_parquet(target_index, index=False, engine="pyarrow", compression="zstd")
    meta = {
        "schema_version": MATCH_INDEX_SCHEMA_VERSION,
        "row_count": int(len(merged)),
        "parquet_sha256": hashlib.sha256(target_index.read_bytes()).hexdigest(),
        "refreshed": True,
        "internationals_pack": Path(fresh_intl_pack).name,
        "club_rows_from": Path(bundled_index_path).name,
    }
    (target_dir / "matches_index.meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return target_index
