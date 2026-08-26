from __future__ import annotations

import copy
from pathlib import Path

import pytest
from golavo_core import proof as proof_module
from golavo_core.proof import build_forecast_proof, verify_forecast_proof

REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLES = REPO_ROOT / "data/fixtures/sample_artifacts"


def test_portable_proof_verifies_every_artifact_and_its_bundle_hash() -> None:
    artifact = sorted(SAMPLES.glob("fa_*.json"))[0]

    proof = build_forecast_proof(artifact, ledger_dir=SAMPLES, pack_root=REPO_ROOT / "packs")
    verified = verify_forecast_proof(proof)

    assert verified["verified"] is True
    assert verified["root_artifact_id"] == artifact.stem
    assert verified["artifact_count"] >= 1
    assert verified["source_count"] == (
        verified["embedded_source_count"] + verified["descriptor_only_source_count"]
    )
    assert len(verified["source_checks"]) == verified["source_count"]
    assert {item["status"] for item in verified["source_checks"]} <= {
        "descriptor-only-not-verified",
        "embedded-manifest-hash-valid",
    }
    assert "source authenticity" in " ".join(verified["limits"])
    assert proof["verification"]["artifact_integrity"] == "verified"
    assert proof["bundle_sha256"].startswith("sha256:")


def test_portable_proof_rejects_a_tampered_embedded_artifact() -> None:
    artifact = sorted(SAMPLES.glob("fa_*.json"))[0]
    proof = build_forecast_proof(artifact, ledger_dir=SAMPLES, pack_root=REPO_ROOT / "packs")
    tampered = copy.deepcopy(proof)
    tampered["artifacts"][0]["forecast"]["probs"]["home"] += 0.01

    with pytest.raises(ValueError, match="portable proof hash mismatch|probabilities must sum"):
        verify_forecast_proof(tampered)


def test_portable_proof_rejects_missing_recomputed_source_declarations() -> None:
    artifact = sorted(SAMPLES.glob("fa_*.json"))[0]
    proof = build_forecast_proof(artifact, ledger_dir=SAMPLES, pack_root=REPO_ROOT / "packs")
    tampered = copy.deepcopy(proof)
    tampered["sources"] = []
    tampered["bundle_sha256"] = proof_module._bundle_sha256(tampered)

    with pytest.raises(ValueError, match="sources do not match"):
        verify_forecast_proof(tampered)
