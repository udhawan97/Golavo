"""Tests for the runtime data-refresh index merge.

The refresh rebuilds the internationals side of the match index from a fresh CC0
pack and carries the club history over from the bundled index verbatim. These
tests pin the properties the in-app "pull it in" flow depends on: a newly
published fixture becomes searchable, the club leagues survive a refresh they
were never rebuilt from, stale internationals never linger, and the output is
byte-deterministic (so a refresh is reproducible and cache-safe).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest
from golavo_core.ingest import build_match_index
from golavo_core.ingest.match_index import INDEX_COLUMNS
from golavo_server.refresh import RefreshError, merge_refreshed_index

_HEADER = "date,home_team,away_team,home_score,away_score,tournament,city,country,neutral\n"


def _write_pack(
    pack_dir: Path, source_id: str, rows: str, *, competition: str | None = None
) -> Path:
    """Write a minimal martj42-format CC0 pack with a hash-correct manifest."""
    pack_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "results.csv": _HEADER + rows,
        "former_names.csv": "current,former,start_date,end_date\n",
    }
    entries = []
    for name, content in files.items():
        (pack_dir / name).write_text(content, encoding="utf-8")
        entries.append({"name": name, "sha256": hashlib.sha256(content.encode()).hexdigest()})
    manifest: dict = {
        "files": entries,
        "license": "CC0-1.0",
        "source_id": source_id,
        "upstream_ref": "0" * 40,
        "url": "https://example.test",
        "retrieved_at_utc": "2026-01-01T00:00:00Z",
    }
    if competition is not None:
        manifest["competition"] = competition
    (pack_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return pack_dir


def _bundled_index(tmp_path: Path, intl_rows: str) -> Path:
    """A complete bundled index: an internationals pack + one club league."""
    intl = _write_pack(tmp_path / "intl-old", "martj42-international-results", intl_rows)
    # A non-martj42 source_id parses as the default CSV format yet classifies as
    # source_kind="club" (the real openfootball JSON loader can't read this CSV).
    club = _write_pack(
        tmp_path / "club",
        "synthetic-league",
        "2021-08-14,Arsenal,Chelsea,3,1,Premier League,London,England,FALSE\n"
        "2021-08-21,Chelsea,Arsenal,0,0,Premier League,London,England,FALSE\n",
        competition="Premier League",
    )
    out = tmp_path / "bundled" / "matches_index.parquet"
    build_match_index([intl, club], out)
    return out


def test_refresh_keeps_club_history_and_adds_new_fixture(tmp_path: Path) -> None:
    bundled = _bundled_index(tmp_path, "2019-06-01,Brazil,Argentina,2,2,Copa,Rio,Brazil,FALSE\n")
    # Fresh pack: the old result PLUS a genuinely-new, scheduled (no-score) fixture.
    fresh = _write_pack(
        tmp_path / "intl-fresh",
        "martj42-international-results",
        "2019-06-01,Brazil,Argentina,2,2,Copa,Rio,Brazil,FALSE\n"
        "2026-08-01,France,Spain,NA,NA,World Cup,Paris,France,TRUE\n",
    )
    target = tmp_path / "refresh"
    merged_path = merge_refreshed_index(fresh, bundled, target)
    df = pd.read_parquet(merged_path)

    # Exact contract + ids unique across the merge.
    assert list(df.columns) == INDEX_COLUMNS
    assert df["match_id"].is_unique
    # Club history survived a refresh it was never rebuilt from.
    assert (df["home_team"] == "Arsenal").any()
    assert (df["source_kind"] == "club").sum() == 2
    # The new fixture is now searchable as an upcoming (incomplete) match.
    france = df[(df["home_team"] == "France") & (df["away_team"] == "Spain")]
    assert len(france) == 1
    assert bool(france.iloc[0]["is_complete"]) is False
    # Meta digest matches the merged bytes (honest sidecar).
    meta = json.loads((target / "matches_index.meta.json").read_text())
    assert meta["refreshed"] is True
    assert meta["row_count"] == len(df)
    assert meta["parquet_sha256"] == hashlib.sha256(merged_path.read_bytes()).hexdigest()
    # Fresh internationals side tables/aliases landed alongside the index.
    assert (target / "aliases.json").exists()


def test_refresh_states_the_packs_it_was_built_from(tmp_path: Path) -> None:
    """A refreshed generation must stay provable, not just fresh.

    The retrospective proves a story's index and a seal's pack are one snapshot
    by comparing built_from[].manifest_sha256 with the pack's manifest digest.
    This meta used to be written to its own shape without the key, so a
    refreshed generation silently lost the ability to make that claim.
    """
    bundled = _bundled_index(tmp_path, "2019-06-01,Brazil,Argentina,2,2,Copa,Rio,Brazil,FALSE\n")
    fresh = _write_pack(
        tmp_path / "intl-fresh",
        "martj42-international-results",
        "2019-06-01,Brazil,Argentina,2,2,Copa,Rio,Brazil,FALSE\n",
    )
    target = tmp_path / "refresh"
    merge_refreshed_index(fresh, bundled, target)

    meta = json.loads((target / "matches_index.meta.json").read_text())
    built_from = meta["built_from"]
    assert [entry["source_id"] for entry in built_from] == ["martj42-international-results"]
    assert built_from[0]["manifest_sha256"] == hashlib.sha256(
        (fresh / "manifest.json").read_bytes()
    ).hexdigest()
    # The refresh-specific facts are additions, not a replacement shape.
    assert meta["refreshed"] is True


def test_refresh_drops_stale_internationals(tmp_path: Path) -> None:
    """The internationals side is rebuilt, not merged — a match dropped upstream
    must not linger from the old bundled index."""
    bundled = _bundled_index(
        tmp_path,
        "2019-06-01,Brazil,Argentina,2,2,Copa,Rio,Brazil,FALSE\n"
        "2018-01-01,Ghana,Egypt,1,1,Friendly,Accra,Ghana,FALSE\n",
    )
    fresh = _write_pack(
        tmp_path / "intl-fresh",
        "martj42-international-results",
        "2019-06-01,Brazil,Argentina,2,2,Copa,Rio,Brazil,FALSE\n",  # Ghana v Egypt gone
    )
    df = pd.read_parquet(merge_refreshed_index(fresh, bundled, tmp_path / "refresh"))
    assert not (df["home_team"] == "Ghana").any()
    assert (df["home_team"] == "Brazil").any()  # still present in the fresh side
    assert (df["home_team"] == "Arsenal").any()  # club history untouched


def test_refresh_is_byte_deterministic(tmp_path: Path) -> None:
    bundled = _bundled_index(tmp_path, "2019-06-01,Brazil,Argentina,2,2,Copa,Rio,Brazil,FALSE\n")
    fresh = _write_pack(
        tmp_path / "intl-fresh",
        "martj42-international-results",
        "2019-06-01,Brazil,Argentina,2,2,Copa,Rio,Brazil,FALSE\n"
        "2026-08-01,France,Spain,NA,NA,World Cup,Paris,France,TRUE\n",
    )
    first = merge_refreshed_index(fresh, bundled, tmp_path / "a")
    second = merge_refreshed_index(fresh, bundled, tmp_path / "b")
    assert first.read_bytes() == second.read_bytes()


def test_refresh_rejects_a_club_pack(tmp_path: Path) -> None:
    bundled = _bundled_index(tmp_path, "2019-06-01,Brazil,Argentina,2,2,Copa,Rio,Brazil,FALSE\n")
    not_intl = _write_pack(
        tmp_path / "club-pack",
        "synthetic-league",
        "2021-08-14,Arsenal,Chelsea,3,1,Premier League,London,England,FALSE\n",
        competition="Premier League",
    )
    with pytest.raises(RefreshError, match="not a pure internationals source"):
        merge_refreshed_index(not_intl, bundled, tmp_path / "refresh")
