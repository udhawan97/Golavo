from __future__ import annotations

import copy
from pathlib import Path

import pytest
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
    assert proof["verification"]["artifact_integrity"] == "verified"
    assert proof["bundle_sha256"].startswith("sha256:")


def test_portable_proof_rejects_a_tampered_embedded_artifact() -> None:
    artifact = sorted(SAMPLES.glob("fa_*.json"))[0]
    proof = build_forecast_proof(artifact, ledger_dir=SAMPLES, pack_root=REPO_ROOT / "packs")
    tampered = copy.deepcopy(proof)
    tampered["artifacts"][0]["forecast"]["probs"]["home"] += 0.01

    with pytest.raises(ValueError, match="portable proof hash mismatch|probabilities must sum"):
        verify_forecast_proof(tampered)
