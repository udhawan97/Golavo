from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pandas as pd
import pytest
from golavo_core.artifacts import score_forecast, seal_forecast, validate_artifact
from golavo_core.ingest import assert_no_future_rows, load_match_table
from golavo_core.models.candidates import EloOrdinalLogitModel

REPO_ROOT = Path(__file__).resolve().parents[2]
PACK = REPO_ROOT / "packs/martj42-internationals"
SAMPLES = REPO_ROOT / "data/fixtures/sample_artifacts"


def _rewrite_manifest(pack: Path, *, retrieved_at: str) -> None:
    manifest_path = pack / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["retrieved_at_utc"] = retrieved_at
    for entry in manifest["files"]:
        entry["sha256"] = hashlib.sha256((pack / entry["name"]).read_bytes()).hexdigest()
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def test_ingest_types_completed_and_scheduled_rows() -> None:
    matches = load_match_table(PACK)
    assert str(matches["home_score"].dtype) == "Int16"
    assert matches["neutral"].dtype.name == "boolean"
    assert int((~matches["is_complete"]).sum()) == 3
    assert matches["match_id"].is_unique


def test_neutral_flag_removes_elo_home_advantage() -> None:
    model = EloOrdinalLogitModel()
    model.ratings = {"A": 1500.0, "B": 1500.0}
    neutral = model.predict("A", "B", True).probs
    hosted = model.predict("A", "B", False).probs
    assert neutral[0] == pytest.approx(neutral[2])
    assert hosted[0] > neutral[0]


def test_future_training_row_fails_loudly() -> None:
    injected = pd.DataFrame(
        {
            "match_id": ["m_injected_future"],
            "date": [pd.Timestamp("2030-01-02")],
        }
    )
    with pytest.raises(ValueError, match="training leakage"):
        assert_no_future_rows(injected, "2030-01-01T23:59:59Z")


def test_seal_is_byte_identical_for_same_snapshot_and_seed(tmp_path: Path) -> None:
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    kwargs = {
        "pack_dir": PACK,
        "date": "2026-07-11",
        "home_team": "Norway",
        "away_team": "England",
        "as_of_utc": "2026-07-10T20:00:00Z",
        "family": "elo_ordlogit",
        "seed": 20260710,
    }
    first = seal_forecast(output_dir=first_dir, **kwargs)
    second = seal_forecast(output_dir=second_dir, **kwargs)
    assert first.name == second.name
    assert first.read_bytes() == second.read_bytes()


def test_abstention_gate_uses_ten_match_minimum(tmp_path: Path) -> None:
    sparse_pack = tmp_path / "sparse"
    shutil.copytree(PACK, sparse_pack)
    rows = pd.read_csv(sparse_pack / "results.csv")
    target = rows.loc[
        rows["date"].eq("2026-07-11")
        & rows["home_team"].eq("Norway")
        & rows["away_team"].eq("England")
    ]
    history = rows.loc[
        rows["home_score"].notna()
        & (
            rows["home_team"].isin(["Norway", "England"])
            | rows["away_team"].isin(["Norway", "England"])
        )
    ].tail(4)
    pd.concat([history, target]).to_csv(sparse_pack / "results.csv", index=False)
    _rewrite_manifest(sparse_pack, retrieved_at="2026-07-10T19:35:25Z")
    path = seal_forecast(
        pack_dir=sparse_pack,
        output_dir=tmp_path / "artifacts",
        date="2026-07-11",
        home_team="Norway",
        away_team="England",
        as_of_utc="2026-07-10T20:00:00Z",
    )
    artifact = json.loads(path.read_text(encoding="utf-8"))
    assert artifact["status"] == "abstained"
    assert artifact["forecast"]["probs"] is None
    assert "require 10 each" in artifact["forecast"]["abstain_reason"]


def test_score_writes_successor_and_never_mutates_seal(tmp_path: Path) -> None:
    sealed_path = seal_forecast(
        pack_dir=PACK,
        output_dir=tmp_path / "sealed",
        date="2026-07-11",
        home_team="Norway",
        away_team="England",
        as_of_utc="2026-07-10T20:00:00Z",
    )
    sealed_bytes = sealed_path.read_bytes()
    newer = tmp_path / "newer"
    shutil.copytree(PACK, newer)
    results_path = newer / "results.csv"
    text = results_path.read_text(encoding="utf-8")
    old = "2026-07-11,Norway,England,NA,NA,FIFA World Cup"
    assert old in text
    results_path.write_text(
        text.replace(old, "2026-07-11,Norway,England,1,0,FIFA World Cup"),
        encoding="utf-8",
    )
    _rewrite_manifest(newer, retrieved_at="2026-07-12T00:00:00Z")
    scored_path = score_forecast(
        artifact_path=sealed_path,
        newer_pack_dir=newer,
        output_dir=tmp_path / "scored",
    )
    scored = json.loads(scored_path.read_text(encoding="utf-8"))
    assert sealed_path.read_bytes() == sealed_bytes
    assert scored["status"] == "scored"
    assert scored["supersedes"] == json.loads(sealed_bytes)["artifact_id"]
    assert scored["evaluation"]["actual"] == {
        "home_goals": 1,
        "away_goals": 0,
        "outcome": "home",
    }


def test_all_sample_artifacts_validate() -> None:
    paths = sorted(SAMPLES.glob("fa_*.json"))
    assert 6 <= len(paths) <= 10
    statuses = set()
    for path in paths:
        artifact = json.loads(path.read_text(encoding="utf-8"))
        validate_artifact(artifact)
        statuses.add(artifact["status"])
    assert statuses == {"sealed", "scored", "abstained", "voided"}


def test_elo_beats_climatological_on_all_frozen_folds() -> None:
    summary = json.loads((REPO_ROOT / "docs/handoff/eval_summary.json").read_text())
    assert {fold["fold_id"] for fold in summary["folds"]} == {"WC2022", "EURO2024", "WC2026"}
    for fold in summary["folds"]:
        scores = {model["family"]: model["log_loss"] for model in fold["models"]}
        assert scores["elo_ordlogit"] < scores["climatological"]
