"""Deterministic fantasy-pick sealing, rival derivation, and scoring.

This module is deliberately pure.  It knows how to turn a leak-safe match
analysis into five rival calls, content-address a locked user pick, score a
finished match, and aggregate season views.  Ledger I/O and kickoff state live
in ``golavo_server.picks``.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from jsonschema import Draft202012Validator, FormatChecker

PICK_SCHEMA_VERSION = "0.1.0"
Outcome = Literal["home", "draw", "away"]
OUTCOMES: tuple[Outcome, ...] = ("home", "draw", "away")


def canonical_pick_bytes(record: dict[str, Any]) -> bytes:
    """Return stable UTF-8 JSON bytes without forecast-specific rounding."""
    return json.dumps(
        record,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def pick_id(payload: dict[str, Any]) -> str:
    """Return the content address for a stable locked-pick payload."""
    digest = hashlib.sha256(canonical_pick_bytes(payload)).hexdigest()
    return f"pk_{digest[:20]}"


def pick_payload_sha256(record: dict[str, Any]) -> str:
    """Hash a locked record without its self-referential digest."""
    payload = copy.deepcopy(record)
    payload.pop("payload_sha256", None)
    return hashlib.sha256(canonical_pick_bytes(payload)).hexdigest()


def _stable_pick_payload(record: dict[str, Any]) -> dict[str, Any]:
    payload = copy.deepcopy(record)
    payload.pop("pick_id", None)
    payload.pop("payload_sha256", None)
    return payload


def validate_user_pick(record: dict[str, Any], schema_path: Path | None = None) -> None:
    if schema_path is None:
        from golavo_core.resources import user_pick_schema_path

        schema_path = user_pick_schema_path()
    schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    validator.evolve(schema=schema["$defs"]["UserPick"]).validate(record)


def verify_pick_integrity(
    record: dict[str, Any], *, expected_id: str | None = None
) -> dict[str, Any]:
    """Validate a locked pick and prove its id, digest, and filename agree."""
    validate_user_pick(record)
    if record.get("status") != "locked":
        raise ValueError("only locked picks carry an immutable integrity stamp")

    stored_hash = record.get("payload_sha256")
    recomputed_hash = pick_payload_sha256(record)
    if stored_hash != recomputed_hash:
        raise ValueError(
            f"payload_sha256 mismatch: stored {stored_hash!r}, content hashes to {recomputed_hash}"
        )

    recomputed_id = pick_id(_stable_pick_payload(record))
    if record.get("pick_id") != recomputed_id:
        raise ValueError(
            f"pick_id mismatch: stored {record.get('pick_id')!r}, content addresses "
            f"to {recomputed_id}"
        )
    if expected_id is not None and expected_id != recomputed_id:
        raise ValueError(
            f"pick filename {expected_id!r} does not match its content id {recomputed_id}"
        )
    return record


def outcome_of(home_goals: int, away_goals: int) -> Outcome:
    if home_goals > away_goals:
        return "home"
    if home_goals < away_goals:
        return "away"
    return "draw"


def _modal_outcome(probs: dict[str, Any]) -> Outcome:
    # Tuple order is the product decision's deterministic home > draw > away
    # tie-break; max returns the first equal value.
    return max(OUTCOMES, key=lambda outcome: float(probs[outcome]))


def derive_rival_picks(analysis: dict[str, Any]) -> dict[str, Any]:
    """Snapshot each council model's honest scoring capability and call."""
    rivals: list[dict[str, Any]] = []
    for model in analysis.get("models", []):
        family = str(model["family"])
        probs = model.get("probs")
        matrix = model.get("score_matrix")
        abstained = bool(model.get("abstained")) or probs is None

        score: dict[str, int] | None = None
        outcome: Outcome | None = None
        capability: Literal["score", "outcome_only", "abstained"]
        if abstained:
            capability = "abstained"
        elif matrix is not None:
            likely = matrix["most_likely"]
            # Stored ScoreMatrix uses ``home``/``away``. Accept the explicit
            # ``*_goals`` spelling as well for contract fixtures and migrations.
            home = int(likely.get("home", likely.get("home_goals")))
            away = int(likely.get("away", likely.get("away_goals")))
            score = {"home_goals": home, "away_goals": away}
            outcome = outcome_of(home, away)
            capability = "score"
        else:
            outcome = _modal_outcome(probs)
            capability = "outcome_only"

        rivals.append(
            {
                "family": family,
                "capability": capability,
                "score_pick": score,
                "outcome_pick": outcome,
            }
        )

    return {
        "analysis_fingerprint": {
            "index_fingerprint": str(
                analysis.get("index_fingerprint") or analysis.get("_index_fingerprint") or "unknown"
            ),
            "analysis_schema_version": str(analysis.get("schema_version") or "unknown"),
            "information_cutoff_utc": str(
                analysis.get("information_cutoff_utc") or "1970-01-01T00:00:00Z"
            ),
        },
        "rivals": rivals,
    }


def _points_for_call(
    *,
    score: dict[str, Any] | None,
    outcome: str | None,
    result_home: int,
    result_away: int,
) -> dict[str, int]:
    actual = outcome_of(result_home, result_away)
    exact = (
        int(
            score is not None
            and int(score["home_goals"]) == result_home
            and int(score["away_goals"]) == result_away
        )
        * 3
    )
    outcome_points = int(outcome == actual)
    return {"exact": exact, "outcome": outcome_points, "total": exact + outcome_points}


def score_pick(locked_record: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    """Score the user and all frozen rivals under the same additive rules."""
    result_home = int(result["home_goals"])
    result_away = int(result["away_goals"])
    user_call = locked_record["user_pick"]
    user_base = _points_for_call(
        score={
            "home_goals": int(user_call["home_goals"]),
            "away_goals": int(user_call["away_goals"]),
        },
        outcome=user_call.get("outcome")
        or outcome_of(int(user_call["home_goals"]), int(user_call["away_goals"])),
        result_home=result_home,
        result_away=result_away,
    )

    rival_points: list[dict[str, Any]] = []
    played_totals: list[int] = []
    for rival in locked_record.get("rivals", []):
        points = _points_for_call(
            score=rival.get("score_pick"),
            outcome=rival.get("outcome_pick"),
            result_home=result_home,
            result_away=result_away,
        )
        if rival.get("capability") != "abstained":
            played_totals.append(points["total"])
        rival_points.append({"family": rival["family"], **points})

    best_rival = max(played_totals, default=0)
    beat_ai = bool(played_totals) and user_base["total"] > best_rival
    bonus = int(beat_ai)
    return {
        "user": {
            "exact": user_base["exact"],
            "outcome": user_base["outcome"],
            "bonus": bonus,
            "total": user_base["total"] + bonus,
        },
        "rivals": rival_points,
        "beat_ai": beat_ai,
        "best_rival_total": best_rival,
    }


def football_season(kickoff_utc: str) -> str:
    kickoff = datetime.fromisoformat(kickoff_utc.replace("Z", "+00:00"))
    kickoff = kickoff.astimezone(UTC)
    first_year = kickoff.year if (kickoff.month, kickoff.day) >= (7, 1) else kickoff.year - 1
    return f"{first_year}-{str(first_year + 1)[-2:]}"


def _ordered_views(views: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        views,
        key=lambda view: (
            view["record"]["match"]["kickoff_utc"],
            view["record"]["match"]["match_id"],
        ),
    )


def season_summary(views: list[dict[str, Any]], *, season: str | None = None) -> dict[str, Any]:
    """Aggregate ledger views without persisting derived standings."""
    filtered = [
        view
        for view in views
        if season is None or football_season(view["record"]["match"]["kickoff_utc"]) == season
    ]
    ordered = _ordered_views(filtered)
    counts = {status: 0 for status in ("draft", "locked", "scored", "void")}
    for view in ordered:
        status = str(view["status"])
        if status in counts:
            counts[status] += 1

    scored = [view for view in ordered if view.get("status") == "scored"]
    user = {"total": 0, "exact": 0, "outcome": 0, "bonus": 0}
    rival_totals: dict[str, dict[str, Any]] = {}
    series: list[dict[str, Any]] = []
    goal_diff_errors: list[int] = []
    best_streak = 0
    current_streak = 0

    for view in scored:
        scoring = view["scoring"]
        for key in user:
            user[key] += int(scoring["user"][key])
        for rival in scoring.get("rivals", []):
            row = rival_totals.setdefault(
                str(rival["family"]),
                {"family": str(rival["family"]), "total": 0, "exact": 0, "outcome": 0},
            )
            for key in ("total", "exact", "outcome"):
                row[key] += int(rival[key])

        if int(scoring["user"]["outcome"]) >= 1:
            current_streak += 1
            best_streak = max(best_streak, current_streak)
        else:
            current_streak = 0

        call = view["record"]["user_pick"]
        result = view["result"]
        goal_diff_errors.append(
            abs(
                (int(call["home_goals"]) - int(call["away_goals"]))
                - (int(result["home_goals"]) - int(result["away_goals"]))
            )
        )
        series.append(
            {
                "kickoff_utc": view["record"]["match"]["kickoff_utc"],
                "match_id": view["record"]["match"]["match_id"],
                "user_total": user["total"],
                "per_family_totals": {
                    family: row["total"] for family, row in sorted(rival_totals.items())
                },
            }
        )

    scored_count = len(scored)
    exact_calls = sum(int(view["scoring"]["user"]["exact"] > 0) for view in scored)
    winner_calls = sum(int(view["scoring"]["user"]["outcome"] > 0) for view in scored)
    return {
        "schema_version": PICK_SCHEMA_VERSION,
        "season": season,
        "counts": counts,
        "user": user,
        "rivals": [rival_totals[key] for key in sorted(rival_totals)],
        "series": series,
        "accuracy": {
            "exact": exact_calls / scored_count if scored_count else 0.0,
            "winner": winner_calls / scored_count if scored_count else 0.0,
        },
        "streak": {"current": current_streak, "best": best_streak},
        "goal_diff_mae": (
            sum(goal_diff_errors) / len(goal_diff_errors) if goal_diff_errors else 0.0
        ),
    }
