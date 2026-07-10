"""Pinned sourcepack ingestion. Runtime ingestion performs no network I/O."""

from .snapshot import (
    assert_no_future_rows,
    load_match_table,
    snapshot_descriptor,
    training_rows,
    validate_pack,
    write_parquet,
)

__all__ = [
    "assert_no_future_rows",
    "load_match_table",
    "snapshot_descriptor",
    "training_rows",
    "validate_pack",
    "write_parquet",
]
