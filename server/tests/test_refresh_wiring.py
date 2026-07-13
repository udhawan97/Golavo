"""Tests for wiring the running sidecar at a runtime-refreshed index.

The refresh engine writes fresh bytes to a per-user location; these tests pin the
glue that makes the live server *use* them: where the refresh dir sits relative to
the ledger, that source/CI mode has none (so nothing changes without a real
desktop install), and that ``repoint_to_refreshed`` actually swings the module's
path globals and clears the cache.
"""

from __future__ import annotations

from pathlib import Path

from golavo_server import matches, runtime, seal


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


def test_repoint_ignores_a_refresh_dir_with_no_index(monkeypatch, tmp_path: Path) -> None:
    """A half-provisioned refresh dir (no index yet) must not be adopted."""
    ledger = tmp_path / "app" / "ledger"
    ledger.mkdir(parents=True)
    (tmp_path / "app" / "refresh").mkdir()  # exists but empty — no matches_index.parquet
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
