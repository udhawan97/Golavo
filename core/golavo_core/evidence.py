"""Deterministic MatchEvidenceBundle construction.

The bundle is the only authoritative object Golavo's optional AI layer is shown.
Optional candidate-fact context is separately fenced as untrusted data. The
bundle is a pure function of a sealed or scored ForecastArtifact: no wall clock,
no network, no model — build it twice and you get byte-identical output.

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


def _ranked_scorelines(
    score_matrix: dict[str, Any], top: int = 3
) -> list[tuple[int, int, float]]:
    """The top ``top`` most likely concrete scorelines as (home, away, probability).

    Tie-break matches the sealed most_likely: highest probability, then fewest home
    goals, then fewest away goals — so rank 1 is exactly score_matrix.most_likely.
    """
    grid = score_matrix["grid"]
    cells = [
        (float(grid[i][j]), i, j) for i in range(len(grid)) for j in range(len(grid[i]))
    ]
    cells.sort(key=lambda cell: (-cell[0], cell[1], cell[2]))
    return [(i, j, prob) for prob, i, j in cells[:top]]


def _score_numbers(
    match: dict[str, Any], score_matrix: dict[str, Any], data_sources: list[str]
) -> list[dict[str, Any]]:
    """Whitelist entries derived from the exact-score matrix (Phase 8, additive).

    Every scoreline probability the AI may cite is enumerated here with an id, a
    citable engine source, and the exact display string. The engine owns these
    numbers; the AI cannot invent a scoreline or a percentage that is not listed.
    """
    home, away = match["home_team"], match["away_team"]
    numbers: list[dict[str, Any]] = []
    for rank, (goals_home, goals_away, prob) in enumerate(_ranked_scorelines(score_matrix), 1):
        numbers.append(
            {
                "id": f"score_r{rank}_home",
                "value": int(goals_home),
                "unit": "count",
                "label": f"Most likely scoreline #{rank}: goals for {home}",
                "display": str(int(goals_home)),
                "source_ids": data_sources,
            }
        )
        numbers.append(
            {
                "id": f"score_r{rank}_away",
                "value": int(goals_away),
                "unit": "count",
                "label": f"Most likely scoreline #{rank}: goals for {away}",
                "display": str(int(goals_away)),
                "source_ids": data_sources,
            }
        )
        numbers.append(
            {
                "id": f"score_r{rank}_prob",
                "value": _pct(prob),
                "unit": "percent",
                "label": f"Probability of {home} {goals_home}–{goals_away} {away}",
                "display": _fmt_pct(prob),
                "source_ids": data_sources,
            }
        )
    numbers.append(
        {
            "id": "score_grid_max",
            "value": int(score_matrix["max_goals"]),
            "unit": "count",
            "label": "Exact-score grid cap (goals per side)",
            "display": str(int(score_matrix["max_goals"])),
            "source_ids": data_sources,
        }
    )
    numbers.append(
        {
            "id": "score_tail_prob",
            "value": _pct(score_matrix["tail"]["probability"]),
            "unit": "percent",
            "label": f"Probability a side scores more than {int(score_matrix['max_goals'])}",
            "display": _fmt_pct(score_matrix["tail"]["probability"]),
            "source_ids": data_sources,
        }
    )
    return numbers


def _score_facts(
    match: dict[str, Any], score_matrix: dict[str, Any], data_sources: list[str]
) -> list[dict[str, Any]]:
    """Deterministic scoreline facts, each bound to its whitelisted numbers."""
    home, away = match["home_team"], match["away_team"]
    ranked = _ranked_scorelines(score_matrix)
    h1, a1, p1 = ranked[0]
    facts: list[dict[str, Any]] = [
        {
            "fact_id": "most_likely_scoreline",
            "text": (
                f"The single most likely exact score is {home} {h1}–{a1} {away}, "
                f"at {_fmt_pct(p1)}."
            ),
            "kind": "forecast",
            "source_ids": data_sources,
            "number_refs": ["score_r1_home", "score_r1_away", "score_r1_prob"],
        }
    ]
    if len(ranked) >= 3:
        h2, a2, p2 = ranked[1]
        h3, a3, p3 = ranked[2]
        facts.append(
            {
                "fact_id": "scoreline_shortlist",
                "text": (
                    f"Most likely exact scores: {home} {h1}–{a1} {away} ({_fmt_pct(p1)}), "
                    f"{h2}–{a2} ({_fmt_pct(p2)}), {h3}–{a3} ({_fmt_pct(p3)})."
                ),
                "kind": "forecast",
                "source_ids": data_sources,
                "number_refs": [
                    "score_r1_home", "score_r1_away", "score_r1_prob",
                    "score_r2_home", "score_r2_away", "score_r2_prob",
                    "score_r3_home", "score_r3_away", "score_r3_prob",
                ],
            }
        )
    facts.append(
        {
            "fact_id": "scoreline_tail",
            "text": (
                f"Beyond {int(score_matrix['max_goals'])} goals for either side lies "
                f"{_fmt_pct(score_matrix['tail']['probability'])} of the exact-score distribution."
            ),
            "kind": "forecast",
            "source_ids": data_sources,
            "number_refs": ["score_grid_max", "score_tail_prob"],
        }
    )
    return facts


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
    score_matrix = forecast.get("score_matrix")
    if score_matrix is not None:
        numbers.extend(_score_numbers(match, score_matrix, data_sources))
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

    score_matrix = forecast.get("score_matrix")
    if score_matrix is not None:
        facts.extend(_score_facts(match, score_matrix, data_sources))

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


def build_evidence_bundle(
    artifact: dict[str, Any],
    *,
    extra_facts: list[dict[str, Any]] | tuple[dict[str, Any], ...] = (),
    extra_numbers: list[dict[str, Any]] | tuple[dict[str, Any], ...] = (),
) -> dict[str, Any]:
    """Build the deterministic evidence bundle for a sealed/scored/abstained artifact.

    Pure function of the artifact. Voided artifacts are accepted (the AI can
    explain the void), abstained artifacts yield an empty allowed_numbers list.

    ``extra_facts`` / ``extra_numbers`` (Phase 7, additive) append deterministic
    Commentator's Notebook facts and their whitelisted numbers. They are ONLY
    ever appended — engine facts and numbers keep their exact position and value,
    so folding notebook context can never change a forecast number. With the
    defaults (empty) the output is byte-for-byte identical to the pre-Phase-7
    bundle. Notebook number ids are namespaced ``nb_*``; a collision with an
    engine number id is rejected.
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
        "allowed_numbers": [
            *_allowed_numbers(artifact, engine_id, snapshot_ids),
            *extra_numbers,
        ],
        "facts": [*_facts(artifact, engine_id, snapshot_ids, leading), *extra_facts],
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
    number_id_list = [number["id"] for number in bundle["allowed_numbers"]]
    number_ids = set(number_id_list)
    if len(number_id_list) != len(number_ids):
        raise ValueError("allowed_numbers contains duplicate ids (folded facts collided)")

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


# --- Match-analysis bundles (schema 0.2.0, additive) ---------------------------
#
# The same whitelist machinery, fed by the on-demand MatchAnalysis (the cockpit's
# Replay/Preview council) plus the Commentator's Notebook — so the AI can write a
# DEEPER read of the notes for ANY indexed match, under exactly the guards the
# sealed path uses. The bundle id is `ma_*`, its status is the analysis kind
# (never a sealed status), and its hash derives from the analysis payload — a
# match bundle can never masquerade as a sealed forecast's evidence.

MATCH_EVIDENCE_SCHEMA_VERSION = "0.2.0"
_MATCH_ENGINE_SOURCE_ID = "engine:match_analysis"

_VOICE_LABELS = {
    "elo_ordlogit": "Elo ratings model",
    "dixon_coles": "Dixon-Coles goal model",
    "climatological": "climatology baseline",
}


def _match_sources(
    pack_source_ids: tuple[str, ...],
    extra_sources: tuple[dict[str, Any], ...] = (),
) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = [
        {
            "source_id": _MATCH_ENGINE_SOURCE_ID,
            "kind": "engine",
            "title": "Golavo deterministic engine · on-demand model council",
            "url": REPO_URL,
            "license": ENGINE_LICENSE,
        }
    ]
    for sid in pack_source_ids:
        sources.append(
            {
                "source_id": sid,
                "kind": "snapshot",
                "title": f"Vendored data pack · {sid} · match results",
                "url": REPO_URL,
                # Every bundled results pack is CC0 (packs/README.md; enforced by
                # the license-isolation gate).
                "license": "CC0-1.0",
            }
        )
    # Per-dataset attributions (goalscorers/shootouts) from the notebook fold, so
    # scorer/shootout facts cite a distinct source and the AI chips vary. Finalized
    # here from the minimal descriptors notebook_to_evidence produced.
    seen = {s["source_id"] for s in sources}
    for extra in extra_sources:
        sid = str(extra["source_id"])
        if sid in seen:
            continue
        seen.add(sid)
        sources.append(
            {
                "source_id": sid,
                "kind": "snapshot",
                "title": str(extra["title"]),
                "url": REPO_URL,
                "license": str(extra.get("license") or "CC0-1.0"),
            }
        )
    return sources


def _council_numbers(analysis: dict[str, Any], data_sources: list[str]) -> list[dict[str, Any]]:
    match = analysis["match"]
    numbers: list[dict[str, Any]] = []
    labels = {
        "home": f"{match['home_team']} win probability",
        "draw": "Draw probability",
        "away": f"{match['away_team']} win probability",
    }
    for entry in analysis["models"]:
        probs = entry.get("probs")
        family = entry["family"]
        if probs is None or family not in _VOICE_LABELS:
            continue  # variants are disclosure, not extra whitelisted voices
        for key in _OUTCOME_KEYS:
            numbers.append(
                {
                    "id": f"mc_{family}_prob_{key}",
                    "value": _pct(probs[key]),
                    "unit": "percent",
                    "label": f"{labels[key]} · {_VOICE_LABELS[family]}",
                    "display": _fmt_pct(probs[key]),
                    "source_ids": data_sources,
                }
            )
        xg = entry.get("expected_goals")
        if xg is not None:
            for side in ("home", "away"):
                numbers.append(
                    {
                        "id": f"mc_{family}_xg_{side}",
                        "value": round(float(xg[side]), 6),
                        "unit": "goals",
                        "label": f"Model expected goals · {match[f'{side}_team']} "
                        f"({_VOICE_LABELS[family]})",
                        "display": _fmt_goals(xg[side]),
                        "source_ids": data_sources,
                    }
                )
    score_matrix = analysis.get("score_matrix")
    if score_matrix is not None:
        ml = score_matrix["most_likely"]
        numbers.append(
            {
                "id": "mc_most_likely_home",
                "value": int(ml["home"]),
                "unit": "count",
                "label": f"Most likely scoreline: goals for {match['home_team']}",
                "display": str(int(ml["home"])),
                "source_ids": data_sources,
            }
        )
        numbers.append(
            {
                "id": "mc_most_likely_away",
                "value": int(ml["away"]),
                "unit": "count",
                "label": f"Most likely scoreline: goals for {match['away_team']}",
                "display": str(int(ml["away"])),
                "source_ids": data_sources,
            }
        )
        numbers.append(
            {
                "id": "mc_most_likely_prob",
                "value": _pct(ml["probability"]),
                "unit": "percent",
                "label": "Probability of the most likely scoreline (goal model)",
                "display": _fmt_pct(ml["probability"]),
                "source_ids": data_sources,
            }
        )
    markets = analysis.get("derived_markets")
    if markets is not None:
        numbers.append(
            {
                "id": "mc_btts_yes",
                "value": _pct(markets["btts"]["yes"]),
                "unit": "percent",
                "label": "Both teams to score (goal model)",
                "display": _fmt_pct(markets["btts"]["yes"]),
                "source_ids": data_sources,
            }
        )
        for side in ("home", "away"):
            numbers.append(
                {
                    "id": f"mc_clean_sheet_{side}",
                    "value": _pct(markets["clean_sheets"][side]),
                    "unit": "percent",
                    "label": f"Clean-sheet probability · {match[f'{side}_team']} (goal model)",
                    "display": _fmt_pct(markets["clean_sheets"][side]),
                    "source_ids": data_sources,
                }
            )
    return numbers


def _council_facts(analysis: dict[str, Any], data_sources: list[str]) -> list[dict[str, Any]]:
    match = analysis["match"]
    home, away = match["home_team"], match["away_team"]
    kind = analysis["analysis_kind"]
    facts: list[dict[str, Any]] = [
        {
            "fact_id": "analysis_kind",
            "text": (
                "This is a replay: every model was fit using only matches before kickoff. "
                "It shows what the methods WOULD have said — it is not a forecast that "
                "existed at the time and it never enters the track record."
                if kind == "replay"
                else "This is a preview computed from everything known so far. It is not "
                "sealed and will move as new results arrive."
            ),
            "kind": "context",
            "source_ids": [_MATCH_ENGINE_SOURCE_ID],
            "number_refs": [],
        }
    ]
    by_family = {entry["family"]: entry for entry in analysis["models"]}
    for family in ("elo_ordlogit", "dixon_coles", "climatological"):
        entry = by_family.get(family)
        probs = entry.get("probs") if entry else None
        if probs is None:
            continue
        role_note = (
            " (a team-blind reference the voices must beat, not a third opinion)"
            if family == "climatological"
            else ""
        )
        facts.append(
            {
                "fact_id": f"council_{family}",
                "text": (
                    f"The {_VOICE_LABELS[family]}{role_note} puts this at {home} "
                    f"{_fmt_pct(probs['home'])}, draw {_fmt_pct(probs['draw'])}, {away} "
                    f"{_fmt_pct(probs['away'])}."
                ),
                "kind": "forecast",
                "source_ids": data_sources,
                "number_refs": [f"mc_{family}_prob_{key}" for key in _OUTCOME_KEYS],
            }
        )
    council = analysis.get("council") or {}
    if council.get("voices", 0) >= 2:
        facts.append(
            {
                "fact_id": "council_agreement",
                "text": (
                    "The two model voices agree on the likeliest outcome."
                    if council.get("voices_agree")
                    else "The two model voices DISAGREE on the likeliest outcome — the ratings "
                    "view and the recent-goals view genuinely part ways on this fixture."
                ),
                "kind": "forecast",
                "source_ids": [_MATCH_ENGINE_SOURCE_ID],
                "number_refs": [],
            }
        )
    if analysis.get("abstained"):
        facts.append(
            {
                "fact_id": "abstained",
                "text": (
                    "The engine abstained from modelling this fixture: at least one side has "
                    "too little history to model honestly. No probabilities were issued."
                ),
                "kind": "context",
                "source_ids": [_MATCH_ENGINE_SOURCE_ID],
                "number_refs": [],
            }
        )
    return facts


def build_match_evidence_bundle(
    analysis: dict[str, Any],
    *,
    notebook_facts: list[dict[str, Any]] | tuple[dict[str, Any], ...] = (),
    notebook_numbers: list[dict[str, Any]] | tuple[dict[str, Any], ...] = (),
    pack_source_ids: tuple[str, ...] = (),
    extra_sources: list[dict[str, Any]] | tuple[dict[str, Any], ...] = (),
) -> dict[str, Any]:
    """Build the evidence bundle for one on-demand MatchAnalysis (no artifact).

    Pure function of its inputs. ``notebook_facts``/``notebook_numbers`` are the
    Commentator's Notebook fold (``notebook_to_evidence``) — appended verbatim, so
    the notes the user reads and the numbers the AI may cite are the same set.
    The AI layer treats this bundle exactly like an artifact bundle: same
    whitelist, same citation rules, same fail-closed review.
    """
    kind = analysis.get("analysis_kind")
    if kind not in {"preview", "replay"}:
        raise ValueError(f"cannot build a match evidence bundle from analysis kind {kind!r}")

    match = analysis["match"]
    payload_hash = hashlib.sha256(_canonical_bytes(analysis)).hexdigest()
    data_sources = [_MATCH_ENGINE_SOURCE_ID, *pack_source_ids]

    council = analysis.get("council") or {}
    leading = council.get("leading_outcome")

    bundle: dict[str, Any] = {
        "schema_version": MATCH_EVIDENCE_SCHEMA_VERSION,
        "bundle_id": "eb_pending00",
        "artifact_id": f"ma_{payload_hash[:20]}",
        "artifact_status": kind,
        "derived_from_payload_sha256": payload_hash,
        "match": {
            "match_id": match["match_id"],
            "competition": match["competition"],
            "stage": None,
            "kickoff_utc": match["kickoff_utc"],
            "home_team": match["home_team"],
            "away_team": match["away_team"],
            "neutral_venue": bool(match["neutral_venue"]),
            "city": None,
            "country": None,
        },
        "forecast_summary": {
            "market": "1x2_regulation",
            "horizon": "pre-kickoff",
            "uncertainty": analysis["uncertainty"],
            "abstained": bool(analysis["abstained"]),
            "leading_outcome": leading,
        },
        "allowed_numbers": [
            *_council_numbers(analysis, data_sources),
            *notebook_numbers,
        ],
        "facts": [*_council_facts(analysis, data_sources), *notebook_facts],
        "features": [
            {
                "feature_id": "analysis_kind",
                "name": "Analysis kind",
                "kind": "categorical",
                "value": kind,
                "value_ref": None,
                "source_ids": [_MATCH_ENGINE_SOURCE_ID],
            },
            {
                "feature_id": "information_cutoff",
                "name": "Information cutoff (UTC)",
                "kind": "timestamp",
                "value": analysis["information_cutoff_utc"],
                "value_ref": None,
                "source_ids": [_MATCH_ENGINE_SOURCE_ID],
            },
        ],
        "sources": _match_sources(pack_source_ids, tuple(extra_sources)),
        "data_quality": {
            "uncertainty": analysis["uncertainty"],
            "abstained": bool(analysis["abstained"]),
            "abstain_reason": analysis.get("abstain_reason"),
            "training_cutoff_utc": analysis["information_cutoff_utc"],
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
