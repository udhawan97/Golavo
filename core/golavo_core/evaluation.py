"""Strictly chronological Phase 0 evaluation and calibration reporting."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from jsonschema import Draft202012Validator, FormatChecker

from golavo_core.ingest import load_match_table, snapshot_descriptor, training_rows
from golavo_core.models import FAMILIES, fit_model

FOLDS = (
    {
        "fold_id": "WC2022",
        "competition": "FIFA World Cup",
        "window_start": "2022-11-20",
        "window_end": "2022-12-18",
    },
    {
        "fold_id": "EURO2024",
        "competition": "UEFA Euro",
        "window_start": "2024-06-14",
        "window_end": "2024-07-14",
    },
    {
        "fold_id": "WC2026",
        "competition": "FIFA World Cup",
        "window_start": "2026-06-11",
        "window_end": "2026-07-19",
    },
)


def _outcomes(matches: pd.DataFrame) -> np.ndarray:
    return np.where(
        matches["home_score"].to_numpy() > matches["away_score"].to_numpy(),
        0,
        np.where(
            matches["home_score"].to_numpy() == matches["away_score"].to_numpy(), 1, 2
        ),
    )


def _wilson(successes: int, total: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if total == 0:
        return (math.nan, math.nan)
    p = successes / total
    denominator = 1.0 + z * z / total
    centre = (p + z * z / (2.0 * total)) / denominator
    margin = z * math.sqrt((p * (1.0 - p) + z * z / (4.0 * total)) / total) / denominator
    return max(0.0, centre - margin), min(1.0, centre + margin)


def _metrics(probs: np.ndarray, outcomes: np.ndarray) -> dict[str, Any]:
    assigned = np.clip(probs[np.arange(len(outcomes)), outcomes], 1e-12, 1.0)
    one_hot = np.eye(3)[outcomes]
    log_loss = float(-np.log(assigned).mean())
    brier = float(np.square(probs - one_hot).sum(axis=1).mean())
    cumulative_probs = np.cumsum(probs, axis=1)[:, :2]
    cumulative_actual = np.cumsum(one_hot, axis=1)[:, :2]
    rps = float(np.square(cumulative_probs - cumulative_actual).sum(axis=1).mean() / 2.0)

    confidence = probs.max(axis=1)
    predicted = probs.argmax(axis=1)
    correct = predicted == outcomes
    bins: list[dict[str, Any]] = []
    ece = 0.0
    boundaries = np.linspace(0.0, 1.0, 11)
    for index, (lower, upper) in enumerate(zip(boundaries[:-1], boundaries[1:], strict=True)):
        mask = (confidence >= lower) & (
            confidence <= upper if index == len(boundaries) - 2 else confidence < upper
        )
        count = int(mask.sum())
        if count:
            mean_confidence = float(confidence[mask].mean())
            successes = int(correct[mask].sum())
            accuracy = successes / count
            low, high = _wilson(successes, count)
            ece += count / len(outcomes) * abs(accuracy - mean_confidence)
            row = {
                "lower": round(float(lower), 6),
                "upper": round(float(upper), 6),
                "count": count,
                "mean_confidence": round(mean_confidence, 6),
                "accuracy": round(accuracy, 6),
                "wilson_low": round(low, 6),
                "wilson_high": round(high, 6),
            }
        else:
            row = {
                "lower": round(float(lower), 6),
                "upper": round(float(upper), 6),
                "count": 0,
                "mean_confidence": None,
                "accuracy": None,
                "wilson_low": None,
                "wilson_high": None,
            }
        bins.append(row)
    return {
        "log_loss": round(log_loss, 6),
        "brier": round(brier, 6),
        "ece": round(ece, 6),
        "rps": round(rps, 6),
        "reliability_bins": bins,
    }


def _predict_frame(model: Any, matches: pd.DataFrame) -> np.ndarray:
    return np.array(
        [
            model.predict(str(row.home_team), str(row.away_team), bool(row.neutral)).probs
            for row in matches.itertuples(index=False)
        ],
        dtype=float,
    )


def _tune_dixon_coles_xi(train: pd.DataFrame, cutoff_utc: str) -> float:
    cutoff = pd.Timestamp(cutoff_utc)
    cutoff = cutoff.tz_localize("UTC") if cutoff.tzinfo is None else cutoff.tz_convert("UTC")
    validation_start = cutoff - pd.Timedelta(days=365)
    dates = pd.to_datetime(train["date"], utc=True)
    fit_rows = train.loc[dates < validation_start].copy()
    validation = train.loc[(dates >= validation_start) & (dates <= cutoff)].copy()
    if fit_rows.empty or validation.empty:
        return 0.001
    fit_cutoff = (validation_start - pd.Timedelta(seconds=1)).isoformat()
    outcomes = _outcomes(validation)
    candidates = (0.0005, 0.001, 0.002)
    scores: list[tuple[float, float]] = []
    for xi in candidates:
        model = fit_model("dixon_coles", fit_rows, fit_cutoff, xi=xi)
        score = _metrics(_predict_frame(model, validation), outcomes)["log_loss"]
        scores.append((float(score), xi))
    return min(scores)[1]


def evaluate(pack_dir: Path) -> dict[str, Any]:
    """Evaluate all candidates on frozen chronological tournament folds."""
    matches = load_match_table(pack_dir)
    snapshot = snapshot_descriptor(pack_dir)
    fold_results: list[dict[str, Any]] = []
    for fold in FOLDS:
        start = pd.Timestamp(fold["window_start"], tz="UTC")
        end = pd.Timestamp(fold["window_end"], tz="UTC")
        cutoff = start - pd.Timedelta(seconds=1)
        train = training_rows(matches, cutoff)
        dates = pd.to_datetime(matches["date"], utc=True)
        test = matches.loc[
            (dates >= start)
            & (dates <= end)
            & matches["tournament"].eq(fold["competition"])
            & matches["is_complete"]
        ].copy()
        if test.empty:
            raise ValueError(f"{fold['fold_id']} has no rows in the pinned snapshot")
        outcomes = _outcomes(test)
        xi = _tune_dixon_coles_xi(train, cutoff.isoformat())
        models: list[dict[str, Any]] = []
        for family in FAMILIES:
            family_xi = xi if family == "dixon_coles" else 0.001
            fitted = fit_model(family, train, cutoff.isoformat(), xi=family_xi)
            predictions = _predict_frame(fitted, test)
            metrics = _metrics(predictions, outcomes)
            params = fitted.predict(
                str(test.iloc[0]["home_team"]),
                str(test.iloc[0]["away_team"]),
                bool(test.iloc[0]["neutral"]),
            ).params
            models.append({"family": family, "params": params, **metrics})
        fold_results.append(
            {
                **fold,
                "training_cutoff_utc": cutoff.isoformat().replace("+00:00", "Z"),
                "n_matches": len(test),
                "models": models,
            }
        )
    return {
        "schema_version": "0.1.0",
        "generated_at_utc": snapshot["retrieved_at_utc"],
        "primary_metric": "log_loss",
        "source_snapshot": snapshot,
        "folds": fold_results,
    }


def _validate_summary(summary: dict[str, Any], schema_path: Path) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    wrapper = {
        "$schema": schema["$schema"],
        "$ref": "#/$defs/EvalSummary",
        "$defs": schema["$defs"],
    }
    Draft202012Validator(wrapper, format_checker=FormatChecker()).validate(summary)


def write_evaluation(
    pack_dir: Path, summary_path: Path, report_path: Path, schema_path: Path
) -> dict[str, Any]:
    """Write the machine-readable summary and honest Markdown report."""
    summary = evaluate(pack_dir)
    _validate_summary(summary, schema_path)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Phase 0 chronological evaluation",
        "",
        "Log loss is primary. Each tournament is a frozen test window; model fitting and",
        "Dixon-Coles decay selection use only rows before the stated cutoff. Candidates are",
        "reported honestly and no test fold is used for parameter tuning.",
        "",
        "| Fold | Matches | Model | Log loss | Brier | ECE | RPS |",
        "|---|---:|---|---:|---:|---:|---:|",
    ]
    for fold in summary["folds"]:
        for model in fold["models"]:
            lines.append(
                f"| {fold['fold_id']} | {fold['n_matches']} | {model['family']} | "
                f"{model['log_loss']:.6f} | {model['brier']:.6f} | "
                f"{model['ece']:.6f} | {model['rps']:.6f} |"
            )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "Elo is a baseline, not a declared champion. A lower log loss is better. Candidate",
            "models that lose to Elo remain in this report; Phase 0 does not tune on test results",
            "to manufacture a win. Reliability-bin Wilson intervals are in `eval_summary.json`.",
            "",
            "The source supplies dates but not kickoff times; fold cutoffs use 23:59:59 UTC on",
            "the day before each tournament window.",
        ]
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary
