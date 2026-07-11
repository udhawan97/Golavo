#!/usr/bin/env python3
"""Generate deterministic synthetic ForecastArtifact contract fixtures."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "core"))

from golavo_core.artifacts import canonical_bytes, payload_sha256, validate_artifact  # noqa: E402
from golavo_core.calibration import calibration_summary  # noqa: E402
from golavo_core.models.candidates import PoissonModel  # noqa: E402
from golavo_core.score_matrix import (  # noqa: E402
    build_score_matrix,
    expected_goals,
    outcome_probabilities,
)

_POISSON_FAMILIES = {"poisson_independent", "dixon_coles", "bivariate_poisson"}


def _goal_forecast(
    index: int, family: str
) -> tuple[dict[str, float], dict[str, float], dict[str, Any]]:
    """Coherent (probs, expected_goals, score_matrix) from a real Poisson matrix.

    Rates vary with the fixture index so the suite covers a range of scorelines.
    Everything is derived from ONE matrix, so the fixture satisfies the same
    coherence invariant validate_artifact enforces on real seals — the residual
    (largest outcome) absorbs six-decimal rounding so the probabilities sum to 1.
    """
    home_rate = round(1.15 + 0.10 * index, 4)
    away_rate = round(max(0.35, 1.30 - 0.05 * index), 4)
    matrix = PoissonModel(family)._matrix(home_rate, away_rate)
    home, draw, away = outcome_probabilities(matrix)
    raw = {"home": home, "draw": draw, "away": away}
    ordered = sorted(raw, key=raw.__getitem__)  # ascending; residual goes on the largest
    probs = {ordered[0]: round(raw[ordered[0]], 6), ordered[1]: round(raw[ordered[1]], 6)}
    probs[ordered[2]] = round(1.0 - probs[ordered[0]] - probs[ordered[1]], 6)
    eg_home, eg_away = expected_goals(matrix)
    expected = {"home": round(eg_home, 6), "away": round(eg_away, 6)}
    return {k: probs[k] for k in ("home", "draw", "away")}, expected, build_score_matrix(matrix)

OUTPUT_DIR = REPO_ROOT / "data/fixtures/sample_artifacts"
UI_CALIBRATION_MOCK = REPO_ROOT / "ui/src/mocks/calibration.json"
UI_FORECAST_MOCKS = REPO_ROOT / "ui/src/mocks/forecasts"
SNAPSHOT_HASH = hashlib.sha256(
    (REPO_ROOT / "data/fixtures/martj42-results-subset.csv").read_bytes()
).hexdigest()
PARAMS_HASH = hashlib.sha256(b'{"synthetic_fixture":true}').hexdigest()


def _base(index: int, status: str) -> dict[str, Any]:
    abstained = status == "abstained"
    family = ("elo_ordlogit", "poisson_independent", "dixon_coles")[index % 3]
    # Goal-based families carry a coherent exact-score matrix (Phase 8); elo has no
    # goal model, so it exercises the honest "no score distribution" state; abstained
    # fixtures carry no forecast at all.
    score_matrix: dict[str, Any] | None = None
    if abstained:
        probs = None
        expected_goals_value = None
    elif family in _POISSON_FAMILIES:
        probs, expected_goals_value, score_matrix = _goal_forecast(index, family)
    else:
        home = round(0.46 + index * 0.01, 6)
        draw = 0.27
        probs = {"home": home, "draw": draw, "away": round(1.0 - home - draw, 6)}
        expected_goals_value = None
    forecast: dict[str, Any] = {
        "market": "1x2_regulation",
        "sealed_at_utc": f"2030-01-{index + 9:02d}T18:00:00Z",
        "horizon": ("T-72h", "T-24h", "T-60m")[index % 3],
        "probs": probs,
        "expected_goals": expected_goals_value,
        "abstained": abstained,
        "abstain_reason": "synthetic insufficient-data fixture" if abstained else None,
        "uncertainty": "high" if abstained else ("low", "medium")[index % 2],
    }
    if score_matrix is not None:
        forecast["score_matrix"] = score_matrix
    return {
        "schema_version": "0.2.0",
        "artifact_id": "fa_pending00",
        "status": status,
        "supersedes": None,
        "match": {
            "match_id": f"m_synthetic_{index:02d}",
            "competition": "Synthetic contract fixture",
            "stage": "Acceptance test",
            "kickoff_utc": f"2030-01-{index + 10:02d}T18:00:00Z",
            "home_team": f"Example Home {index}",
            "away_team": f"Example Away {index}",
            "neutral_venue": index % 2 == 0,
            "city": "Example City",
            "country": "Example Country",
        },
        "forecast": forecast,
        "model": {
            "model_id": "synthetic_contract_fixture",
            "family": family,
            "version": "0.1.0",
            "params_hash": PARAMS_HASH,
            "code_git_sha": "0000000",
            "seed": 20260710,
        },
        "inputs": {
            "training_cutoff_utc": f"2030-01-{index + 9:02d}T18:00:00Z",
            "snapshots": [
                {
                    "snapshot_id": "sp_synthetic_fixture_v1",
                    "source_id": "golavo-synthetic-contract-fixtures",
                    "url": "https://github.com/udhawan97/Golavo/tree/main/data/fixtures",
                    "upstream_ref": "phase0-fixtures-v1",
                    "retrieved_at_utc": "2030-01-01T00:00:00Z",
                    "sha256": SNAPSHOT_HASH,
                    "license": "CC0-1.0 excerpt; synthetic fields are test-only",
                }
            ],
        },
        "provenance": {
            "created_at_utc": f"2030-01-{index + 9:02d}T18:00:00Z",
            "generator": "golavo-sample-fixtures/0.2.0",
            "deterministic": True,
            "payload_sha256": "0" * 64,
        },
        "evaluation": None,
    }


def _finalize(artifact: dict[str, Any]) -> dict[str, Any]:
    stable = copy.deepcopy(artifact)
    stable.pop("artifact_id")
    stable["provenance"].pop("payload_sha256")
    artifact["artifact_id"] = f"fa_{hashlib.sha256(canonical_bytes(stable)).hexdigest()[:20]}"
    artifact["provenance"]["payload_sha256"] = payload_sha256(artifact)
    validate_artifact(artifact)
    return artifact


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUTPUT_DIR.glob("fa_*.json"):
        old.unlink()
    artifacts = [_finalize(_base(index, status)) for index, status in enumerate(
        ("sealed", "sealed", "sealed", "scored", "scored", "abstained", "abstained", "voided"),
        start=1,
    )]
    for index in (3, 4):
        artifact = artifacts[index]
        artifact["supersedes"] = artifacts[index - 3]["artifact_id"]
        probs = artifact["forecast"]["probs"]
        outcome = "home" if index == 3 else "away"
        assigned = probs[outcome]
        actual = {"home_goals": 2, "away_goals": 1, "outcome": "home"}
        if outcome == "away":
            actual = {"home_goals": 0, "away_goals": 1, "outcome": "away"}
        one_hot = {"home": 0.0, "draw": 0.0, "away": 0.0}
        one_hot[outcome] = 1.0
        artifact["evaluation"] = {
            "actual": actual,
            "scored_at_utc": "2030-02-01T00:00:00Z",
            "metrics": {
                "log_loss": round(-__import__("math").log(assigned), 6),
                "brier": round(sum((probs[key] - one_hot[key]) ** 2 for key in one_hot), 6),
                "prob_assigned_to_outcome": assigned,
            },
        }
        artifact["provenance"]["created_at_utc"] = "2030-02-01T00:00:00Z"
        artifacts[index] = _finalize(artifact)
    # The voided sample supersedes its OWN sealed root (a seal resolves exactly
    # once, so it must not share a root with a scored sample).
    artifacts[7]["supersedes"] = artifacts[2]["artifact_id"]
    artifacts[7]["void_reason"] = "synthetic postponement fixture (contract example)"
    artifacts[7]["provenance"]["created_at_utc"] = "2030-02-01T00:00:00Z"
    artifacts[7] = _finalize(artifacts[7])
    for artifact in artifacts:
        path = OUTPUT_DIR / f"{artifact['artifact_id']}.json"
        path.write_bytes(canonical_bytes(artifact) + b"\n")
    print(f"wrote {len(artifacts)} sample artifacts to {OUTPUT_DIR}")

    # The UI's bundled mocks are these same fixtures, so every artifact id the
    # mock calibration record references resolves in the mock forecast list.
    UI_FORECAST_MOCKS.mkdir(parents=True, exist_ok=True)
    for old in UI_FORECAST_MOCKS.glob("fa_*.json"):
        old.unlink()
    for artifact in artifacts:
        path = UI_FORECAST_MOCKS / f"{artifact['artifact_id']}.json"
        path.write_bytes(canonical_bytes(artifact) + b"\n")
    print(f"wrote {len(artifacts)} forecast mocks to {UI_FORECAST_MOCKS}")

    # Keep the UI's bundled calibration mock in lockstep with the fixtures by
    # running the REAL aggregator over the synthetic sample ledger.
    label = "data/fixtures/sample_artifacts (synthetic contract fixtures — not forecasts)"
    mock = calibration_summary(OUTPUT_DIR, generated_from=label)
    UI_CALIBRATION_MOCK.write_text(
        json.dumps(mock, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {UI_CALIBRATION_MOCK}")


if __name__ == "__main__":
    main()
