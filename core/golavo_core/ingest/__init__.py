"""Pinned sourcepack ingestion. Runtime ingestion performs no network I/O."""

from pathlib import Path

import pandas as pd

from .match_index import (
    MATCH_INDEX_SCHEMA_VERSION,
    build_match_index,
    default_index_packs,
)
from .openfootball import canonical_team, load_openfootball_table
from .snapshot import (
    assert_no_future_rows,
    load_match_table,
    snapshot_anchor_utc,
    snapshot_descriptor,
    training_rows,
    validate_pack,
    write_parquet,
)


def load_matches(pack_dir: Path) -> pd.DataFrame:
    """Load a pack into the canonical match table, dispatching on manifest source_id."""
    manifest = validate_pack(pack_dir)
    if str(manifest.get("source_id", "")).startswith("openfootball"):
        return load_openfootball_table(pack_dir)
    return load_match_table(pack_dir)


__all__ = [
    "MATCH_INDEX_SCHEMA_VERSION",
    "assert_no_future_rows",
    "build_match_index",
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
