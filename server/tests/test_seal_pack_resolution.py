"""Seal pack resolution: search and sealing must resolve the SAME internationals pack,
so a newly bundled refresh (a higher snapshot anchor) becomes sealable at once.
"""

from __future__ import annotations

import json
from pathlib import Path

from golavo_server import runtime, seal


def _pack(packs: Path, name: str) -> Path:
    pack = packs / name
    pack.mkdir(parents=True)
    manifest = {"source_id": "martj42-international-results", "files": [], "license": "CC0-1.0"}
    (pack / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return pack


def _registry(packs: Path, entries: list[dict]) -> None:
    (packs / "snapshots.json").write_text(json.dumps({"snapshots": entries}), encoding="utf-8")


def test_active_bundled_pack_picks_the_greatest_anchor(tmp_path, monkeypatch) -> None:
    packs = tmp_path / "packs"
    _pack(packs, "martj42-internationals-old")
    _pack(packs, "martj42-internationals-new")
    _registry(
        packs,
        [
            {"source_id": "martj42-international-results",
             "pack": "packs/martj42-internationals-old",
             "upstream_committed_at_utc": "2026-07-07T00:00:00Z",
             "retrieved_at_utc": "2026-07-07T00:00:00Z"},
            {"source_id": "martj42-international-results",
             "pack": "packs/martj42-internationals-new",
             "upstream_committed_at_utc": "2026-07-12T00:00:00Z",
             "retrieved_at_utc": "2026-07-12T00:00:00Z"},
        ],
    )
    monkeypatch.setattr(seal, "PACKS_DIR", packs)
    monkeypatch.setattr(runtime, "refreshed_pack_dir", lambda: None)
    got = seal.resolve_pack_dir("martj42-international-results", "international")
    assert got == packs / "martj42-internationals-new"


def test_resolution_falls_back_to_canonical_without_a_registry(tmp_path, monkeypatch) -> None:
    packs = tmp_path / "packs"
    _pack(packs, "martj42-internationals")  # no snapshots.json bundled (older frozen build)
    monkeypatch.setattr(seal, "PACKS_DIR", packs)
    monkeypatch.setattr(runtime, "refreshed_pack_dir", lambda: None)
    got = seal.resolve_pack_dir("martj42-international-results", "international")
    assert got == packs / "martj42-internationals"


def test_resolution_is_none_for_unsupported_sources() -> None:
    assert seal.resolve_pack_dir("openfootball-football-json", "club") is None
    assert seal.resolve_pack_dir("martj42-international-results", "club") is None
