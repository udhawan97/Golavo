"""Phase 3 forward-loop tests over two retained, pinned martj42 snapshots.

T0 (packs/martj42-internationals-273c731492df, upstream commit 2026-07-07T23:01:13Z)
carries France v Morocco 2026-07-09 as a SCHEDULED fixture; T1
(packs/martj42-internationals, upstream ref ddd7249…, retrieved
2026-07-10T19:35:25Z) carries the completed 2-0 result. Both packs are vendored
byte-exact, so the seal→score loop replays deterministically in CI without
waiting for a real match. Seal validity is anchored on the time the pinned data
state verifiably existed (the upstream commit time), while retrieval times stay
recorded as the honest fetch moments.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
from golavo_core.artifacts import (
    score_forecast,
    seal_forecast,
    validate_artifact,
    void_forecast,
)
from golavo_core.calibration import calibration_summary
from golavo_core.ingest import load_matches, snapshot_descriptor

REPO_ROOT = Path(__file__).resolve().parents[2]
T0_PACK = REPO_ROOT / "packs/martj42-internationals-273c731492df"
T1_PACK = REPO_ROOT / "packs/martj42-internationals"

FIXTURE = {
    "date": "2026-07-09",
    "home_team": "France",
    "away_team": "Morocco",
}
# T-24h relative to the conservative day-proxy kickoff (2026-07-09T00:00:00Z),
# and after T0's upstream commit time (2026-07-07T23:01:13Z).
AS_OF = "2026-07-08T00:00:00Z"


def _seal_t0(output_dir: Path, **overrides) -> Path:
    kwargs = {
        "pack_dir": T0_PACK,
        "output_dir": output_dir,
        "as_of_utc": AS_OF,
        "horizon": "T-24h",
        **FIXTURE,
        **overrides,
    }
    return seal_forecast(**kwargs)


def test_fixture_transitions_from_scheduled_to_completed_across_refs() -> None:
    t0 = load_matches(T0_PACK)
    t1 = load_matches(T1_PACK)
    at_t0 = t0.loc[
        t0["date"].eq("2026-07-09") & t0["home_team"].eq("France") & t0["away_team"].eq("Morocco")
    ]
    at_t1 = t1.loc[
        t1["date"].eq("2026-07-09") & t1["home_team"].eq("France") & t1["away_team"].eq("Morocco")
    ]
    assert len(at_t0) == 1 and len(at_t1) == 1
    assert not bool(at_t0.iloc[0]["is_complete"])
    assert bool(at_t1.iloc[0]["is_complete"])
    assert (int(at_t1.iloc[0]["home_score"]), int(at_t1.iloc[0]["away_score"])) == (2, 0)
    # Identity fields are byte-identical across refs, so the match_id is stable.
    assert at_t0.iloc[0]["match_id"] == at_t1.iloc[0]["match_id"]


def test_snapshot_anchor_records_upstream_commit_and_honest_retrieval() -> None:
    descriptor = snapshot_descriptor(T0_PACK)
    assert descriptor["upstream_committed_at_utc"] == "2026-07-07T23:01:13Z"
    # The pack was fetched days AFTER the fixture completed; the honest fetch
    # time stays recorded while sealing validates against the data-state anchor.
    assert descriptor["retrieved_at_utc"] > "2026-07-09"
    legacy = snapshot_descriptor(T1_PACK)
    assert "upstream_committed_at_utc" not in legacy


def test_forward_loop_replays_deterministically(tmp_path: Path) -> None:
    sealed_a = _seal_t0(tmp_path / "seal-a")
    sealed_b = _seal_t0(tmp_path / "seal-b")
    assert sealed_a.name == sealed_b.name
    assert sealed_a.read_bytes() == sealed_b.read_bytes()
    sealed_bytes = sealed_a.read_bytes()

    sealed = json.loads(sealed_bytes)
    validate_artifact(sealed)
    assert sealed["schema_version"] == "0.2.0"
    assert sealed["status"] == "sealed"
    assert sealed["supersedes"] is None
    assert sealed["match"]["kickoff_utc"] == "2026-07-09T00:00:00Z"
    assert sealed["forecast"]["sealed_at_utc"] == AS_OF
    assert sealed["inputs"]["training_cutoff_utc"] == AS_OF
    snapshot = sealed["inputs"]["snapshots"][0]
    assert snapshot["upstream_ref"] == "273c731492df960cae363317e8e78e2be4b4b7cf"
    assert snapshot["upstream_committed_at_utc"] == "2026-07-07T23:01:13Z"
    probs = sealed["forecast"]["probs"]
    assert probs is not None
    assert abs(sum(probs.values()) - 1.0) < 1e-6

    scored_a = score_forecast(
        artifact_path=sealed_a, newer_pack_dir=T1_PACK, output_dir=tmp_path / "score-a"
    )
    scored_b = score_forecast(
        artifact_path=sealed_a, newer_pack_dir=T1_PACK, output_dir=tmp_path / "score-b"
    )
    assert scored_a.read_bytes() == scored_b.read_bytes()

    scored = json.loads(scored_a.read_bytes())
    validate_artifact(scored)
    assert scored["status"] == "scored"
    assert scored["supersedes"] == sealed["artifact_id"]
    assert scored["artifact_id"] != sealed["artifact_id"]
    assert scored["forecast"]["probs"] == probs
    assert scored["evaluation"]["actual"] == {
        "home_goals": 2,
        "away_goals": 0,
        "outcome": "home",
    }
    assert scored["evaluation"]["scored_at_utc"] == "2026-07-10T19:35:25Z"
    metrics = scored["evaluation"]["metrics"]
    assert metrics["prob_assigned_to_outcome"] == round(probs["home"], 6)
    assert metrics["log_loss"] == pytest.approx(-math.log(probs["home"]), abs=1e-5)
    expected_brier = (
        (probs["home"] - 1.0) ** 2 + probs["draw"] ** 2 + probs["away"] ** 2
    )
    assert metrics["brier"] == pytest.approx(expected_brier, abs=1e-5)
    # The seal is immutable: scoring appended a successor, never an edit.
    assert sealed_a.read_bytes() == sealed_bytes
    assert (tmp_path / "score-a" / f"{scored['artifact_id']}.json").exists()


def test_seal_rejects_as_of_before_the_data_state_existed(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="data state existed"):
        _seal_t0(tmp_path, as_of_utc="2026-07-07T22:00:00Z")


def test_seal_rejects_as_of_at_or_after_day_proxy_kickoff(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="before kickoff"):
        _seal_t0(tmp_path, as_of_utc="2026-07-09T00:00:00Z")


def test_seal_rejects_fixtures_that_already_have_results(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="already has a result"):
        _seal_t0(
            tmp_path,
            date="2026-07-07",
            home_team="Switzerland",
            away_team="Colombia",
            as_of_utc="2026-07-08T00:00:00Z",
        )


def test_score_requires_a_strictly_newer_data_state(tmp_path: Path) -> None:
    sealed = _seal_t0(tmp_path / "sealed")
    with pytest.raises(ValueError, match="strictly newer"):
        score_forecast(
            artifact_path=sealed, newer_pack_dir=T0_PACK, output_dir=tmp_path / "scored"
        )


def test_score_refuses_a_fixture_that_is_still_scheduled(tmp_path: Path) -> None:
    # Spain v Belgium (2026-07-10) is scheduled at T0 and STILL scheduled at T1.
    sealed = _seal_t0(
        tmp_path / "sealed",
        date="2026-07-10",
        home_team="Spain",
        away_team="Belgium",
        horizon="T-72h",
    )
    with pytest.raises(ValueError, match="completed result"):
        score_forecast(
            artifact_path=sealed, newer_pack_dir=T1_PACK, output_dir=tmp_path / "scored"
        )


def test_void_supersedes_with_reason_and_without_a_result(tmp_path: Path) -> None:
    sealed_path = _seal_t0(
        tmp_path / "sealed",
        date="2026-07-10",
        home_team="Spain",
        away_team="Belgium",
        horizon="T-72h",
    )
    sealed_bytes = sealed_path.read_bytes()
    with pytest.raises(ValueError, match="recorded reason"):
        void_forecast(
            artifact_path=sealed_path,
            output_dir=tmp_path / "voided",
            voided_at_utc="2026-07-10T19:35:25Z",
            reason="   ",
        )
    reason = "postponed in the newer snapshot; no result will be fabricated"
    voided_a = void_forecast(
        artifact_path=sealed_path,
        output_dir=tmp_path / "voided-a",
        voided_at_utc="2026-07-10T19:35:25Z",
        reason=reason,
    )
    voided_b = void_forecast(
        artifact_path=sealed_path,
        output_dir=tmp_path / "voided-b",
        voided_at_utc="2026-07-10T19:35:25Z",
        reason=reason,
    )
    assert voided_a.read_bytes() == voided_b.read_bytes()
    voided = json.loads(voided_a.read_bytes())
    validate_artifact(voided)
    sealed = json.loads(sealed_bytes)
    assert voided["status"] == "voided"
    assert voided["supersedes"] == sealed["artifact_id"]
    assert voided["void_reason"] == reason
    assert voided["evaluation"] is None
    assert voided["forecast"]["probs"] == sealed["forecast"]["probs"]
    assert sealed_path.read_bytes() == sealed_bytes

    # A voided successor is terminal: it can be neither scored nor re-voided.
    with pytest.raises(ValueError, match="only a non-abstained sealed"):
        score_forecast(
            artifact_path=voided_a, newer_pack_dir=T1_PACK, output_dir=tmp_path / "scored"
        )
    with pytest.raises(ValueError, match="sealed or abstained"):
        void_forecast(
            artifact_path=voided_a,
            output_dir=tmp_path / "revoided",
            voided_at_utc="2026-07-11T00:00:00Z",
            reason="double void must fail",
        )


def test_scored_artifacts_cannot_be_voided(tmp_path: Path) -> None:
    sealed = _seal_t0(tmp_path / "sealed")
    scored = score_forecast(
        artifact_path=sealed, newer_pack_dir=T1_PACK, output_dir=tmp_path / "scored"
    )
    with pytest.raises(ValueError, match="sealed or abstained"):
        void_forecast(
            artifact_path=scored,
            output_dir=tmp_path / "voided",
            voided_at_utc="2026-07-11T00:00:00Z",
            reason="results are final; voiding a scored artifact must fail",
        )


def _build_ledger(ledger: Path) -> tuple[Path, Path]:
    """One scored chain (France–Morocco) and one voided chain (Spain–Belgium)."""
    sealed_scored = _seal_t0(ledger)
    score_forecast(artifact_path=sealed_scored, newer_pack_dir=T1_PACK, output_dir=ledger)
    sealed_voided = _seal_t0(
        ledger,
        date="2026-07-10",
        home_team="Spain",
        away_team="Belgium",
        horizon="T-72h",
    )
    void_forecast(
        artifact_path=sealed_voided,
        output_dir=ledger,
        voided_at_utc="2026-07-10T19:35:25Z",
        reason="postponement drill: fixture never completed in the newer snapshot",
    )
    return sealed_scored, sealed_voided


def test_calibration_summary_aggregates_real_chains(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    sealed_scored, sealed_voided = _build_ledger(ledger)
    summary = calibration_summary(ledger)
    assert summary == calibration_summary(ledger)  # pure function of the ledger
    assert summary["schema_version"] == "0.2.0"
    assert summary["counts"] == {
        "sealed": 2,
        "abstained": 0,
        "scored": 1,
        "voided": 1,
        "pending": 0,
    }

    chains = summary["chains"]
    assert [c["match"]["kickoff_utc"] for c in chains] == [
        "2026-07-09T00:00:00Z",
        "2026-07-10T00:00:00Z",
    ]
    scored_chain, voided_chain = chains
    sealed = json.loads(sealed_scored.read_bytes())
    assert scored_chain["sealed_artifact_id"] == sealed["artifact_id"]
    assert scored_chain["probs"] == sealed["forecast"]["probs"]
    assert scored_chain["resolution"]["status"] == "scored"
    assert scored_chain["resolution"]["actual"]["outcome"] == "home"
    metrics = scored_chain["resolution"]["metrics"]
    assert summary["running"] == {
        "n_scored": 1,
        "log_loss": metrics["log_loss"],
        "brier": metrics["brier"],
        "prob_assigned_to_outcome": metrics["prob_assigned_to_outcome"],
    }
    assert sum(bin["count"] for bin in summary["reliability_bins"]) == 1
    assert voided_chain["sealed_artifact_id"] == json.loads(sealed_voided.read_bytes())[
        "artifact_id"
    ]
    assert voided_chain["resolution"]["status"] == "voided"
    assert voided_chain["resolution"]["actual"] is None
    assert "postponement drill" in voided_chain["resolution"]["void_reason"]


def test_calibration_summary_of_an_empty_or_missing_ledger(tmp_path: Path) -> None:
    summary = calibration_summary(tmp_path / "does-not-exist")
    assert summary["counts"] == {
        "sealed": 0,
        "abstained": 0,
        "scored": 0,
        "voided": 0,
        "pending": 0,
    }
    assert summary["running"] is None
    assert summary["chains"] == []
    assert summary["reliability_bins"] == []


def test_calibration_rejects_a_double_resolved_seal(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    sealed = _seal_t0(ledger)
    score_forecast(artifact_path=sealed, newer_pack_dir=T1_PACK, output_dir=ledger)
    # void_forecast only sees the seal file, so the conflict must surface at
    # ledger aggregation: one seal never resolves twice.
    void_forecast(
        artifact_path=sealed,
        output_dir=ledger,
        voided_at_utc="2026-07-11T00:00:00Z",
        reason="conflicting resolution for the integrity test",
    )
    with pytest.raises(ValueError, match="resolves exactly once"):
        calibration_summary(ledger)
