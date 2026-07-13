"""Pinned sourcepack ingestion. Runtime ingestion performs no network I/O."""

from pathlib import Path

import pandas as pd

from .match_index import (
    MATCH_INDEX_SCHEMA_VERSION,
    build_match_index,
    default_index_packs,
)
from .openfootball import canonical_team, load_openfootball_table
from .overlay import apply_exact_kickoffs
from .snapshot import (
    assert_no_future_rows,
    co_source_descriptors,
    load_match_table,
    snapshot_anchor_utc,
    snapshot_descriptor,
    training_rows,
    validate_pack,
    write_parquet,
)


def load_matches(pack_dir: Path) -> pd.DataFrame:
    """Load a pack into the canonical match table, dispatching on manifest source_id.

    After the source loader, any manifest-declared ``kickoffs.csv`` is spliced on so a
    pack carrying exact kickoff times (from a CC0 overlay source) sharpens its window;
    a pack without one is unchanged. Both the search index and the seal path load
    through here, so an exact kickoff reaches search, eligibility, and the sealed
    artifact identically.
    """
    manifest = validate_pack(pack_dir)
    if str(manifest.get("source_id", "")).startswith("openfootball"):
        frame = load_openfootball_table(pack_dir)
    else:
        frame = load_match_table(pack_dir)
    return apply_exact_kickoffs(frame, pack_dir, manifest)


__all__ = [
    "MATCH_INDEX_SCHEMA_VERSION",
    "apply_exact_kickoffs",
    "assert_no_future_rows",
    "build_match_index",
    "co_source_descriptors",
    "canonical_team",
    "default_index_packs",
    "load_match_table",
    "load_matches",
    "load_openfootball_table",
    "snapshot_anchor_utc",
    "snapshot_descriptor",
    "training_rows",
    "validate_pack",
    "write_parquet",
]
