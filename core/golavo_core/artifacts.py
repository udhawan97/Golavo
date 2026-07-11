"""Canonical, immutable ForecastArtifact sealing and scoring."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from jsonschema import Draft202012Validator, FormatChecker

from golavo_core import __version__
from golavo_core.ingest import (
    load_matches,
    snapshot_anchor_utc,
    snapshot_descriptor,
    training_rows,
)
from golavo_core.models import FAMILIES, fit_model

SCHEMA_VERSION = "0.2.0"
GENERATOR = f"golavo-core/{__version__}"
DECAY_WINDOW_DAYS = 365 * 8
MIN_TEAM_MATCHES = 10


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp must include a UTC offset: {value}")
    return parsed.astimezone(UTC).replace(microsecond=0)


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _schema_path() -> Path:
    return Path(__file__).resolve().parents[2] / "docs/contracts/forecast_artifact.schema.json"


def validate_artifact(artifact: dict[str, Any], schema_path: Path | None = None) -> None:
    schema = json.loads((schema_path or _schema_path()).read_text(encoding="utf-8"))
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(artifact)
    probs = artifact["forecast"]["probs"]
    if probs is not None and abs(sum(probs.values()) - 1.0) > 1e-6:
        raise ValueError("forecast probabilities must sum to 1")


def canonical_bytes(value: dict[str, Any]) -> bytes:
    """Return sorted canonical JSON with forecast probabilities rounded to 6 dp."""
    payload = copy.deepcopy(value)
    probs = payload.get("forecast", {}).get("probs")
    if probs is not None:
        rounded = {key: round(float(probs[key]), 6) for key in ("home", "draw", "away")}
        drift = round(1.0 - sum(rounded.values()), 6)
        largest = max(rounded, key=rounded.get)
        rounded[largest] = round(rounded[largest] + drift, 6)
        payload["forecast"]["probs"] = rounded
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def payload_sha256(artifact: dict[str, Any]) -> str:
    """Hash canonical JSON excluding the self-referential digest field."""
    payload = copy.deepcopy(artifact)
    payload["provenance"].pop("payload_sha256", None)
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def _code_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parents[2],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "0000000"


def _params_hash(params: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_bytes({"params": params})).hexdigest()


def _artifact_id(stable_payload: dict[str, Any]) -> str:
    digest = hashlib.sha256(canonical_bytes(stable_payload)).hexdigest()
    return f"fa_{digest[:20]}"


def _find_match(
    matches: pd.DataFrame,
    date: str,
    home_team: str,
    away_team: str,
    match_id: str | None = None,
) -> pd.Series:
    day = pd.Timestamp(date)
    rows = matches.loc[
        matches["date"].eq(day)
        & matches["home_team"].eq(home_team)
        & matches["away_team"].eq(away_team)
    ]
    if match_id is not None:
        rows = rows.loc[rows["match_id"].eq(match_id)]
    if len(rows) != 1:
        raise ValueError(
            f"expected exactly one match for {date} {home_team} v {away_team}; found {len(rows)}"
        )
    return rows.iloc[0]


def _team_counts(train: pd.DataFrame, as_of: datetime, teams: tuple[str, str]) -> dict[str, int]:
    start = pd.Timestamp(as_of) - pd.Timedelta(days=DECAY_WINDOW_DAYS)
    dates = pd.to_datetime(train["date"], utc=True)
    window = train.loc[dates >= start]
    return {
        team: int((window["home_team"].eq(team) | window["away_team"].eq(team)).sum())
        for team in teams
    }


def _write_artifact(artifact: dict[str, Any], output_dir: Path) -> Path:
    validate_artifact(artifact)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{artifact['artifact_id']}.json"
    bytes_to_write = canonical_bytes(artifact) + b"\n"
    if path.exists() and path.read_bytes() != bytes_to_write:
        raise FileExistsError(f"immutable artifact collision at {path}")
    path.write_bytes(bytes_to_write)
    event = {
        "artifact_id": artifact["artifact_id"],
        "created_at_utc": artifact["provenance"]["created_at_utc"],
        "payload_sha256": artifact["provenance"]["payload_sha256"],
        "status": artifact["status"],
        "supersedes": artifact.get("supersedes"),
    }
    line = canonical_bytes(event) + b"\n"
    audit_path = output_dir / "audit.jsonl"
    existing = audit_path.read_bytes().splitlines(keepends=True) if audit_path.exists() else []
    if line not in existing:
        with audit_path.open("ab") as stream:
            stream.write(line)
    return path


def seal_forecast(
    *,
    pack_dir: Path,
    output_dir: Path,
    date: str,
    home_team: str,
    away_team: str,
    as_of_utc: str,
    horizon: str = "T-24h",
    family: str = "elo_ordlogit",
    seed: int = 20260710,
    match_id: str | None = None,
) -> Path:
    """Seal a deterministic forecast and append one audit event."""
    if family not in FAMILIES:
        raise ValueError(f"unknown model family: {family}")
    as_of = _utc(as_of_utc)
    snapshot = snapshot_descriptor(pack_dir)
    anchor = _utc(snapshot_anchor_utc(snapshot))
    if anchor > as_of:
        raise ValueError(
            "cannot seal as-of a time before the snapshot's data state existed "
            "(upstream commit time, or our retrieval time when no commit time is pinned)"
        )

    matches = load_matches(pack_dir)
    match = _find_match(matches, date, home_team, away_team, match_id)
    if bool(match["is_complete"]):
        raise ValueError(
            "fixture already has a result in this snapshot; a forward seal targets a "
            "scheduled fixture — never re-forecast a played match as if it were upcoming"
        )
    kickoff = pd.Timestamp(match["kickoff_utc"]).to_pydatetime()
    if as_of >= kickoff:
        raise ValueError(
            "sealed_at_utc must be before kickoff_utc (dates-only source: kickoff is "
            "the conservative 00:00 UTC day proxy)"
        )
    cutoff = min(as_of, kickoff - pd.Timedelta(seconds=1).to_pytimedelta())
    train = training_rows(matches, _iso(cutoff))
    train = train.loc[~train["match_id"].eq(match["match_id"])].copy()
    counts = _team_counts(train, as_of, (home_team, away_team))
    abstained = min(counts.values()) < MIN_TEAM_MATCHES

    probs: dict[str, float] | None = None
    expected_goals: dict[str, float] | None = None
    params: dict[str, Any] = {"minimum_team_matches": MIN_TEAM_MATCHES}
    if not abstained:
        model = fit_model(family, train, _iso(cutoff))
        prediction = model.predict(home_team, away_team, bool(match["neutral"]))
        probs = dict(zip(("home", "draw", "away"), prediction.probs, strict=True))
        params.update(prediction.params)
        if prediction.expected_goals is not None:
            expected_goals = {
                "home": round(prediction.expected_goals[0], 6),
                "away": round(prediction.expected_goals[1], 6),
            }

    minimum_count = min(counts.values())
    uncertainty = "high" if minimum_count < 20 else "medium" if minimum_count < 40 else "low"
    created = _iso(as_of)
    artifact: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "artifact_id": "fa_pending00",
        "status": "abstained" if abstained else "sealed",
        "supersedes": None,
        "match": {
            "match_id": str(match["match_id"]),
            "competition": str(match["tournament"]),
            "stage": None,
            "kickoff_utc": _iso(kickoff),
            "home_team": home_team,
            "away_team": away_team,
            "neutral_venue": bool(match["neutral"]),
            "city": None if pd.isna(match["city"]) else str(match["city"]),
            "country": None if pd.isna(match["country"]) else str(match["country"]),
        },
        "forecast": {
            "market": "1x2_regulation",
            "sealed_at_utc": created,
            "horizon": horizon,
            "probs": probs,
            "expected_goals": expected_goals,
            "abstained": abstained,
            "abstain_reason": (
                f"insufficient data: {home_team}={counts[home_team]}, "
                f"{away_team}={counts[away_team]}; require {MIN_TEAM_MATCHES} each"
                if abstained
                else None
            ),
            "uncertainty": uncertainty,
        },
        "model": {
            "model_id": f"{family}_phase0",
            "family": family,
            "version": __version__,
            "params_hash": _params_hash(params),
            "code_git_sha": _code_sha(),
            "seed": seed,
        },
        "inputs": {"training_cutoff_utc": _iso(cutoff), "snapshots": [snapshot]},
        "provenance": {
            "created_at_utc": created,
            "generator": GENERATOR,
            "deterministic": True,
            "payload_sha256": "0" * 64,
        },
        "evaluation": None,
    }
    stable = copy.deepcopy(artifact)
    stable.pop("artifact_id")
    stable["provenance"].pop("payload_sha256")
    artifact["artifact_id"] = _artifact_id(stable)
    artifact["provenance"]["payload_sha256"] = payload_sha256(artifact)
    return _write_artifact(artifact, output_dir)


def score_forecast(*, artifact_path: Path, newer_pack_dir: Path, output_dir: Path) -> Path:
    """Score a seal from a newer snapshot, writing a superseding artifact."""
    sealed = json.loads(artifact_path.read_text(encoding="utf-8"))
    validate_artifact(sealed)
    if sealed["status"] != "sealed" or sealed["forecast"]["probs"] is None:
        raise ValueError("only a non-abstained sealed artifact can be scored")
    newer_snapshot = snapshot_descriptor(newer_pack_dir)
    old_anchor = max(
        _utc(snapshot_anchor_utc(item)) for item in sealed["inputs"]["snapshots"]
    )
    new_anchor = _utc(snapshot_anchor_utc(newer_snapshot))
    if new_anchor <= old_anchor:
        raise ValueError(
            "scoring requires a snapshot whose data state is strictly newer than the seal's"
        )

    match = sealed["match"]
    matches = load_matches(newer_pack_dir)
    actual = _find_match(
        matches,
        match["kickoff_utc"][:10],
        match["home_team"],
        match["away_team"],
        match["match_id"],
    )
    if not bool(actual["is_complete"]):
        raise ValueError("newer snapshot does not contain a completed result for this match")
    home_goals = int(actual["home_score"])
    away_goals = int(actual["away_score"])
    outcome = "home" if home_goals > away_goals else "draw" if home_goals == away_goals else "away"
    probs = sealed["forecast"]["probs"]
    assigned = float(probs[outcome])
    one_hot = {"home": 0.0, "draw": 0.0, "away": 0.0}
    one_hot[outcome] = 1.0
    brier = sum((float(probs[key]) - one_hot[key]) ** 2 for key in one_hot)

    scored = copy.deepcopy(sealed)
    scored["status"] = "scored"
    scored["supersedes"] = sealed["artifact_id"]
    scored["inputs"]["snapshots"] = [*sealed["inputs"]["snapshots"], newer_snapshot]
    scored["evaluation"] = {
        "actual": {"home_goals": home_goals, "away_goals": away_goals, "outcome": outcome},
        "scored_at_utc": _iso(new_anchor),
        "metrics": {
            "log_loss": round(-math.log(max(assigned, 1e-12)), 6),
            "brier": round(brier, 6),
            "prob_assigned_to_outcome": round(assigned, 6),
        },
    }
    scored["provenance"]["created_at_utc"] = _iso(new_anchor)
    scored["provenance"]["payload_sha256"] = "0" * 64
    stable = copy.deepcopy(scored)
    stable.pop("artifact_id")
    stable["provenance"].pop("payload_sha256")
    scored["artifact_id"] = _artifact_id(stable)
    scored["provenance"]["payload_sha256"] = payload_sha256(scored)
    return _write_artifact(scored, output_dir)


def void_forecast(
    *, artifact_path: Path, output_dir: Path, voided_at_utc: str, reason: str
) -> Path:
    """Void a seal (postponement, abandonment): an immutable successor, never a result."""
    sealed = json.loads(artifact_path.read_text(encoding="utf-8"))
    validate_artifact(sealed)
    if sealed["status"] not in {"sealed", "abstained"}:
        raise ValueError("only a sealed or abstained artifact can be voided")
    if not reason.strip():
        raise ValueError("voiding requires a recorded reason")
    voided = copy.deepcopy(sealed)
    voided["status"] = "voided"
    voided["supersedes"] = sealed["artifact_id"]
    voided["void_reason"] = reason.strip()
    voided["provenance"]["created_at_utc"] = _iso(_utc(voided_at_utc))
    voided["provenance"]["payload_sha256"] = "0" * 64
    stable = copy.deepcopy(voided)
    stable.pop("artifact_id")
    stable["provenance"].pop("payload_sha256")
    voided["artifact_id"] = _artifact_id(stable)
    voided["provenance"]["payload_sha256"] = payload_sha256(voided)
    return _write_artifact(voided, output_dir)
