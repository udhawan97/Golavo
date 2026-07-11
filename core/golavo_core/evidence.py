"""Deterministic MatchEvidenceBundle construction.

The bundle is the ONLY object Golavo's optional AI layer is ever shown. It is a
pure function of a sealed or scored ForecastArtifact: no wall clock, no network,
no model — build it twice and you get byte-identical output.

Its purpose is to make the numeric-whitelist guard possible. `allowed_numbers`
enumerates every numeric value the AI is permitted to utter, each with an id, a
unit, a citable source, and the exact display string. The deterministic engine
owns those numbers; the AI may cite and explain them but can never introduce one
that is not on the list (see golavo_core.ai.whitelist).

This module never imports or touches the ForecastArtifact writer, and adds no
field to that contract — the bundle is a sibling artifact.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from golavo_core import __version__

EVIDENCE_SCHEMA_VERSION = "0.1.0"
GENERATOR = f"golavo-core/{__version__}"
REPO_URL = "https://github.com/udhawan97/Golavo"
ENGINE_LICENSE = "Apache-2.0"

_OUTCOME_KEYS = ("home", "draw", "away")


def _schema() -> dict[str, Any]:
    from golavo_core.resources import evidence_bundle_schema_path

    return json.loads(evidence_bundle_schema_path().read_text(encoding="utf-8"))


def _canonical_bytes(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _pct(prob: float) -> float:
    return round(float(prob) * 100.0, 6)


def _fmt_pct(prob: float) -> str:
    return f"{float(prob) * 100.0:.1f}%"


def _fmt_goals(value: float) -> str:
    return f"{float(value):.1f}"


def _fmt_metric(value: float) -> str:
    return f"{float(value):.3f}"


def _leading_outcome(probs: dict[str, float] | None) -> str | None:
    if not probs:
        return None
    return max(_OUTCOME_KEYS, key=lambda key: float(probs[key]))


def _engine_source_id(model: dict[str, Any]) -> str:
    return f"engine:{model['model_id']}"


def _sources(artifact: dict[str, Any]) -> list[dict[str, Any]]:
    model = artifact["model"]
    sources: list[dict[str, Any]] = [
        {
            "source_id": _engine_source_id(model),
            "kind": "engine",
            "title": f"Golavo deterministic engine · {model['family']}",
            "url": REPO_URL,
            "license": ENGINE_LICENSE,
            "upstream_ref": model["code_git_sha"],
            "retrieved_at_utc": None,
            "upstream_committed_at_utc": None,
            # params_hash is a 64-hex digest pinning the exact fitted parameters.
            "sha256": model["params_hash"],
        }
    ]
    for snapshot in artifact["inputs"]["snapshots"]:
        sources.append(
            {
                "source_id": snapshot["snapshot_id"],
                "kind": "snapshot",
                "title": snapshot["source_id"],
                "url": snapshot["url"],
                "license": snapshot["license"],
                "upstream_ref": snapshot["upstream_ref"],
                "retrieved_at_utc": snapshot["retrieved_at_utc"],
                "upstream_committed_at_utc": snapshot.get("upstream_committed_at_utc"),
                "sha256": snapshot["sha256"],
            }
        )
    return sources


def _allowed_numbers(
    artifact: dict[str, Any], engine_id: str, snapshot_ids: list[str]
) -> list[dict[str, Any]]:
    forecast = artifact["forecast"]
    match = artifact["match"]
    probs = forecast["probs"]
    data_sources = [engine_id, *snapshot_ids]
    numbers: list[dict[str, Any]] = []
    if probs is not None:
        labels = {
            "home": f"{match['home_team']} win probability",
            "draw": "Draw probability",
            "away": f"{match['away_team']} win probability",
        }
        for key in _OUTCOME_KEYS:
            numbers.append(
                {
                    "id": f"prob_{key}",
                    "value": _pct(probs[key]),
                    "unit": "percent",
                    "label": labels[key],
                    "display": _fmt_pct(probs[key]),
                    "source_ids": data_sources,
                }
            )
    xg = forecast.get("expected_goals")
    if xg is not None:
        numbers.append(
            {
                "id": "xg_home",
                "value": round(float(xg["home"]), 6),
                "unit": "goals",
                "label": f"Expected goals · {match['home_team']}",
                "display": _fmt_goals(xg["home"]),
                "source_ids": data_sources,
            }
        )
        numbers.append(
            {
                "id": "xg_away",
                "value": round(float(xg["away"]), 6),
                "unit": "goals",
                "label": f"Expected goals · {match['away_team']}",
                "display": _fmt_goals(xg["away"]),
                "source_ids": data_sources,
            }
        )
    evaluation = artifact.get("evaluation")
    if evaluation is not None:
        actual = evaluation["actual"]
        metrics = evaluation["metrics"]
        # The final score is a datum, not an engine output: cite the snapshots.
        result_sources = snapshot_ids or [engine_id]
        numbers.append(
            {
                "id": "actual_home_goals",
                "value": int(actual["home_goals"]),
                "unit": "count",
                "label": f"Full-time goals · {match['home_team']}",
                "display": str(int(actual["home_goals"])),
                "source_ids": result_sources,
            }
        )
        numbers.append(
            {
                "id": "actual_away_goals",
                "value": int(actual["away_goals"]),
                "unit": "count",
                "label": f"Full-time goals · {match['away_team']}",
                "display": str(int(actual["away_goals"])),
                "source_ids": result_sources,
            }
        )
        numbers.append(
            {
                "id": "prob_assigned",
                "value": _pct(metrics["prob_assigned_to_outcome"]),
                "unit": "percent",
                "label": "Probability the seal assigned to the actual outcome",
                "display": _fmt_pct(metrics["prob_assigned_to_outcome"]),
                "source_ids": data_sources,
            }
        )
        numbers.append(
            {
                "id": "log_loss",
                "value": round(float(metrics["log_loss"]), 6),
                "unit": "log_loss",
                "label": "Log loss of the sealed forecast",
                "display": _fmt_metric(metrics["log_loss"]),
                "source_ids": data_sources,
            }
        )
        numbers.append(
            {
                "id": "brier",
                "value": round(float(metrics["brier"]), 6),
                "unit": "brier",
                "label": "Brier score of the sealed forecast",
                "display": _fmt_metric(metrics["brier"]),
                "source_ids": data_sources,
            }
        )
    return numbers


def _facts(
    artifact: dict[str, Any], engine_id: str, snapshot_ids: list[str], leading: str | None
) -> list[dict[str, Any]]:
    match = artifact["match"]
    forecast = artifact["forecast"]
    probs = forecast["probs"]
    data_sources = [engine_id, *snapshot_ids]
    home, away = match["home_team"], match["away_team"]
    facts: list[dict[str, Any]] = []

    if probs is not None and leading is not None:
        leader_phrase = {
            "home": f"{home} to win",
            "draw": "a draw",
            "away": f"{away} to win",
        }[leading]
        facts.append(
            {
                "fact_id": "leading_outcome",
                "text": (
                    f"The single most likely regulation result is {leader_phrase} "
                    f"at {_fmt_pct(probs[leading])}."
                ),
                "kind": "forecast",
                "source_ids": data_sources,
                "number_refs": [f"prob_{leading}"],
            }
        )
        facts.append(
            {
                "fact_id": "distribution",
                "text": (
                    f"Sealed 1X2 probabilities: {home} {_fmt_pct(probs['home'])}, "
                    f"draw {_fmt_pct(probs['draw'])}, {away} {_fmt_pct(probs['away'])}."
                ),
                "kind": "forecast",
                "source_ids": data_sources,
                "number_refs": ["prob_home", "prob_draw", "prob_away"],
            }
        )

    xg = forecast.get("expected_goals")
    if xg is not None:
        facts.append(
            {
                "fact_id": "expected_goals",
                "text": (
                    f"Model expected goals: {_fmt_goals(xg['home'])} for {home}, "
                    f"{_fmt_goals(xg['away'])} for {away}."
                ),
                "kind": "forecast",
                "source_ids": [engine_id],
                "number_refs": ["xg_home", "xg_away"],
            }
        )

    facts.append(
        {
            "fact_id": "seal_immutability",
            "text": (
                f"This forecast was sealed at horizon {forecast['horizon']} before kickoff. "
                "Its probabilities are immutable and were produced entirely by the deterministic "
                "engine — no AI produced, changed, or reviewed any number here."
            ),
            "kind": "context",
            "source_ids": [engine_id],
            "number_refs": [],
        }
    )
    facts.append(
        {
            "fact_id": "uncertainty",
            "text": (
                "The engine flags its model uncertainty for this fixture as "
                f"{forecast['uncertainty']}."
            ),
            "kind": "context",
            "source_ids": [engine_id],
            "number_refs": [],
        }
    )
    facts.append(
        {
            "fact_id": "venue",
            "text": (
                "The fixture is at a neutral venue, so no home advantage was applied."
                if match["neutral_venue"]
                else f"{home} were treated as the home side, with home advantage applied."
            ),
            "kind": "context",
            "source_ids": [engine_id, *snapshot_ids],
            "number_refs": [],
        }
    )

    if forecast["abstained"]:
        facts.append(
            {
                "fact_id": "abstained",
                "text": (
                    "The engine abstained from forecasting this fixture because at least "
                    "one side had too few recent matches to model honestly; no "
                    "probabilities were issued."
                ),
                "kind": "context",
                "source_ids": [engine_id],
                "number_refs": [],
            }
        )

    evaluation = artifact.get("evaluation")
    if evaluation is not None and probs is not None:
        actual = evaluation["actual"]
        outcome_phrase = {
            "home": f"a {home} win",
            "draw": "a draw",
            "away": f"an {away} win",
        }[actual["outcome"]]
        facts.append(
            {
                "fact_id": "result",
                "text": (
                    f"Full-time result: {home} {int(actual['home_goals'])}"
                    f"–{int(actual['away_goals'])} {away} ({outcome_phrase}). The sealed "
                    f"forecast had assigned {_fmt_pct(evaluation['metrics']['prob_assigned_to_outcome'])} "  # noqa: E501
                    "to that outcome."
                ),
                "kind": "result",
                "source_ids": [engine_id, *snapshot_ids],
                "number_refs": ["actual_home_goals", "actual_away_goals", "prob_assigned"],
            }
        )
    return facts


def _features(artifact: dict[str, Any], engine_id: str) -> list[dict[str, Any]]:
    model = artifact["model"]
    forecast = artifact["forecast"]
    match = artifact["match"]
    features: list[dict[str, Any]] = [
        {
            "feature_id": "model_family",
            "name": "Model family",
            "kind": "categorical",
            "value": model["family"],
            "value_ref": None,
            "source_ids": [engine_id],
        },
        {
            "feature_id": "horizon",
            "name": "Seal horizon before kickoff",
            "kind": "categorical",
            "value": forecast["horizon"],
            "value_ref": None,
            "source_ids": [engine_id],
        },
        {
            "feature_id": "neutral_venue",
            "name": "Neutral venue",
            "kind": "boolean",
            "value": bool(match["neutral_venue"]),
            "value_ref": None,
            "source_ids": [engine_id],
        },
        {
            "feature_id": "uncertainty",
            "name": "Model uncertainty",
            "kind": "categorical",
            "value": forecast["uncertainty"],
            "value_ref": None,
            "source_ids": [engine_id],
        },
        {
            "feature_id": "training_cutoff",
            "name": "Training cutoff (UTC)",
            "kind": "timestamp",
            "value": artifact["inputs"]["training_cutoff_utc"],
            "value_ref": None,
            "source_ids": [engine_id],
        },
    ]
    if forecast.get("expected_goals") is not None:
        features.append(
            {
                "feature_id": "expected_goals_home",
                "name": "Expected goals (home)",
                "kind": "numeric",
                "value": None,
                "value_ref": "xg_home",
                "source_ids": [engine_id],
            }
        )
        features.append(
            {
                "feature_id": "expected_goals_away",
                "name": "Expected goals (away)",
                "kind": "numeric",
                "value": None,
                "value_ref": "xg_away",
                "source_ids": [engine_id],
            }
        )
    return features


def build_evidence_bundle(artifact: dict[str, Any]) -> dict[str, Any]:
    """Build the deterministic evidence bundle for a sealed/scored/abstained artifact.

    Pure function of the artifact. Voided artifacts are accepted (the AI can
    explain the void), abstained artifacts yield an empty allowed_numbers list.
    """
    if artifact.get("status") not in {"sealed", "scored", "abstained", "voided"}:
        raise ValueError(f"cannot build an evidence bundle from status {artifact.get('status')!r}")

    model = artifact["model"]
    match = artifact["match"]
    forecast = artifact["forecast"]
    engine_id = _engine_source_id(model)
    snapshot_ids = [snapshot["snapshot_id"] for snapshot in artifact["inputs"]["snapshots"]]
    leading = _leading_outcome(forecast["probs"])

    bundle: dict[str, Any] = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "bundle_id": "eb_pending00",
        "artifact_id": artifact["artifact_id"],
        "artifact_status": artifact["status"],
        "derived_from_payload_sha256": artifact["provenance"]["payload_sha256"],
        "match": {
            "match_id": match["match_id"],
            "competition": match["competition"],
            "stage": match.get("stage"),
            "kickoff_utc": match["kickoff_utc"],
            "home_team": match["home_team"],
            "away_team": match["away_team"],
            "neutral_venue": bool(match["neutral_venue"]),
            "city": match.get("city"),
            "country": match.get("country"),
        },
        "forecast_summary": {
            "market": forecast["market"],
            "horizon": forecast["horizon"],
            "uncertainty": forecast["uncertainty"],
            "abstained": bool(forecast["abstained"]),
            "leading_outcome": leading,
        },
        "allowed_numbers": _allowed_numbers(artifact, engine_id, snapshot_ids),
        "facts": _facts(artifact, engine_id, snapshot_ids, leading),
        "features": _features(artifact, engine_id),
        "sources": _sources(artifact),
        "data_quality": {
            "uncertainty": forecast["uncertainty"],
            "abstained": bool(forecast["abstained"]),
            "abstain_reason": forecast.get("abstain_reason"),
            "training_cutoff_utc": artifact["inputs"]["training_cutoff_utc"],
        },
        "generator": GENERATOR,
        "bundle_hash": "0" * 64,
    }

    stable = copy.deepcopy(bundle)
    stable.pop("bundle_id")
    stable.pop("bundle_hash")
    digest = hashlib.sha256(_canonical_bytes(stable)).hexdigest()
    bundle["bundle_id"] = f"eb_{digest[:20]}"
    bundle["bundle_hash"] = digest
    validate_evidence_bundle(bundle)
    return bundle


def validate_evidence_bundle(bundle: dict[str, Any]) -> None:
    """Validate against the JSON schema and enforce cross-field referential integrity."""
    from jsonschema import Draft202012Validator, FormatChecker

    Draft202012Validator(_schema(), format_checker=FormatChecker()).validate(bundle)

    source_ids = {source["source_id"] for source in bundle["sources"]}
    number_ids = {number["id"] for number in bundle["allowed_numbers"]}

    def _check_sources(holder: dict[str, Any], where: str) -> None:
        for sid in holder["source_ids"]:
            if sid not in source_ids:
                raise ValueError(f"{where} cites unknown source_id {sid!r}")

    for number in bundle["allowed_numbers"]:
        _check_sources(number, f"allowed_numbers[{number['id']}]")
    for fact in bundle["facts"]:
        _check_sources(fact, f"facts[{fact['fact_id']}]")
        for ref in fact["number_refs"]:
            if ref not in number_ids:
                raise ValueError(f"facts[{fact['fact_id']}] references unknown number id {ref!r}")
    for feature in bundle["features"]:
        _check_sources(feature, f"features[{feature['feature_id']}]")
        ref = feature["value_ref"]
        if ref is not None and ref not in number_ids:
            raise ValueError(
                f"features[{feature['feature_id']}] references unknown number id {ref!r}"
            )


def load_and_build(artifact_path: Path) -> dict[str, Any]:
    """Convenience: read an artifact JSON file and build its evidence bundle."""
    artifact = json.loads(Path(artifact_path).read_text(encoding="utf-8"))
    return build_evidence_bundle(artifact)
