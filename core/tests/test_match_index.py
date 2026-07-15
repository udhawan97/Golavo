"""Tests for the committed match search index builder.

The index folds every bundled CC0 pack into one deterministic Parquet plus side
tables. These tests pin the properties a later search/notebook consumer relies
on: a fail-closed license gate, per-pack match ids preserved across the merge,
the exact column contract, byte-reproducible output, and the anchor-based pack
selection. Fixtures are tiny synthetic packs with hashed manifests so nothing
here depends on the multi-megabyte real packs.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest
from golavo_core.ingest import (
    MATCH_INDEX_SCHEMA_VERSION,
    build_match_index,
    default_index_packs,
)
from golavo_core.ingest.match_index import INDEX_COLUMNS, normalize

_HEADER = "date,home_team,away_team,home_score,away_score,tournament,city,country,neutral\n"


def _write_pack(
    pack_dir: Path,
    source_id: str,
    result_rows: str,
    *,
    license: str = "CC0-1.0",
    competition: str | None = None,
) -> Path:
    """Write a minimal martj42-format pack with a hash-correct manifest."""
    pack_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "results.csv": _HEADER + result_rows,
        "former_names.csv": "current,former,start_date,end_date\n",
    }
    entries = []
    for name, content in files.items():
        (pack_dir / name).write_text(content, encoding="utf-8")
        entries.append({"name": name, "sha256": hashlib.sha256(content.encode()).hexdigest()})
    manifest: dict = {
        "files": entries,
        "license": license,
        "source_id": source_id,
        "upstream_ref": "0" * 40,
        "url": "https://example.test",
        "retrieved_at_utc": "2026-01-01T00:00:00Z",
    }
    if competition is not None:
        manifest["competition"] = competition
    (pack_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return pack_dir


def _two_packs(tmp_path: Path) -> list[Path]:
    intl = _write_pack(
        tmp_path / "martj42-mini",
        "martj42-international-results",
        "2020-01-01,Atlético,Côte d'Ivoire,1,0,Friendly,Madrid,Spain,FALSE\n"
        "2019-06-01,Brazil,Argentina,2,2,Copa,Rio,Brazil,FALSE\n",
    )
    club = _write_pack(
        tmp_path / "league-mini",
        "synthetic-league",
        "2021-08-14,Arsenal,Chelsea,3,1,Synthetic League,London,England,FALSE\n"
        "2021-08-21,Chelsea,Arsenal,0,0,Synthetic League,London,England,FALSE\n",
        competition="Synthetic League",
    )
    return [intl, club]


def test_build_index_columns_kinds_and_ids(tmp_path: Path) -> None:
    out = tmp_path / "out" / "matches_index.parquet"
    build_match_index(_two_packs(tmp_path), out)
    df = pd.read_parquet(out)

    # Exact, ordered column contract the server search workstream binds to.
    assert list(df.columns) == INDEX_COLUMNS
    assert len(df) == 4
    assert df["match_id"].is_unique

    # Typed for a search/notebook consumer.
    assert pd.api.types.is_string_dtype(df["home_team"])
    assert pd.api.types.is_integer_dtype(df["home_score"])  # nullable Int16
    assert str(df["ht_home_score"].dtype) == "Int16"
    assert str(df["ht_away_score"].dtype) == "Int16"
    assert df.loc[df["source_kind"] == "international", "ht_home_score"].isna().all()
    assert pd.api.types.is_bool_dtype(df["is_complete"])
    assert df["kickoff_precision"].eq("day").all()

    # source_kind is derived purely from the source_id prefix.
    kinds = dict(zip(df["source_id"], df["source_kind"], strict=True))
    assert kinds["martj42-international-results"] == "international"
    assert kinds["synthetic-league"] == "club"

    # competition mirrors tournament; norms fold diacritics.
    assert (df["competition"] == df["tournament"]).all()
    atletico = df.loc[df["home_team"] == "Atlético"].iloc[0]
    assert atletico["home_norm"] == "atletico"
    assert atletico["away_norm"] == "cote d'ivoire"

    meta = json.loads((out.parent / "matches_index.meta.json").read_text())
    assert meta["schema_version"] == MATCH_INDEX_SCHEMA_VERSION
    assert meta["row_count"] == 4
    # built_from is sorted by (source_id, pack): martj42-* sorts before synthetic-*.
    assert [b["pack"] for b in meta["built_from"]] == ["martj42-mini", "league-mini"]
    assert meta["parquet_sha256"] == hashlib.sha256(out.read_bytes()).hexdigest()


def test_build_index_is_byte_deterministic(tmp_path: Path) -> None:
    packs = _two_packs(tmp_path)
    first = tmp_path / "a" / "matches_index.parquet"
    second = tmp_path / "b" / "matches_index.parquet"
    build_match_index(packs, first)
    build_match_index(packs, second)
    assert first.read_bytes() == second.read_bytes()
    meta_a = json.loads((first.parent / "matches_index.meta.json").read_text())
    meta_b = json.loads((second.parent / "matches_index.meta.json").read_text())
    assert meta_a["parquet_sha256"] == meta_b["parquet_sha256"]


def test_license_gate_is_fail_closed(tmp_path: Path) -> None:
    pack = _write_pack(
        tmp_path / "odbl-pack",
        "synthetic-league",
        "2021-08-14,Arsenal,Chelsea,3,1,Synthetic League,London,England,FALSE\n",
        license="ODbL-1.0",
    )
    with pytest.raises(ValueError, match="not cleared for the bundled match index"):
        build_match_index([pack], tmp_path / "out" / "matches_index.parquet")


def test_match_ids_are_preserved_not_rederived(tmp_path: Path) -> None:
    """Each pack's own ids must survive the merge verbatim (identity per source)."""
    from golavo_core.ingest import load_matches

    packs = _two_packs(tmp_path)
    expected = set()
    for pack in packs:
        expected |= set(load_matches(pack)["match_id"])
    out = tmp_path / "out" / "matches_index.parquet"
    build_match_index(packs, out)
    assert set(pd.read_parquet(out)["match_id"]) == expected


def test_default_index_packs_keeps_later_anchor(tmp_path: Path) -> None:
    older = _write_pack(tmp_path / "packs" / "src-old", "src", _HEADER_ROW())
    newer = _write_pack(tmp_path / "packs" / "src-new", "src", _HEADER_ROW())
    registry = {
        "schema_version": "0.1.0",
        "snapshots": [
            {
                "pack": "packs/src-old",
                "source_id": "src",
                "retrieved_at_utc": "2026-01-01T00:00:00Z",
                "upstream_committed_at_utc": None,
            },
            {
                "pack": "packs/src-new",
                "source_id": "src",
                "retrieved_at_utc": "2026-02-01T00:00:00Z",
                "upstream_committed_at_utc": None,
            },
        ],
    }
    (tmp_path / "packs" / "snapshots.json").write_text(json.dumps(registry), encoding="utf-8")
    selected = default_index_packs(tmp_path)
    assert selected == [newer.resolve()]
    assert older.resolve() not in selected


def test_normalize_folds_diacritics() -> None:
    assert normalize("Atlético") == "atletico"
    assert normalize("Côte d'Ivoire") == "cote d'ivoire"
    assert normalize("  München  ") == "munchen"


def _HEADER_ROW() -> str:
    return "2020-01-01,A,B,1,0,Friendly,City,Country,FALSE\n"
