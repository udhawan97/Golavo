"""Regression tests for the v0.2 hardening fixes.

H1 — a read path must verify a sealed artifact's content hash and content id, not
just its schema and coherence, so a hand-edited ``fa_*.json`` can never be served
or folded into the calibration record as if it were a genuine seal.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest
from golavo_core.artifacts import (
    canonical_bytes,
    load_verified_artifact,
    score_forecast,
    seal_forecast,
    verify_artifact_integrity,
)
from golavo_core.calibration import calibration_summary

REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLES = REPO_ROOT / "data/fixtures/sample_artifacts"


def _sample_with_probs_no_matrix() -> dict:
    """A genuine sealed/scored sample that has probs but no score_matrix, so a
    prob transposition stays schema-valid and coherent — isolating the content
    hash as the sole thing that must catch the tamper."""
    for path in sorted(SAMPLES.glob("fa_*.json")):
        artifact = json.loads(path.read_text(encoding="utf-8"))
        forecast = artifact["forecast"]
        if forecast.get("probs") is not None and forecast.get("score_matrix") is None:
            return artifact
    raise AssertionError("expected a probs-without-matrix sample fixture")


def test_verify_accepts_every_genuine_sample() -> None:
    paths = sorted(SAMPLES.glob("fa_*.json"))
    assert paths, "sample fixtures missing"
    for path in paths:
        # Round-trips through the same helper every read path now uses.
        assert load_verified_artifact(path)["artifact_id"] == path.stem


def test_verify_rejects_a_transposed_probability_via_content_hash() -> None:
    artifact = _sample_with_probs_no_matrix()
    tampered = copy.deepcopy(artifact)
    probs = tampered["forecast"]["probs"]
    probs["home"], probs["away"] = probs["away"], probs["home"]
    # The tamper is deliberately schema-valid (still sums to 1, no matrix to
    # contradict), so only the recomputed payload_sha256 can catch it.
    assert abs(sum(probs.values()) - 1.0) < 1e-9
    with pytest.raises(ValueError, match="payload_sha256 mismatch"):
        verify_artifact_integrity(tampered)


def test_verify_rejects_a_filename_that_does_not_match_content(tmp_path: Path) -> None:
    artifact = json.loads(sorted(SAMPLES.glob("fa_*.json"))[0].read_text())
    wrong = tmp_path / "fa_deadbeefdeadbeef0000.json"
    wrong.write_bytes(canonical_bytes(artifact) + b"\n")
    with pytest.raises(ValueError, match="does not match its content id"):
        load_verified_artifact(wrong)


def test_calibration_rejects_a_tampered_ledger(tmp_path: Path) -> None:
    """A ledger with an edited scored artifact must not silently skew the record."""
    ledger = tmp_path / "ledger"
    sealed = seal_forecast(
        pack_dir=REPO_ROOT / "packs/martj42-internationals-273c731492df",
        output_dir=ledger,
        date="2026-07-09",
        home_team="France",
        away_team="Morocco",
        as_of_utc="2026-07-08T00:00:00Z",
    )
    scored_path = score_forecast(
        artifact_path=sealed,
        newer_pack_dir=REPO_ROOT / "packs/martj42-internationals",
        output_dir=ledger,
    )
    # A clean ledger aggregates fine.
    assert calibration_summary(ledger)["running"]["n_scored"] == 1

    # Edit the recorded log loss (a number a reader trusts) without re-sealing.
    scored = json.loads(scored_path.read_text(encoding="utf-8"))
    scored["evaluation"]["metrics"]["log_loss"] = 0.0
    scored_path.write_bytes(canonical_bytes(scored) + b"\n")
    with pytest.raises(ValueError, match="payload_sha256 mismatch"):
        calibration_summary(ledger)


# --- H2: docs must not overclaim an unimplemented security control ------------

def test_docs_do_not_overclaim_pack_signature_verification() -> None:
    """No minisign pack SIGNATURE-verification code exists at this commit (only
    per-file sha256). Any shipped doc that mentions pack signing must mark it
    planned/gated/not-implemented, never assert it as an active control."""
    signing = re.compile(r"minisign|signature[- ]?verif|signed pack", re.IGNORECASE)
    qualifier = re.compile(
        r"planned|not yet|not implemented|gated|roadmap|hash-verified", re.IGNORECASE
    )
    for rel in ("SECURITY.md", "README.md", "packs/README.md"):
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), 1):
            if "pack" in line.lower() and signing.search(line):
                assert qualifier.search(line), (
                    f"{rel}:{i} presents pack signing as active without a "
                    f"planned/gated qualifier: {line.strip()!r}"
                )
    # Pin the corrected honest phrasing so the qualifier cannot be silently dropped.
    assert "not yet implemented" in (REPO_ROOT / "SECURITY.md").read_text(encoding="utf-8")
