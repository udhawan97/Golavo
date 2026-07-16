"""Deterministic tournament outlooks from Golavo's own fitted model voices.

The World Cup outlook is deliberately not a seal and never enters the forecast
ledger.  It fits the same Elo and Dixon-Coles voices as Match Analysis at one
explicit cutoff, then exactly enumerates the four-team bracket.  There is no
Monte Carlo noise and no blended consensus number.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pandas as pd

from golavo_core.artifacts import MIN_TEAM_MATCHES
from golavo_core.ingest import training_rows
from golavo_core.models import fit_model

OUTLOOK_SCHEMA_VERSION = "0.1.0"
OUTLOOK_RULE = "ko-2026.07.1"
OUTLOOK_LABEL = (
    "Tournament outlook — a simulation from current model fits. Not a sealed forecast."
)
_WORLD_CUP = "FIFA World Cup"
_SEMIFINAL_START = pd.Timestamp("2026-07-14T00:00:00Z")
_SEMIFINAL_END = pd.Timestamp("2026-07-16T00:00:00Z")
_METRICS = ("reach_final", "reach_third_place_match", "champion", "third")


class OutlookUnavailable(ValueError):
    """The committed snapshot cannot support an honest tournament outlook."""


def _utc(value: str | pd.Timestamp | None) -> pd.Timestamp:
    timestamp = pd.Timestamp(value or datetime.now(UTC))
    return (
        timestamp.tz_localize("UTC")
        if timestamp.tzinfo is None
        else timestamp.tz_convert("UTC")
    )


def _iso(value: pd.Timestamp) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _normalise_pair(home: float, away: float) -> tuple[float, float]:
    total = home + away
    if total <= 0.0:
        return 0.5, 0.5
    return home / total, away / total


def knockout_advance_probability(model: Any, home_team: str, away_team: str) -> float:
    """Probability the nominal home team advances under ``ko-2026.07.1``.

    The Dixon-Coles voice follows the registered rule literally: regulation
    win mass plus regulation-draw mass times a 30-minute matrix built from the
    same fitted rates at one-third duration; an extra-time draw is a 50/50
    shootout.  Elo has no score process, so its disclosed fallback uses its own
    regulation non-draw share beyond 90 minutes.  Both paths remain wholly
    inside the fitted Golavo voice and preserve home/away complementarity.
    """
    regulation = model.predict(home_team, away_team, True)
    home_90, draw_90, away_90 = (float(value) for value in regulation.probs)
    if hasattr(model, "predict_duration"):
        extra_time = model.predict_duration(
            home_team,
            away_team,
            True,
            fraction=1.0 / 3.0,
        )
        home_et, draw_et, _away_et = (float(value) for value in extra_time.probs)
        beyond_90 = home_et + 0.5 * draw_et
    else:
        beyond_90, _ = _normalise_pair(home_90, away_90)
    return min(1.0, max(0.0, home_90 + draw_90 * beyond_90))


def _winner_probability(
    advance: Callable[[str, str], float],
    home_team: str,
    away_team: str,
    winner: str,
) -> float:
    home = float(advance(home_team, away_team))
    return home if winner == home_team else 1.0 - home


def enumerate_four_team_bracket(
    semifinal_one: tuple[str, str],
    semifinal_two: tuple[str, str],
    *,
    advance: Callable[[str, str], float],
) -> list[dict[str, Any]]:
    """Exactly enumerate two semifinals, a final and a third-place match."""
    a, b = semifinal_one
    c, d = semifinal_two
    teams = (a, b, c, d)
    if len(set(teams)) != 4:
        raise ValueError("a four-team bracket requires four distinct teams")
    totals = {team: {metric: 0.0 for metric in _METRICS} for team in teams}

    p_a = float(advance(a, b))
    p_c = float(advance(c, d))
    if not 0.0 <= p_a <= 1.0 or not 0.0 <= p_c <= 1.0:
        raise ValueError("advance probabilities must be in [0, 1]")

    semifinal_paths = (
        (a, b, p_a),
        (b, a, 1.0 - p_a),
    )
    other_paths = (
        (c, d, p_c),
        (d, c, 1.0 - p_c),
    )
    for finalist_one, third_one, probability_one in semifinal_paths:
        totals[finalist_one]["reach_final"] += probability_one
        totals[third_one]["reach_third_place_match"] += probability_one
        for finalist_two, third_two, probability_two in other_paths:
            path = probability_one * probability_two
            final_home = float(advance(finalist_one, finalist_two))
            third_home = float(advance(third_one, third_two))
            totals[finalist_one]["champion"] += path * final_home
            totals[finalist_two]["champion"] += path * (1.0 - final_home)
            totals[third_one]["third"] += path * third_home
            totals[third_two]["third"] += path * (1.0 - third_home)

    # The second semifinal's direct reach probabilities are constant across the
    # first semifinal paths, so stamp them once after enumeration.
    totals[c]["reach_final"] = p_c
    totals[d]["reach_final"] = 1.0 - p_c
    totals[c]["reach_third_place_match"] = 1.0 - p_c
    totals[d]["reach_third_place_match"] = p_c

    rows = [
        {
            "team": team,
            **{metric: round(float(totals[team][metric]), 9) for metric in _METRICS},
        }
        for team in teams
    ]
    rows.sort(key=lambda item: (-item["champion"], item["team"]))
    return rows


def _resolved_at(row: Any, as_of: pd.Timestamp) -> bool:
    """Whether a semifinal is both played and knowable at ``as_of``.

    The index carries results for matches later than a past cutoff, so completion
    alone cannot pin a bracket: the kickoff must also have passed. Mirrors the
    training-row guard, which already refuses post-cutoff semifinals.
    """
    return bool(row.get("is_complete") or False) and _utc(row["kickoff_utc"]) <= as_of


def _fixed_semifinal_probability(row: Any, as_of: pd.Timestamp) -> float | None:
    if not _resolved_at(row, as_of):
        return None
    home = row.get("home_score")
    away = row.get("away_score")
    if pd.isna(home) or pd.isna(away) or int(home) == int(away):
        raise OutlookUnavailable(
            "A completed semifinal is level in the match index, but the shootout winner is not "
            "part of the index contract. Refresh to a bracket that names the finalists."
        )
    return 1.0 if int(home) > int(away) else 0.0


def _semifinals(frame: pd.DataFrame) -> list[Any]:
    kickoff = pd.to_datetime(frame["kickoff_utc"], utc=True)
    selected = frame.loc[
        frame["competition"].astype("string").eq(_WORLD_CUP)
        & (kickoff >= _SEMIFINAL_START)
        & (kickoff < _SEMIFINAL_END)
    ].copy()
    selected["_kickoff"] = pd.to_datetime(selected["kickoff_utc"], utc=True)
    selected = selected.sort_values(["_kickoff", "match_id"], kind="mergesort")
    if len(selected) != 2:
        raise OutlookUnavailable(
            "The pinned snapshot does not contain exactly two resolved 2026 World Cup semifinals."
        )
    return [row for _, row in selected.iterrows()]


def _team_counts(training: pd.DataFrame, teams: tuple[str, ...]) -> dict[str, int]:
    return {
        team: int(
            (
                training["home_team"].astype("string").eq(team)
                | training["away_team"].astype("string").eq(team)
            ).sum()
        )
        for team in teams
    }


def _voice(
    family: str,
    label: str,
    training: pd.DataFrame,
    cutoff_utc: str,
    semifinal_rows: list[Any],
    as_of: pd.Timestamp,
) -> dict[str, Any]:
    model = fit_model(family, training, cutoff_utc)
    fixed = [_fixed_semifinal_probability(row, as_of) for row in semifinal_rows]

    def advance(home_team: str, away_team: str) -> float:
        for index, row in enumerate(semifinal_rows):
            if str(row["home_team"]) == home_team and str(row["away_team"]) == away_team:
                if fixed[index] is not None:
                    return float(fixed[index])
        return knockout_advance_probability(model, home_team, away_team)

    first = (str(semifinal_rows[0]["home_team"]), str(semifinal_rows[0]["away_team"]))
    second = (str(semifinal_rows[1]["home_team"]), str(semifinal_rows[1]["away_team"]))
    rows = enumerate_four_team_bracket(first, second, advance=advance)
    return {
        "voice_id": family,
        "label": label,
        "role": "voice",
        "draw_resolution": (
            "same fitted scoring rates at one-third duration; extra-time draw becomes a "
            "50/50 shootout"
            if family == "dixon_coles"
            else "Elo regulation non-draw share; no score process is invented"
        ),
        "teams": rows,
        "totals": {
            metric: round(sum(float(row[metric]) for row in rows), 9) for metric in _METRICS
        },
    }


def _baseline(semifinal_rows: list[Any], as_of: pd.Timestamp) -> dict[str, Any]:
    fixed = [_fixed_semifinal_probability(row, as_of) for row in semifinal_rows]

    def advance(home_team: str, away_team: str) -> float:
        for index, row in enumerate(semifinal_rows):
            if str(row["home_team"]) == home_team and str(row["away_team"]) == away_team:
                if fixed[index] is not None:
                    return float(fixed[index])
        return 0.5

    first = (str(semifinal_rows[0]["home_team"]), str(semifinal_rows[0]["away_team"]))
    second = (str(semifinal_rows[1]["home_team"]), str(semifinal_rows[1]["away_team"]))
    rows = enumerate_four_team_bracket(first, second, advance=advance)
    return {
        "voice_id": "equal-chance-baseline",
        "label": "Equal-chance baseline",
        "role": "baseline",
        "draw_resolution": "50/50 advancement in every unresolved knockout match",
        "teams": rows,
        "totals": {
            metric: round(sum(float(row[metric]) for row in rows), 9) for metric in _METRICS
        },
    }


def world_cup_2026_outlook(
    frame: pd.DataFrame,
    *,
    as_of_utc: str | pd.Timestamp | None = None,
) -> dict[str, Any]:
    """Build the current four-team World Cup outlook without persistence."""
    as_of = _utc(as_of_utc)
    semifinal_rows = _semifinals(frame)
    teams = tuple(
        str(row[field])
        for row in semifinal_rows
        for field in ("home_team", "away_team")
    )

    international = frame.loc[frame["source_kind"].astype("string").eq("international")].copy()
    training = training_rows(international, as_of)
    # Exact-kickoff overlay rows remain martj42 rows in the index; only completed
    # rows enter training.  Belt-and-braces: never train on either unresolved
    # semifinal even when a malformed snapshot marks it complete after ``as_of``.
    semifinal_ids = {str(row["match_id"]) for row in semifinal_rows}
    training = training.loc[
        ~training["match_id"].astype("string").isin(semifinal_ids)
        | (pd.to_datetime(training["kickoff_utc"], utc=True) <= as_of)
    ].copy()
    counts = _team_counts(training, teams)
    below_floor = {team: count for team, count in counts.items() if count < MIN_TEAM_MATCHES}
    if below_floor:
        detail = ", ".join(f"{team}={count}" for team, count in sorted(below_floor.items()))
        raise OutlookUnavailable(
            f"Insufficient pre-cutoff history ({detail}); {MIN_TEAM_MATCHES} matches are required."
        )

    cutoff = _iso(as_of)
    voices = [
        _voice("elo_ordlogit", "Ratings voice", training, cutoff, semifinal_rows, as_of),
        _voice("dixon_coles", "Goal-model voice", training, cutoff, semifinal_rows, as_of),
        _baseline(semifinal_rows, as_of),
    ]
    semifinal_payload = []
    stale = False
    for row in semifinal_rows:
        kickoff = _utc(row["kickoff_utc"])
        complete = _resolved_at(row, as_of)
        stale = stale or (not complete and kickoff < as_of)
        semifinal_payload.append(
            {
                "match_id": str(row["match_id"]),
                "kickoff_utc": _iso(kickoff),
                "home_team": str(row["home_team"]),
                "away_team": str(row["away_team"]),
                "status": "complete" if complete else "unresolved",
            }
        )
    data_through = pd.to_datetime(training["kickoff_utc"], utc=True).max()
    return {
        "schema_version": OUTLOOK_SCHEMA_VERSION,
        "status": "available",
        "label": OUTLOOK_LABEL,
        "tournament_id": "worldcup-2026",
        "tournament_name": "2026 FIFA World Cup",
        "as_of_utc": cutoff,
        "data_through_utc": _iso(data_through),
        "outlook_rule": OUTLOOK_RULE,
        "method": "exact-four-team-bracket-enumeration",
        "ledger_status": "never_persisted_or_scored_as_a_seal",
        "snapshot_status": "result_refresh_needed" if stale else "current_for_index",
        "snapshot_note": (
            "At least one semifinal kickoff has passed without a result in this pinned snapshot; "
            "probabilities remain a snapshot outlook, not a live result."
            if stale
            else "All unresolved semifinal kickoffs are still in the future at this cutoff."
        ),
        "semifinals": semifinal_payload,
        "voices": voices,
        "provenance": {
            "training_source_ids": sorted(
                str(value) for value in training["source_id"].dropna().astype("string").unique()
            ),
            "fixture_source_id": "openfootball-worldcup-json",
        },
    }
