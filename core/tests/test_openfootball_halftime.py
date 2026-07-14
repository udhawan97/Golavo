"""Half-time ingestion is strict, audited, and identity-neutral."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest
from golavo_core.ingest.openfootball import _extract_ht, load_openfootball_table


def _pack(tmp_path: Path, matches: list[dict]) -> Path:
    pack = tmp_path / "openfootball-mini"
    pack.mkdir(parents=True)
    name = "2020-21.en.1.json"
    payload = json.dumps({"matches": matches}, sort_keys=True)
    (pack / name).write_text(payload, encoding="utf-8")
    manifest = {
        "source_id": "openfootball-eng-pl",
        "license": "CC0-1.0",
        "upstream_ref": "test",
        "files": [{"name": name, "sha256": hashlib.sha256(payload.encode()).hexdigest()}],
    }
    (pack / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return pack


def _match(score: object) -> dict:
    return {
        "date": "2020-09-12",
        "time": "15:00",
        "team1": "Arsenal FC",
        "team2": "Chelsea FC",
        "score": score,
    }


def test_extract_ht_accepts_only_two_integers() -> None:
    assert _extract_ht(_match({"ht": [1, 0]})) == (1, 0)
    for score in ({}, {"ht": {}}, {"ht": [1]}, {"ht": [1, "0"]}, {"ht": [True, 0]}):
        assert _extract_ht(_match(score)) is None


def test_loader_keeps_missing_ht_nullable(tmp_path: Path) -> None:
    frame = load_openfootball_table(_pack(tmp_path, [_match({"ft": [2, 1]})]))
    assert pd.isna(frame.iloc[0]["ht_home_score"])
    assert pd.isna(frame.iloc[0]["ht_away_score"])


def test_loader_rejects_half_time_above_full_time(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="half-time score exceeds full-time score"):
        load_openfootball_table(_pack(tmp_path, [_match({"ht": [2, 0], "ft": [1, 0]})]))


def test_half_time_scores_do_not_change_match_identity(tmp_path: Path) -> None:
    without_ht = load_openfootball_table(
        _pack(tmp_path / "a", [_match({"ft": [2, 1]})])
    ).iloc[0]["match_id"]
    with_ht = load_openfootball_table(
        _pack(tmp_path / "b", [_match({"ht": [1, 0], "ft": [2, 1]})])
    ).iloc[0]["match_id"]
    assert with_ht == without_ht
