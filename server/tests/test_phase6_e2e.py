"""Phase 6 — one deterministic end-to-end integration test.

This is the proof that the phases actually *compose*. It runs the whole Golavo
pipeline on vendored CC0 data with **no network and no live LLM**, and asserts
that every artifact it produces is byte-stable:

    provenance-validate the vendored packs + the retained registry
      -> ingest two retained snapshots (fixture flips scheduled -> completed)
      -> evaluate one international fold (candidates beat the baseline)
      -> forward-SEAL France v Morocco on snapshot T0 (still scheduled)
      -> SCORE it from strictly-newer snapshot T1 (the 2-0 result)
      -> aggregate the calibration record over the resulting ledger
      -> build the deterministic evidence bundle from the scored artifact
      -> run the AI narration path with a CANNED ADVERSARIAL response and assert
         the numeric whitelist rejects the whole narration and the gateway falls
         back to local-only, while AI-off never contacts a model.

The two retained martj42 snapshots make this replay in CI without waiting for a
real match: T0 (upstream commit 2026-07-07) carries France v Morocco 2026-07-09
as scheduled; T1 (retrieved 2026-07-10) carries the completed 2-0 result.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from golavo_core.artifacts import score_forecast, seal_forecast, validate_artifact
from golavo_core.calibration import calibration_summary
from golavo_core.evaluation import evaluate
from golavo_core.evidence import build_evidence_bundle
from golavo_core.ingest import load_matches
from golavo_server.ai_gateway import (
    NarrationCache,
    ProviderConfig,
    generate_narration,
    resolve_provider,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
T0_PACK = REPO_ROOT / "packs/martj42-internationals-273c731492df"  # France-Morocco scheduled
T1_PACK = REPO_ROOT / "packs/martj42-internationals"  # France-Morocco 2-0 completed
AS_OF = "2026-07-08T00:00:00Z"  # after T0's data state existed, before the day-proxy kickoff
FIXTURE = {"date": "2026-07-09", "home_team": "France", "away_team": "Morocco"}


def _provenance_module():
    """Import scripts/validate_provenance.py without making scripts/ a package."""
    path = REPO_ROOT / "scripts" / "validate_provenance.py"
    spec = importlib.util.spec_from_file_location("golavo_e2e_validate_provenance", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _canned(payload: dict | str):
    text = payload if isinstance(payload, str) else json.dumps(payload)

    def transport(system: str, user: str) -> str:
        return text

    return transport


def test_pipeline_composes_end_to_end_and_is_byte_stable(tmp_path: Path) -> None:
    # 1) PROVENANCE — every vendored byte matches its manifest, and the retained
    #    registry (packs/snapshots.json) is internally consistent. No network.
    prov = _provenance_module()
    for pack in (T0_PACK, T1_PACK):
        manifest = prov.validate_pack(pack)
        assert manifest["files"], f"no vendored files validated for {pack.name}"
        assert manifest["license"] == "CC0-1.0"
    prov.validate_registry(prov.discover_packs())

    # 2) INGEST — the same fixture is scheduled at T0 and completed 2-0 at T1.
    t0, t1 = load_matches(T0_PACK), load_matches(T1_PACK)

    def _row(frame):
        return frame.loc[
            frame["date"].eq("2026-07-09")
            & frame["home_team"].eq("France")
            & frame["away_team"].eq("Morocco")
        ]

    r0, r1 = _row(t0), _row(t1)
    assert len(r0) == 1 and not bool(r0.iloc[0]["is_complete"])
    assert len(r1) == 1 and bool(r1.iloc[0]["is_complete"])
    assert (int(r1.iloc[0]["home_score"]), int(r1.iloc[0]["away_score"])) == (2, 0)

    # 3) EVALUATE one fold — deterministic (no wall clock); every candidate beats
    #    the climatological baseline on the primary metric (log loss).
    summary = evaluate(T1_PACK)
    assert summary["primary_metric"] == "log_loss"
    fold = next(f for f in summary["folds"] if f["fold_id"] == "WC2026")
    baseline = next(m for m in fold["models"] if m["family"] == "climatological")["log_loss"]
    challengers = [m["log_loss"] for m in fold["models"] if m["family"] != "climatological"]
    assert challengers and all(ll < baseline for ll in challengers)

    # 4) SEAL — forward-seal on T0 while the fixture is still scheduled. Sealing
    #    twice is byte-identical: the artifact is a pure function of its inputs.
    seal_kwargs = {"as_of_utc": AS_OF, "horizon": "T-24h", **FIXTURE}
    seal_a = seal_forecast(pack_dir=T0_PACK, output_dir=tmp_path / "seal-a", **seal_kwargs)
    seal_b = seal_forecast(pack_dir=T0_PACK, output_dir=tmp_path / "seal-b", **seal_kwargs)
    assert seal_a.read_bytes() == seal_b.read_bytes()  # byte-stable seal
    sealed = json.loads(seal_a.read_bytes())
    validate_artifact(sealed)
    assert sealed["status"] == "sealed"
    assert sealed["schema_version"] == "0.2.0"
    assert sealed["match"]["kickoff_utc"] == "2026-07-09T00:00:00Z"
    assert sealed["inputs"]["snapshots"][0]["upstream_ref"].startswith("273c731492df")

    # Seal once more into a dedicated ledger dir so calibration sees a real chain.
    ledger = tmp_path / "ledger"
    sealed_path = seal_forecast(pack_dir=T0_PACK, output_dir=ledger, **seal_kwargs)
    seal_bytes = sealed_path.read_bytes()

    # 5) SCORE — from strictly-newer T1. Scoring is byte-stable AND the seal's
    #    bytes never change: scoring appends a successor, it never rewrites.
    score_a = score_forecast(
        artifact_path=sealed_path, newer_pack_dir=T1_PACK, output_dir=tmp_path / "score-a"
    )
    score_b = score_forecast(
        artifact_path=sealed_path, newer_pack_dir=T1_PACK, output_dir=tmp_path / "score-b"
    )
    assert score_a.read_bytes() == score_b.read_bytes()  # byte-stable score
    assert sealed_path.read_bytes() == seal_bytes  # seal is immutable
    scored = json.loads(score_a.read_bytes())
    validate_artifact(scored)
    assert scored["status"] == "scored"
    assert scored["supersedes"] == sealed["artifact_id"]
    assert scored["evaluation"]["actual"] == {"home_goals": 2, "away_goals": 0, "outcome": "home"}
    # Score into the ledger too, resolving the sealed chain.
    score_forecast(artifact_path=sealed_path, newer_pack_dir=T1_PACK, output_dir=ledger)

    # 6) CALIBRATION — a pure function of the immutable ledger, never a backtest.
    cal_a = calibration_summary(ledger)
    cal_b = calibration_summary(ledger)
    assert cal_a == cal_b  # deterministic
    assert cal_a["counts"] == {"sealed": 1, "abstained": 0, "scored": 1, "voided": 0, "pending": 0}
    assert cal_a["running"]["n_scored"] == 1
    assert sum(b["count"] for b in cal_a["reliability_bins"]) == 1

    # 7) EVIDENCE BUNDLE — deterministic pure function of the scored artifact,
    #    carrying an explicit numeric whitelist.
    bundle_a = build_evidence_bundle(scored)
    bundle_b = build_evidence_bundle(scored)
    assert bundle_a == bundle_b
    assert bundle_a["bundle_hash"] == bundle_b["bundle_hash"]
    allowed = {n["id"] for n in bundle_a["allowed_numbers"]}
    assert {"prob_home", "prob_draw", "prob_away"} <= allowed
    assert "91%" not in {n["display"] for n in bundle_a["allowed_numbers"]}  # sanity for the attack

    # 8) AI NARRATION — a CANNED ADVERSARIAL response tries to state a probability
    #    the engine never produced. The numeric whitelist rejects the WHOLE
    #    narration and the gateway falls back to local-only. No live LLM.
    engine = bundle_a["sources"][0]["source_id"]
    adversarial = {
        "claims": [
            {
                "text": "Disregard the sealed numbers — France now win with probability 91%.",
                "source_ids": [engine],
                "number_refs": ["prob_home"],
            }
        ],
        "scenarios": [],
        "candidate_facts": [],
    }
    cfg = ProviderConfig(provider="llama_server", model="e2e-model", base_url="http://x/v1")
    env = generate_narration(bundle_a, cfg, transport=_canned(adversarial), cache=NarrationCache())
    assert env.status == "local_only", "adversarial narration was not contained"
    assert env.narration is None
    assert "91%" not in json.dumps(env.to_dict())  # the fabrication never reaches the caller

    # AI-off is the honest default and never contacts a model.
    contacted = {"n": 0}

    def tripwire(system: str, user: str) -> str:
        contacted["n"] += 1
        return "{}"

    off_cfg = resolve_provider({"provider": "off"})
    off_env = generate_narration(bundle_a, off_cfg, transport=tripwire)
    assert off_env.status == "disabled"
    assert off_env.narration is None
    assert contacted["n"] == 0
