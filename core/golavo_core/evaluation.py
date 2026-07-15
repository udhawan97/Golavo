"""Strictly chronological evaluation and calibration reporting (source-agnostic)."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from jsonschema import Draft202012Validator, FormatChecker

from golavo_core.ingest import load_matches, snapshot_descriptor, training_rows, validate_pack
from golavo_core.models import FAMILIES, fit_model

REPORT_CARD_BOOTSTRAP_REPLICATES = 2000
REPORT_CARD_BOOTSTRAP_SEED = 20260715
REPORT_CARD_MIN_MATCHES = 50

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

# Club season folds: for each accepted league, the three most recent CLEAN
# seasons per the audit gate (docs/handoff/openfootball-audit.md). Every audited
# fold season starts after Aug 1 and ends before Jun 30, so the shared window
# convention holds. La Liga and Serie A folds stop at 2023-24 because their
# 2024-25 captures are missing the final matchday; Ligue 1 excludes the
# COVID-abandoned 2019-20 and is a 380-match league through 2022-23, 306 after.
# Leagues are modeled independently — domestic files carry no inter-league
# matches, so there is NO cross-league strength calibration.


def _season_fold(prefix: str, competition: str, first_year: int) -> dict[str, str]:
    return {
        "fold_id": f"{prefix}{first_year}-{str(first_year + 1)[-2:]}",
        "competition": competition,
        "window_start": f"{first_year}-08-01",
        "window_end": f"{first_year + 1}-06-30",
    }


CLUB_FOLDS = tuple(
    _season_fold("EPL", "English Premier League", year) for year in (2022, 2023, 2024)
)
CLUB_FOLDS_BY_COMPETITION: dict[str, tuple[dict[str, str], ...]] = {
    "English Premier League": CLUB_FOLDS,
    "La Liga": tuple(_season_fold("LALIGA", "La Liga", year) for year in (2021, 2022, 2023)),
    "Bundesliga": tuple(
        _season_fold("BUNDESLIGA", "Bundesliga", year) for year in (2022, 2023, 2024)
    ),
    "Serie A": tuple(_season_fold("SERIEA", "Serie A", year) for year in (2021, 2022, 2023)),
    "Ligue 1": tuple(_season_fold("LIGUE1-", "Ligue 1", year) for year in (2022, 2023, 2024)),
}


def _outcomes(matches: pd.DataFrame) -> np.ndarray:
    return np.where(
        matches["home_score"].to_numpy() > matches["away_score"].to_numpy(),
        0,
        np.where(matches["home_score"].to_numpy() == matches["away_score"].to_numpy(), 1, 2),
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


def _log_loss_rows(probs: np.ndarray, outcomes: np.ndarray) -> np.ndarray:
    assigned = np.clip(probs[np.arange(len(outcomes)), outcomes], 1e-12, 1.0)
    return -np.log(assigned)


def _bootstrap_skill_interval(
    model_rows: list[np.ndarray],
    baseline_rows: list[np.ndarray],
    *,
    seed: int,
) -> list[float]:
    """Seeded, fold-stratified match bootstrap for relative log-loss skill."""
    rng = np.random.default_rng(seed)
    values = np.empty(REPORT_CARD_BOOTSTRAP_REPLICATES, dtype=float)
    for replicate in range(REPORT_CARD_BOOTSTRAP_REPLICATES):
        model_total = 0.0
        baseline_total = 0.0
        count = 0
        for model, baseline in zip(model_rows, baseline_rows, strict=True):
            indices = rng.integers(0, len(model), size=len(model))
            model_total += float(model[indices].sum())
            baseline_total += float(baseline[indices].sum())
            count += len(model)
        model_mean = model_total / count
        baseline_mean = baseline_total / count
        values[replicate] = 1.0 - model_mean / baseline_mean
    low, high = np.quantile(values, [0.025, 0.975])
    return [round(float(low), 6), round(float(high), 6)]


def _build_report_cards(
    folds: list[dict[str, Any]],
    losses: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Aggregate held-out folds without erasing their dates or rank variation."""
    loss_by_fold = {str(item["fold_id"]): item for item in losses}
    competitions: list[str] = []
    for fold in folds:
        competition = str(fold["competition"])
        if competition not in competitions:
            competitions.append(competition)

    cards: list[dict[str, Any]] = []
    for competition in competitions:
        selected = [fold for fold in folds if fold["competition"] == competition]
        baseline_rows = [
            loss_by_fold[str(fold["fold_id"])]["families"]["climatological"]
            for fold in selected
        ]
        n_matches = sum(int(fold["n_matches"]) for fold in selected)
        model_cards: list[dict[str, Any]] = []
        for family in FAMILIES:
            family_rows = [
                loss_by_fold[str(fold["fold_id"])]["families"][family]
                for fold in selected
            ]
            model_total = sum(float(values.sum()) for values in family_rows)
            baseline_total = sum(float(values.sum()) for values in baseline_rows)
            skill = 1.0 - model_total / baseline_total
            weighted = {
                metric: sum(
                    float(next(m for m in fold["models"] if m["family"] == family)[metric])
                    * int(fold["n_matches"])
                    for fold in selected
                )
                / n_matches
                for metric in ("brier", "ece", "rps")
            }
            ranks: list[int] = []
            for fold in selected:
                ordered = sorted(fold["models"], key=lambda model: model["log_loss"])
                ranks.append(
                    next(
                        i
                        for i, model in enumerate(ordered, 1)
                        if model["family"] == family
                    )
                )
            sample_status = (
                "available"
                if all(
                    int(fold["n_matches"]) >= REPORT_CARD_MIN_MATCHES
                    for fold in selected
                )
                else "insufficient_sample"
            )
            digest = hashlib.sha256(f"{competition}|{family}".encode()).digest()
            seed = REPORT_CARD_BOOTSTRAP_SEED + int.from_bytes(digest[:4], "big")
            model_cards.append(
                {
                    "family": family,
                    "n_matches": n_matches,
                    "n_folds": len(selected),
                    "log_loss": round(model_total / n_matches, 6),
                    "brier": round(weighted["brier"], 6),
                    "ece": round(weighted["ece"], 6),
                    "rps": round(weighted["rps"], 6),
                    "skill_score": round(skill, 6),
                    "skill_ci_95": (
                        _bootstrap_skill_interval(family_rows, baseline_rows, seed=seed)
                        if sample_status == "available"
                        else None
                    ),
                    "sample_status": sample_status,
                    "mean_rank": round(sum(ranks) / len(ranks), 3),
                    "best_rank": min(ranks),
                    "worst_rank": max(ranks),
                    "first_place_folds": sum(rank == 1 for rank in ranks),
                }
            )
        cards.append(
            {
                "competition": competition,
                "baseline_family": "climatological",
                "primary_metric": "log_loss",
                "minimum_matches": REPORT_CARD_MIN_MATCHES,
                "bootstrap": {
                    "method": "fold-stratified-match-bootstrap",
                    "replicates": REPORT_CARD_BOOTSTRAP_REPLICATES,
                    "seed": REPORT_CARD_BOOTSTRAP_SEED,
                },
                "window_start": min(str(fold["window_start"]) for fold in selected),
                "window_end": max(str(fold["window_end"]) for fold in selected),
                "models": model_cards,
            }
        )
    return cards


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


def _evaluate_folds(
    matches: pd.DataFrame, snapshot: dict[str, str], folds: tuple[dict, ...]
) -> dict[str, Any]:
    fold_results: list[dict[str, Any]] = []
    fold_losses: list[dict[str, Any]] = []
    for fold in folds:
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
        losses: dict[str, np.ndarray] = {}
        for family in FAMILIES:
            family_xi = xi if family == "dixon_coles" else 0.001
            fitted = fit_model(family, train, cutoff.isoformat(), xi=family_xi)
            predictions = _predict_frame(fitted, test)
            losses[family] = _log_loss_rows(predictions, outcomes)
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
        fold_losses.append(
            {"fold_id": fold["fold_id"], "competition": fold["competition"], "families": losses}
        )
    return {
        "schema_version": "0.1.0",
        "generated_at_utc": snapshot["retrieved_at_utc"],
        "primary_metric": "log_loss",
        "source_snapshot": snapshot,
        "folds": fold_results,
        "report_cards": _build_report_cards(fold_results, fold_losses),
    }


def evaluate(pack_dir: Path) -> dict[str, Any]:
    """Evaluate all candidates on the frozen international tournament folds."""
    return _evaluate_folds(load_matches(pack_dir), snapshot_descriptor(pack_dir), FOLDS)


def evaluate_club(pack_dir: Path) -> dict[str, Any]:
    """Evaluate all candidates on a league pack's frozen chronological season folds."""
    competition = str(validate_pack(pack_dir).get("competition", ""))
    folds = CLUB_FOLDS_BY_COMPETITION.get(competition)
    if folds is None:
        raise ValueError(f"no accepted evaluation folds for competition {competition!r}")
    return _evaluate_folds(load_matches(pack_dir), snapshot_descriptor(pack_dir), folds)


def _validate_summary(summary: dict[str, Any], schema_path: Path) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    wrapper = {
        "$schema": schema["$schema"],
        "$ref": "#/$defs/EvalSummary",
        "$defs": schema["$defs"],
    }
    Draft202012Validator(wrapper, format_checker=FormatChecker()).validate(summary)


def _render_report(
    summary: dict[str, Any], report_path: Path, title: str, notes: list[str]
) -> None:
    lines = [
        f"# {title}",
        "",
        "Log loss is primary. Each fold is a frozen test window; model fitting and",
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
    lines += ["", "## Interpretation", "", *notes, ""]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_evaluation(
    pack_dir: Path, summary_path: Path, report_path: Path, schema_path: Path
) -> dict[str, Any]:
    """Write the internationals summary and honest Markdown report."""
    summary = evaluate(pack_dir)
    _validate_summary(summary, schema_path)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _render_report(
        summary,
        report_path,
        "Phase 0 chronological evaluation",
        [
            "Elo is a baseline, not a declared champion. A lower log loss is better. Candidate",
            "models that lose to Elo stay in this report; no test fold tunes its parameters.",
            "Reliability-bin Wilson intervals are in the JSON summary.",
            "",
            "The source supplies dates but not kickoff times; fold cutoffs use 23:59:59 UTC on the",
            "day before each tournament window.",
        ],
    )
    return summary


# Per-league exclusion notes, mirroring docs/handoff/openfootball-audit.md.
_CLUB_REPORT_NOTES: dict[str, str] = {
    "English Premier League": (
        "The partial 2025-26 capture is excluded; each fold trains on all prior clean "
        "seasons from 2010-11."
    ),
    "La Liga": (
        "Folds stop at 2023-24 because the 2024-25 capture is missing its final matchday "
        "(10 results); 2025-26 is a partial capture. Training reaches back to 2012-13."
    ),
    "Bundesliga": (
        "The partial 2025-26 capture is excluded; each fold trains on all prior clean "
        "seasons from 2010-11. A Bundesliga season is 306 matches (18 clubs)."
    ),
    "Serie A": (
        "Folds stop at 2023-24 because the 2024-25 capture is missing its final matchday "
        "(10 results); 2025-26 is a partial capture. Training reaches back to 2013-14."
    ),
    "Ligue 1": (
        "The COVID-abandoned 2019-20 season is excluded as a fold (its 279 played matches "
        "remain training rows) and 2025-26 is a partial capture. Ligue 1 contracted from "
        "20 to 18 clubs in 2023-24, so folds are 380 then 306 matches."
    ),
}


def write_club_evaluation(
    pack_dir: Path, summary_path: Path, report_path: Path, schema_path: Path
) -> dict[str, Any]:
    """Write one league's evaluation summary and honest Markdown report."""
    summary = evaluate_club(pack_dir)
    _validate_summary(summary, schema_path)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    competition = summary["folds"][0]["competition"]
    _render_report(
        summary,
        report_path,
        f"{competition} chronological evaluation (historical)",
        [
            "Historical, not live. Data is a pinned openfootball snapshot (CC0) that passed the",
            "club-coverage gate for completed seasons only (docs/handoff/openfootball-audit.md).",
            _CLUB_REPORT_NOTES[competition],
            "",
            "Elo is a baseline, not a champion. Unlike the near-neutral international folds, club",
            "matches carry a real home advantage, so home-aware candidates have room to help — but",
            "only if they beat Elo out-of-sample here. openfootball kickoff times are venue-local.",
            "Each league is modeled independently from its own pack; there are no inter-league",
            "matches, so strengths are NOT comparable across leagues.",
        ],
    )
    return summary
