"""Which pack wins, decided once.

The rule — for each source (and, for a club source, each competition), the entry
whose data state is anchored latest wins, ties broken by pack path — was written
twice: once for building the search index, once for resolving the pack a seal
trains from. The second carried a docstring reading "Mirrors
ingest.default_index_packs". Search and sealing disagreeing about which pack is
current is exactly the drift that docstring was there to prevent.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from golavo_core.packstore import active_pack, active_packs


def _registry(tmp_path: Path, entries: list[dict[str, object]]) -> Path:
    path = tmp_path / "snapshots.json"
    path.write_text(json.dumps({"snapshots": entries}), encoding="utf-8")
    return path


def _pack(tmp_path: Path, name: str, *, competition: str | None = None) -> None:
    directory = tmp_path / name
    directory.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, object] = {
        "source_id": "s",
        "upstream_ref": "r",
        "files": [],
        "license": "CC0-1.0",
    }
    if competition is not None:
        manifest["competition"] = competition
    (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def _resolve(root: Path):
    return lambda name: root / name


class TestActivePacks:
    def test_the_latest_anchor_wins_its_source(self, tmp_path: Path) -> None:
        _pack(tmp_path, "old")
        _pack(tmp_path, "new")
        registry = _registry(
            tmp_path,
            [
                {"pack": "old", "source_id": "martj42", "retrieved_at_utc": "2026-01-01T00:00:00Z"},
                {"pack": "new", "source_id": "martj42", "retrieved_at_utc": "2026-06-01T00:00:00Z"},
            ],
        )
        packs = active_packs(registry, resolve=_resolve(tmp_path))
        assert [p.directory.name for p in packs] == ["new"]

    def test_the_upstream_commit_time_outranks_our_retrieval_time(self, tmp_path: Path) -> None:
        """A pack fetched later but committed earlier is the older data state."""
        _pack(tmp_path, "fetched_later")
        _pack(tmp_path, "committed_later")
        registry = _registry(
            tmp_path,
            [
                {
                    "pack": "fetched_later",
                    "source_id": "martj42",
                    "retrieved_at_utc": "2026-07-01T00:00:00Z",
                    "upstream_committed_at_utc": "2026-01-01T00:00:00Z",
                },
                {
                    "pack": "committed_later",
                    "source_id": "martj42",
                    "retrieved_at_utc": "2026-02-01T00:00:00Z",
                    "upstream_committed_at_utc": "2026-06-01T00:00:00Z",
                },
            ],
        )
        packs = active_packs(registry, resolve=_resolve(tmp_path))
        assert [p.directory.name for p in packs] == ["committed_later"]

    def test_each_club_competition_keeps_its_own_pack(self, tmp_path: Path) -> None:
        """One club source id is shared across five leagues."""
        _pack(tmp_path, "epl", competition="English Premier League")
        _pack(tmp_path, "bundesliga", competition="Bundesliga")
        registry = _registry(
            tmp_path,
            [
                {
                    "pack": "epl",
                    "source_id": "openfootball",
                    "retrieved_at_utc": "2026-01-01T00:00:00Z",
                },
                {
                    "pack": "bundesliga",
                    "source_id": "openfootball",
                    "retrieved_at_utc": "2026-01-01T00:00:00Z",
                },
            ],
        )
        packs = active_packs(registry, resolve=_resolve(tmp_path))
        assert {p.directory.name for p in packs} == {"epl", "bundesliga"}

    def test_ties_break_on_pack_path_so_the_build_is_deterministic(self, tmp_path: Path) -> None:
        _pack(tmp_path, "aaa")
        _pack(tmp_path, "zzz")
        registry = _registry(
            tmp_path,
            [
                {"pack": "aaa", "source_id": "s", "retrieved_at_utc": "2026-01-01T00:00:00Z"},
                {"pack": "zzz", "source_id": "s", "retrieved_at_utc": "2026-01-01T00:00:00Z"},
            ],
        )
        assert [p.directory.name for p in active_packs(registry, resolve=_resolve(tmp_path))] == [
            "zzz"
        ]

    def test_results_are_ordered_by_pack_path(self, tmp_path: Path) -> None:
        _pack(tmp_path, "b_pack", competition="B")
        _pack(tmp_path, "a_pack", competition="A")
        registry = _registry(
            tmp_path,
            [
                {"pack": "b_pack", "source_id": "s", "retrieved_at_utc": "2026-01-01T00:00:00Z"},
                {"pack": "a_pack", "source_id": "s", "retrieved_at_utc": "2026-01-01T00:00:00Z"},
            ],
        )
        packs = active_packs(registry, resolve=_resolve(tmp_path))
        assert [p.directory.name for p in packs] == ["a_pack", "b_pack"]

    def test_an_entry_the_resolver_declines_is_skipped(self, tmp_path: Path) -> None:
        """A frozen build ships a subset of packs; the rest are simply absent."""
        _pack(tmp_path, "present")
        registry = _registry(
            tmp_path,
            [
                {"pack": "present", "source_id": "s", "retrieved_at_utc": "2026-01-01T00:00:00Z"},
                {
                    "pack": "absent",
                    "source_id": "other",
                    "retrieved_at_utc": "2026-01-01T00:00:00Z",
                },
            ],
        )
        resolve = lambda name: (tmp_path / name) if (tmp_path / name).is_dir() else None  # noqa: E731
        assert [p.directory.name for p in active_packs(registry, resolve=resolve)] == ["present"]

    def test_a_declared_pack_missing_its_manifest_fails_the_build(self, tmp_path: Path) -> None:
        """The index build must fail closed, never quietly drop a source."""
        registry = _registry(
            tmp_path,
            [{"pack": "ghost", "source_id": "s", "retrieved_at_utc": "2026-01-01T00:00:00Z"}],
        )
        (tmp_path / "ghost").mkdir()
        with pytest.raises((OSError, ValueError)):
            active_packs(registry, resolve=_resolve(tmp_path))


class TestActivePack:
    def test_picks_one_source(self, tmp_path: Path) -> None:
        _pack(tmp_path, "intl")
        _pack(tmp_path, "clubs", competition="Bundesliga")
        registry = _registry(
            tmp_path,
            [
                {
                    "pack": "intl",
                    "source_id": "martj42",
                    "retrieved_at_utc": "2026-01-01T00:00:00Z",
                },
                {
                    "pack": "clubs",
                    "source_id": "openfootball",
                    "retrieved_at_utc": "2026-01-01T00:00:00Z",
                },
            ],
        )
        found = active_pack(registry, resolve=_resolve(tmp_path), source_id="martj42")
        assert found is not None
        assert found.name == "intl"

    def test_a_competition_disambiguates_a_shared_club_source(self, tmp_path: Path) -> None:
        _pack(tmp_path, "epl", competition="English Premier League")
        _pack(tmp_path, "bundesliga", competition="Bundesliga")
        registry = _registry(
            tmp_path,
            [
                {"pack": "epl", "source_id": "of", "retrieved_at_utc": "2026-01-01T00:00:00Z"},
                {
                    "pack": "bundesliga",
                    "source_id": "of",
                    "retrieved_at_utc": "2026-01-01T00:00:00Z",
                },
            ],
        )
        found = active_pack(
            registry, resolve=_resolve(tmp_path), source_id="of", competition="Bundesliga"
        )
        assert found is not None
        assert found.name == "bundesliga"

    def test_an_unknown_source_resolves_to_nothing(self, tmp_path: Path) -> None:
        _pack(tmp_path, "intl")
        registry = _registry(
            tmp_path,
            [{"pack": "intl", "source_id": "martj42", "retrieved_at_utc": "2026-01-01T00:00:00Z"}],
        )
        assert active_pack(registry, resolve=_resolve(tmp_path), source_id="nope") is None

    def test_an_absent_registry_resolves_to_nothing(self, tmp_path: Path) -> None:
        """Older frozen builds ship no registry; the caller falls back."""
        assert (
            active_pack(tmp_path / "missing.json", resolve=_resolve(tmp_path), source_id="s")
            is None
        )
