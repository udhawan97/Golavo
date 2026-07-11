"""Phase 5 — MatchEvidenceBundle construction is deterministic and self-consistent.

The bundle is a pure function of a ForecastArtifact. These tests use the real
seal→score loop over the two retained martj42 snapshots (same fixture as the
Phase 3 tests) plus the synthetic contract fixtures, so no live model is needed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from golavo_core.artifacts import score_forecast, seal_forecast
from golavo_core.evidence import (
    EVIDENCE_SCHEMA_VERSION,
    build_evidence_bundle,
    validate_evidence_bundle,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
T0_PACK = REPO_ROOT / "packs/martj42-internationals-273c731492df"
T1_PACK = REPO_ROOT / "packs/martj42-internationals"
FIXTURES = sorted((REPO_ROOT / "data/fixtures/sample_artifacts").glob("fa_*.json"))


def _seal(output_dir: Path) -> Path:
    return seal_forecast(
        pack_dir=T0_PACK,
        output_dir=output_dir,
        date="2026-07-09",
        home_team="France",
        away_team="Morocco",
        as_of_utc="2026-07-08T00:00:00Z",
        horizon="T-24h",
    )


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_every_sample_artifact_yields_a_valid_bundle() -> None:
    assert FIXTURES, "expected committed sample artifacts"
    for path in FIXTURES:
        bundle = build_evidence_bundle(_load(path))
        validate_evidence_bundle(bundle)
        assert bundle["schema_version"] == EVIDENCE_SCHEMA_VERSION
        assert bundle["bundle_id"].startswith("eb_")
        assert bundle["artifact_id"] == _load(path)["artifact_id"]


def test_bundle_is_a_deterministic_pure_function() -> None:
    artifact = _load(FIXTURES[0])
    first = build_evidence_bundle(artifact)
    second = build_evidence_bundle(artifact)
    assert first == second
    assert first["bundle_hash"] == second["bundle_hash"]


def test_allowed_numbers_cover_exactly_the_engine_numbers(tmp_path: Path) -> None:
    sealed = build_evidence_bundle(_load(_seal(tmp_path)))
    ids = {n["id"] for n in sealed["allowed_numbers"]}
    assert {"prob_home", "prob_draw", "prob_away"} <= ids
    # A sealed (not yet scored) forecast exposes no result numbers.
    assert "actual_home_goals" not in ids
    assert "log_loss" not in ids
    # Every allowed number cites at least one real source and carries a unit.
    source_ids = {s["source_id"] for s in sealed["sources"]}
    for number in sealed["allowed_numbers"]:
        assert number["source_ids"]
        assert set(number["source_ids"]) <= source_ids
        assert number["unit"] in {"percent", "goals", "log_loss", "brier", "count"}


def test_scored_bundle_exposes_result_numbers(tmp_path: Path) -> None:
    sealed_path = _seal(tmp_path)
    scored_path = score_forecast(
        artifact_path=sealed_path, newer_pack_dir=T1_PACK, output_dir=tmp_path
    )
    scored = build_evidence_bundle(_load(scored_path))
    ids = {n["id"] for n in scored["allowed_numbers"]}
    assert {"actual_home_goals", "actual_away_goals", "prob_assigned", "log_loss", "brier"} <= ids
    # France 2–0 Morocco in the retained T1 snapshot.
    by_id = {n["id"]: n for n in scored["allowed_numbers"]}
    assert by_id["actual_home_goals"]["value"] == 2
    assert by_id["actual_away_goals"]["value"] == 0


def test_abstained_bundle_has_no_allowed_numbers() -> None:
    abstained = next(
        _load(path) for path in FIXTURES if _load(path)["status"] == "abstained"
    )
    bundle = build_evidence_bundle(abstained)
    assert bundle["allowed_numbers"] == []
    assert bundle["forecast_summary"]["leading_outcome"] is None
    # Still valid, still carries sources and qualitative facts.
    validate_evidence_bundle(bundle)
    assert bundle["sources"]
    assert any(fact["fact_id"] == "abstained" for fact in bundle["facts"])


def test_every_fact_number_ref_and_source_resolves(tmp_path: Path) -> None:
    scored_path = score_forecast(
        artifact_path=_seal(tmp_path), newer_pack_dir=T1_PACK, output_dir=tmp_path
    )
    bundle = build_evidence_bundle(_load(scored_path))
    number_ids = {n["id"] for n in bundle["allowed_numbers"]}
    source_ids = {s["source_id"] for s in bundle["sources"]}
    for fact in bundle["facts"]:
        assert set(fact["number_refs"]) <= number_ids
        assert set(fact["source_ids"]) <= source_ids


def test_bundle_never_leaks_a_writable_probability_path(tmp_path: Path) -> None:
    """The bundle is a read model: it carries display/value pairs, never a hook
    the AI could use to write back a probability."""
    bundle = build_evidence_bundle(_load(_seal(tmp_path)))
    serialized = json.dumps(bundle)
    assert "payload_sha256" not in bundle  # not the artifact; no seal digest to spoof
    assert bundle["derived_from_payload_sha256"]  # but it is pinned to one
    # Probabilities appear only as immutable display strings + values.
    assert "probs" not in serialized  # no nested Probabilities object to mutate


def test_rejects_unknown_status() -> None:
    with pytest.raises(ValueError):
        build_evidence_bundle({"status": "draft"})
