"""Tests for wiring the running sidecar at a runtime-refreshed index.

The refresh engine writes fresh bytes to a per-user location; these tests pin the
glue that makes the live server *use* them: where the refresh dir sits relative to
the ledger, that source/CI mode has none (so nothing changes without a real
desktop install), and that ``repoint_to_refreshed`` actually swings the module's
path globals and clears the cache.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pandas as pd
from golavo_server import matches, runtime, seal


def _coherence_index(path: Path, match_id: str = "m_old") -> None:
    frame = pd.DataFrame(
        [
            {
                "match_id": match_id,
                "date": "2030-01-01",
                "kickoff_utc": "2030-01-01T12:00:00Z",
                "home_team": "Russia",
                "away_team": "Example",
                "home_norm": "russia",
                "away_norm": "example",
                "home_score": None,
                "away_score": None,
                "is_complete": False,
                "competition": "Friendly",
                "country": "Russia",
                "city": "Moscow",
                "neutral": False,
                "source_id": "martj42-international-results",
                "source_kind": "international",
            }
        ]
    )
    frame["date"] = pd.to_datetime(frame["date"])
    frame["kickoff_utc"] = pd.to_datetime(frame["kickoff_utc"], utc=True)
    frame.to_parquet(path)


def test_refresh_dir_is_none_in_source_mode(monkeypatch) -> None:
    monkeypatch.delenv("GOLAVO_DATA_DIR", raising=False)
    assert runtime.refresh_dir() is None


def test_refresh_dir_sits_beside_the_ledger(monkeypatch) -> None:
    monkeypatch.setenv("GOLAVO_DATA_DIR", "/data/com.golavo.app/ledger")
    assert runtime.refresh_dir() == Path("/data/com.golavo.app/refresh")


def test_resolver_returns_bundle_without_a_refresh(monkeypatch) -> None:
    monkeypatch.delenv("GOLAVO_DATA_DIR", raising=False)
    from golavo_core import resources

    paths = matches._resolve_index_paths()
    assert paths["index"] == Path(resources.match_index_path())
    assert paths["aliases"] == Path(resources.match_index_aliases_path())


def test_repoint_swings_to_refreshed_then_back(monkeypatch, tmp_path: Path) -> None:
    ledger = tmp_path / "com.golavo.app" / "ledger"
    ledger.mkdir(parents=True)
    refreshed = tmp_path / "com.golavo.app" / "refresh"
    refreshed.mkdir()
    for name in (
        "matches_index.parquet",
        "matches_index.meta.json",
        "goalscorers.parquet",
        "shootouts.parquet",
        "aliases.json",
    ):
        (refreshed / name).write_text("x", encoding="utf-8")
    from golavo_core.ingest import MATCH_INDEX_SCHEMA_VERSION

    (refreshed / "matches_index.meta.json").write_text(
        json.dumps({"schema_version": MATCH_INDEX_SCHEMA_VERSION}), encoding="utf-8"
    )

    monkeypatch.setenv("GOLAVO_DATA_DIR", str(ledger))
    matches._CACHE = "stale"  # prove the cache is dropped on repoint
    matches.repoint_to_refreshed()
    try:
        assert matches.INDEX_PATH == refreshed / "matches_index.parquet"
        assert matches.ALIASES_PATH == refreshed / "aliases.json"
        assert matches.GOALSCORERS_PATH == refreshed / "goalscorers.parquet"
        assert matches._CACHE is None
    finally:
        # Restore the module to the bundled paths so later tests are unaffected.
        monkeypatch.delenv("GOLAVO_DATA_DIR", raising=False)
        matches.repoint_to_refreshed()

    from golavo_core import resources

    assert matches.INDEX_PATH == Path(resources.match_index_path())


def test_load_started_before_repoint_cannot_republish_retired_frame(
    monkeypatch, tmp_path: Path
) -> None:
    """Force the launch-warm/read race at the old vulnerable publication point."""
    old_index = tmp_path / "old.parquet"
    new_index = tmp_path / "new.parquet"
    old_meta = tmp_path / "old.meta.json"
    new_meta = tmp_path / "new.meta.json"
    for path in (old_index, new_index):
        path.write_bytes(b"fixture")
    old_meta.write_text('{"generation":"old"}', encoding="utf-8")
    new_meta.write_text('{"generation":"new"}', encoding="utf-8")

    old_frame = object()
    new_frame = object()
    old_read_started = threading.Event()
    allow_old_read_to_finish = threading.Event()

    def blocked_read(path: Path) -> object:
        if Path(path) == old_index:
            old_read_started.set()
            assert allow_old_read_to_finish.wait(5), "test barrier timed out"
            return old_frame
        assert Path(path) == new_index
        return new_frame

    monkeypatch.setattr(pd, "read_parquet", blocked_read)
    monkeypatch.setattr(matches, "INDEX_PATH", old_index)
    monkeypatch.setattr(matches, "INDEX_META_PATH", old_meta)
    # repoint updates every side-table global; register their original values
    # with monkeypatch so this race test cannot leak a temporary alias path.
    monkeypatch.setattr(matches, "GOALSCORERS_PATH", matches.GOALSCORERS_PATH)
    monkeypatch.setattr(matches, "SHOOTOUTS_PATH", matches.SHOOTOUTS_PATH)
    monkeypatch.setattr(matches, "ALIASES_PATH", matches.ALIASES_PATH)
    matches.reset_cache()
    monkeypatch.setattr(
        matches,
        "_resolve_index_paths",
        lambda: {
            "index": new_index,
            "meta": new_meta,
            "goalscorers": tmp_path / "new-goalscorers.parquet",
            "shootouts": tmp_path / "new-shootouts.parquet",
            "aliases": tmp_path / "new-aliases.json",
        },
    )

    loaded: list[object] = []
    worker = threading.Thread(
        target=lambda: loaded.append(matches._load_index()), daemon=True
    )
    worker.start()
    try:
        assert old_read_started.wait(5), "old generation never started loading"
        matches.repoint_to_refreshed()
    finally:
        allow_old_read_to_finish.set()
        worker.join(5)

    assert not worker.is_alive()
    assert loaded == [new_frame]
    assert matches._CACHE is new_frame
    assert matches.index_snapshot().frame is new_frame
    assert matches.index_fingerprint() == matches._fingerprint_for(new_index, new_meta)
    matches.reset_cache()


def test_search_keeps_aliases_from_its_captured_generation(
    monkeypatch, tmp_path: Path
) -> None:
    old_index, new_index = tmp_path / "old.parquet", tmp_path / "new.parquet"
    _coherence_index(old_index)
    _coherence_index(new_index, "m_new")
    old_meta, new_meta = tmp_path / "old.meta.json", tmp_path / "new.meta.json"
    old_meta.write_text('{"generation":"old"}', encoding="utf-8")
    new_meta.write_text('{"generation":"new"}', encoding="utf-8")
    old_aliases, new_aliases = tmp_path / "old-aliases.json", tmp_path / "new-aliases.json"
    old_aliases.write_text('{"soviet union":["Russia"]}', encoding="utf-8")
    new_aliases.write_text('{"soviet union":["Spain"]}', encoding="utf-8")

    for name, value in (
        ("INDEX_PATH", old_index),
        ("INDEX_META_PATH", old_meta),
        ("ALIASES_PATH", old_aliases),
        ("GOALSCORERS_PATH", tmp_path / "old-goals.parquet"),
        ("SHOOTOUTS_PATH", tmp_path / "old-shootouts.parquet"),
    ):
        monkeypatch.setattr(matches, name, value)
    matches.reset_cache()
    monkeypatch.setattr(
        matches,
        "_resolve_index_paths",
        lambda: {
            "index": new_index,
            "meta": new_meta,
            "aliases": new_aliases,
            "goalscorers": tmp_path / "new-goals.parquet",
            "shootouts": tmp_path / "new-shootouts.parquet",
        },
    )
    alias_read_started = threading.Event()
    allow_alias_read = threading.Event()
    real_load_aliases = matches._load_aliases
    seen_paths: list[Path | None] = []

    def blocked_aliases(path: Path | None = None) -> dict[str, list[str]]:
        seen_paths.append(path)
        alias_read_started.set()
        assert allow_alias_read.wait(5), "alias barrier timed out"
        return real_load_aliases(path)

    monkeypatch.setattr(matches, "_load_aliases", blocked_aliases)
    result: list[dict] = []
    worker = threading.Thread(
        target=lambda: result.append(
            matches.search_matches("soviet union", forecasts_dir=tmp_path / "ledger")
        ),
        daemon=True,
    )
    worker.start()
    try:
        assert alias_read_started.wait(5), "search never reached alias read"
        matches.repoint_to_refreshed()
    finally:
        allow_alias_read.set()
        worker.join(5)
    assert not worker.is_alive()
    assert seen_paths == [old_aliases]
    assert [item["match_id"] for item in result[0]["matches"]] == ["m_old"]
    matches.reset_cache()


def test_notebook_keeps_side_tables_from_its_captured_generation(
    monkeypatch, tmp_path: Path
) -> None:
    from golavo_core import facts

    old_index, new_index = tmp_path / "old.parquet", tmp_path / "new.parquet"
    _coherence_index(old_index)
    _coherence_index(new_index, "m_new")
    old_meta, new_meta = tmp_path / "old.meta.json", tmp_path / "new.meta.json"
    old_meta.write_text('{"generation":"old"}', encoding="utf-8")
    new_meta.write_text('{"generation":"new"}', encoding="utf-8")
    old_goals, new_goals = tmp_path / "old-goals.parquet", tmp_path / "new-goals.parquet"
    old_shootouts = tmp_path / "old-shootouts.parquet"
    new_shootouts = tmp_path / "new-shootouts.parquet"
    pd.DataFrame([{"marker": "old"}]).to_parquet(old_goals)
    pd.DataFrame([{"marker": "new"}]).to_parquet(new_goals)
    pd.DataFrame([{"marker": "old"}]).to_parquet(old_shootouts)
    pd.DataFrame([{"marker": "new"}]).to_parquet(new_shootouts)
    old_aliases, new_aliases = tmp_path / "old-aliases.json", tmp_path / "new-aliases.json"
    old_aliases.write_text("{}", encoding="utf-8")
    new_aliases.write_text("{}", encoding="utf-8")

    for name, value in (
        ("INDEX_PATH", old_index),
        ("INDEX_META_PATH", old_meta),
        ("ALIASES_PATH", old_aliases),
        ("GOALSCORERS_PATH", old_goals),
        ("SHOOTOUTS_PATH", old_shootouts),
    ):
        monkeypatch.setattr(matches, name, value)
    matches.reset_cache()
    monkeypatch.setattr(
        matches,
        "_resolve_index_paths",
        lambda: {
            "index": new_index,
            "meta": new_meta,
            "aliases": new_aliases,
            "goalscorers": new_goals,
            "shootouts": new_shootouts,
        },
    )
    side_read_started = threading.Event()
    allow_side_read = threading.Event()
    real_load_side_tables = matches._load_side_tables
    seen_paths: list[tuple[Path | None, Path | None]] = []

    def blocked_side_tables(
        goalscorers_path: Path | None = None,
        shootouts_path: Path | None = None,
    ) -> tuple[object, object]:
        seen_paths.append((goalscorers_path, shootouts_path))
        side_read_started.set()
        assert allow_side_read.wait(5), "side-table barrier timed out"
        return real_load_side_tables(goalscorers_path, shootouts_path)

    monkeypatch.setattr(matches, "_load_side_tables", blocked_side_tables)
    monkeypatch.setattr(
        facts,
        "build_notebook",
        lambda **kwargs: {"marker": kwargs["goalscorers"].iloc[0]["marker"]},
    )
    result: list[dict | None] = []
    worker = threading.Thread(
        target=lambda: result.append(
            matches.match_notebook("m_old", forecasts_dir=tmp_path / "ledger")
        ),
        daemon=True,
    )
    worker.start()
    try:
        assert side_read_started.wait(5), "notebook never reached side-table read"
        matches.repoint_to_refreshed()
    finally:
        allow_side_read.set()
        worker.join(5)
    assert not worker.is_alive()
    assert seen_paths == [(old_goals, old_shootouts)]
    assert result[0] is not None and result[0]["notebook"]["marker"] == "old"
    matches.reset_cache()


def test_repoint_ignores_a_refresh_dir_with_no_index(monkeypatch, tmp_path: Path) -> None:
    """A half-provisioned refresh dir (no index yet) must not be adopted."""
    ledger = tmp_path / "app" / "ledger"
    ledger.mkdir(parents=True)
    (tmp_path / "app" / "refresh").mkdir()  # exists but empty — no matches_index.parquet
    monkeypatch.setenv("GOLAVO_DATA_DIR", str(ledger))
    from golavo_core import resources

    assert matches._resolve_index_paths()["index"] == Path(resources.match_index_path())


def test_resolver_ignores_a_refreshed_index_with_stale_schema(
    monkeypatch, tmp_path: Path
) -> None:
    ledger = tmp_path / "app" / "ledger"
    ledger.mkdir(parents=True)
    refreshed = tmp_path / "app" / "refresh"
    refreshed.mkdir()
    (refreshed / "matches_index.parquet").write_bytes(b"stale")
    (refreshed / "matches_index.meta.json").write_text(
        json.dumps({"schema_version": "0.2.0"}), encoding="utf-8"
    )
    monkeypatch.setenv("GOLAVO_DATA_DIR", str(ledger))

    from golavo_core import resources

    assert matches._resolve_index_paths()["index"] == Path(resources.match_index_path())


def test_seal_resolver_prefers_a_refreshed_pack(monkeypatch, tmp_path: Path) -> None:
    ledger = tmp_path / "app" / "ledger"
    ledger.mkdir(parents=True)
    pinned = tmp_path / "app" / "refresh" / "pack"
    pinned.mkdir(parents=True)
    (pinned / "manifest.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("GOLAVO_DATA_DIR", str(ledger))

    resolved = seal.resolve_pack_dir("martj42-international-results", "international")
    assert resolved == pinned


def test_seal_resolver_falls_back_to_bundle_without_a_refreshed_pack(
    monkeypatch, tmp_path: Path
) -> None:
    """A refresh dir with no pinned pack yet must not shadow the bundled pack."""
    ledger = tmp_path / "app" / "ledger"
    ledger.mkdir(parents=True)
    (tmp_path / "app" / "refresh").mkdir(parents=True)  # exists, but no pack/manifest.json
    monkeypatch.setenv("GOLAVO_DATA_DIR", str(ledger))

    resolved = seal.resolve_pack_dir("martj42-international-results", "international")
    # A bundled internationals pack (the greatest-anchor one, present in source mode) —
    # never the empty refresh dir.
    assert resolved is not None
    assert (resolved / "manifest.json").is_file()
    assert resolved != tmp_path / "app" / "refresh" / "pack"
