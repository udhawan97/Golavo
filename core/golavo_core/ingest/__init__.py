"""Pinned sourcepack ingestion. Runtime ingestion performs no network I/O."""

from pathlib import Path

import pandas as pd

from .footballtxt import load_footballtxt_table, parse_footballtxt
from .match_index import (
    MATCH_INDEX_SCHEMA_VERSION,
    build_match_index,
    default_index_packs,
)
from .openfootball import canonical_team, load_openfootball_table
from .overlay import apply_exact_kickoffs
from .snapshot import (
    NoKickoffAnchor,
    TrainingView,
    assert_no_future_rows,
    co_source_descriptors,
    leak_safe_training_view,
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
    source_id = str(manifest.get("source_id", ""))
    if source_id == "openfootball-football-json":
        frame = load_openfootball_table(pack_dir)
    elif source_id == "openfootball-champions-league":
        frame = load_footballtxt_table(pack_dir)
    else:
        frame = load_match_table(pack_dir)
    return apply_exact_kickoffs(frame, pack_dir, manifest)


__all__ = [
    "MATCH_INDEX_SCHEMA_VERSION",
    "NoKickoffAnchor",
    "TrainingView",
    "apply_exact_kickoffs",
    "assert_no_future_rows",
    "build_match_index",
    "co_source_descriptors",
    "canonical_team",
    "default_index_packs",
    "leak_safe_training_view",
    "load_footballtxt_table",
    "load_match_table",
    "load_matches",
    "load_openfootball_table",
    "parse_footballtxt",
    "snapshot_anchor_utc",
    "snapshot_descriptor",
    "training_rows",
    "validate_pack",
    "write_parquet",
]
