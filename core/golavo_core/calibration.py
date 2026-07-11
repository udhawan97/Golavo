"""Aggregate the REAL sealed-forecast ledger into a calibration record.

This reads immutable ForecastArtifacts from the ledger directory — genuine
sealed→scored/voided chains — and never evaluation backtests. The record is a
pure, deterministic function of the ledger contents: no wall clock, no network.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from jsonschema import Draft202012Validator, FormatChecker

from golavo_core.artifacts import _schema_path, validate_artifact
from golavo_core.evaluation import _metrics

SCHEMA_VERSION = "0.2.0"
_OUTCOME_INDEX = {"home": 0, "draw": 1, "away": 2}
_ROOT_STATUSES = {"sealed", "abstained"}
_RESOLUTION_STATUSES = {"scored", "voided"}


def _load_ledger(artifact_dir: Path) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    if artifact_dir.is_dir():
        for path in sorted(artifact_dir.glob("fa_*.json")):
            artifact = json.loads(path.read_text(encoding="utf-8"))
            validate_artifact(artifact)
            artifacts.append(artifact)
    return artifacts


def _chain_pairs(
    artifacts: list[dict[str, Any]],
) -> list[tuple[dict[str, Any], dict[str, Any] | None]]:
    """Pair each root seal with its at-most-one resolving successor."""
    by_id = {artifact["artifact_id"]: artifact for artifact in artifacts}
    successors: dict[str, dict[str, Any]] = {}
    for artifact in artifacts:
        superseded = artifact.get("supersedes")
        if superseded is None:
            if artifact["status"] not in _ROOT_STATUSES:
                raise ValueError(
                    f"{artifact['artifact_id']}: a {artifact['status']} artifact must "
                    "supersede the seal it resolves"
                )
            continue
        if superseded not in by_id:
            raise ValueError(
                f"{artifact['artifact_id']} supersedes {superseded}, which is not in the ledger"
            )
        if artifact["status"] not in _RESOLUTION_STATUSES:
            raise ValueError(f"{artifact['artifact_id']}: only scored/voided supersede a seal")
        if superseded in successors:
            raise ValueError(
                f"{superseded} has two successors; a seal resolves exactly once"
            )
        successors[superseded] = artifact
    roots = [artifact for artifact in artifacts if artifact.get("supersedes") is None]
    roots.sort(key=lambda a: (a["match"]["kickoff_utc"], a["artifact_id"]))
    return [(root, successors.get(root["artifact_id"])) for root in roots]


def _resolution(successor: dict[str, Any] | None) -> dict[str, Any]:
    if successor is None:
        return {
            "status": "pending",
            "artifact_id": None,
            "resolved_at_utc": None,
            "actual": None,
            "metrics": None,
            "void_reason": None,
        }
    evaluation = successor.get("evaluation")
    return {
        "status": successor["status"],
        "artifact_id": successor["artifact_id"],
        "resolved_at_utc": (
            evaluation["scored_at_utc"]
            if evaluation is not None
            else successor["provenance"]["created_at_utc"]
        ),
        "actual": None if evaluation is None else evaluation["actual"],
        "metrics": None if evaluation is None else evaluation["metrics"],
        "void_reason": successor.get("void_reason"),
    }


def calibration_summary(
    artifact_dir: Path,
    *,
    generated_from: str = "data/artifacts (real sealed forecasts; never backtests)",
) -> dict[str, Any]:
    """Build the deterministic calibration record for one ledger directory."""
    pairs = _chain_pairs(_load_ledger(artifact_dir))
    chains: list[dict[str, Any]] = []
    scored_probs: list[list[float]] = []
    scored_outcomes: list[int] = []
    counts = {"sealed": 0, "abstained": 0, "scored": 0, "voided": 0, "pending": 0}
    for root, successor in pairs:
        resolution = _resolution(successor)
        counts[root["status"]] += 1
        counts[resolution["status"]] += 1
        chains.append(
            {
                "sealed_artifact_id": root["artifact_id"],
                "match": root["match"],
                "sealed_at_utc": root["forecast"]["sealed_at_utc"],
                "horizon": root["forecast"]["horizon"],
                "family": root["model"]["family"],
                "abstained": root["forecast"]["abstained"],
                "probs": root["forecast"]["probs"],
                "resolution": resolution,
            }
        )
        if resolution["status"] == "scored":
            probs = root["forecast"]["probs"]
            scored_probs.append([probs["home"], probs["draw"], probs["away"]])
            scored_outcomes.append(_OUTCOME_INDEX[resolution["actual"]["outcome"]])

    running: dict[str, Any] | None = None
    reliability_bins: list[dict[str, Any]] = []
    if scored_probs:
        probs_array = np.array(scored_probs, dtype=float)
        outcomes_array = np.array(scored_outcomes, dtype=int)
        metrics = _metrics(probs_array, outcomes_array)
        assigned = probs_array[np.arange(len(scored_outcomes)), outcomes_array]
        running = {
            "n_scored": len(scored_outcomes),
            "log_loss": metrics["log_loss"],
            "brier": metrics["brier"],
            "prob_assigned_to_outcome": round(float(assigned.mean()), 6),
        }
        reliability_bins = metrics["reliability_bins"]

    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_from": generated_from,
        "primary_metric": "log_loss",
        "counts": counts,
        "running": running,
        "reliability_bins": reliability_bins,
        "chains": chains,
    }
    _validate_calibration(summary)
    return summary


def _validate_calibration(summary: dict[str, Any]) -> None:
    schema = json.loads(_schema_path().read_text(encoding="utf-8"))
    wrapper = {
        "$schema": schema["$schema"],
        "$ref": "#/$defs/CalibrationSummary",
        "$defs": schema["$defs"],
    }
    Draft202012Validator(wrapper, format_checker=FormatChecker()).validate(summary)
    totals = summary["counts"]
    if totals["sealed"] + totals["abstained"] != (
        totals["scored"] + totals["voided"] + totals["pending"]
    ):
        raise ValueError("calibration counts do not reconcile roots with resolutions")
