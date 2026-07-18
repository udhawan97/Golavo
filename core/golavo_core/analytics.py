"""Cutoff-safe analytics derived only from Golavo's committed match index.

The module intentionally keeps the scope narrow: team strengths are comparable
only inside one competition, workload counts only matches present in the index,
and schedule difficulty stays blocked until a fixture source supplies an explicit
completeness certificate.  Every calculation filters to ``as_of_utc`` before it
selects teams or fits a model, so appending future rows cannot rewrite history.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pandas as pd

from golavo_core.competitions import competition_by_id
from golavo_core.ingest.snapshot import (
    ORDER_INSTANT,
    completed_view,
    iso_utc,
    to_utc,
)
from golavo_core.models.candidates import PoissonModel
from golavo_core.trends import month_end_checkpoints

ANALYTICS_SCHEMA_VERSION = "0.1.0"
MIN_STRENGTH_MATCHES = 8


def _utc(value: str | pd.Timestamp | None) -> pd.Timestamp:
    """As-of defaults to now; the shared rule owns the timezone handling."""
    return to_utc(value or datetime.now(UTC))


def _active_teams(rows: pd.DataFrame, anchor: pd.Timestamp) -> list[str]:
    # "Active" means present near the competition's latest indexed match, not
    # merely somewhere in the last two seasons (which would retain relegated
    # clubs on a current league page).
    recent = rows.loc[rows[ORDER_INSTANT] >= anchor - pd.Timedelta(days=90)]
    values = pd.concat([recent["home_team"], recent["away_team"]], ignore_index=True)
    return sorted(str(value) for value in values.dropna().unique())


def _team_match_counts(rows: pd.DataFrame) -> dict[str, int]:
    values = pd.concat([rows["home_team"], rows["away_team"]], ignore_index=True)
    return {str(team): int(count) for team, count in values.value_counts().items()}


def _strength_trends(rows: pd.DataFrame) -> dict[str, Any]:
    if rows.empty:
        return {
            "status": "unavailable",
            "reason": "No completed matches exist for this competition before the cutoff.",
            "method": "time-decayed-poisson-rates-v1",
            "minimum_matches": MIN_STRENGTH_MATCHES,
            "teams": [],
        }

    anchor = rows[ORDER_INSTANT].max()
    teams = _active_teams(rows, anchor)
    trends: dict[str, list[dict[str, Any]]] = {team: [] for team in teams}
    for checkpoint in month_end_checkpoints(anchor):
        training = rows.loc[rows[ORDER_INSTANT] <= checkpoint].copy()
        counts = _team_match_counts(training)
        eligible = [team for team in teams if counts.get(team, 0) >= MIN_STRENGTH_MATCHES]
        if not eligible:
            continue
        # The shipped goal voice's fit: chronological, exponentially decayed and
        # shrunk by an eight-match prior. It asserts that no row exceeds cutoff.
        model = PoissonModel("poisson_independent", xi=0.001).fit(
            training.drop(columns=[ORDER_INSTANT]), iso_utc(checkpoint)
        )
        for team in eligible:
            attack = float(model.attack.get(team, 1.0))
            defence_conceding = float(model.defence.get(team, 1.0))
            trends[team].append(
                {
                    "cutoff_utc": iso_utc(checkpoint),
                    "sample_matches": counts[team],
                    "attack_index": round(100.0 * attack, 1),
                    # The fitted defence multiplier is goals conceded (lower is
                    # stronger). Inverting it makes every displayed index share
                    # the intuitive "above 100 is stronger" direction.
                    "defence_index": round(100.0 / defence_conceding, 1),
                    "overall_index": round(100.0 * (attack / defence_conceding) ** 0.5, 1),
                }
            )

    result = [
        {"team": team, "current": points[-1], "trend": points}
        for team, points in trends.items()
        if points
    ]
    result.sort(key=lambda item: (-item["current"]["overall_index"], item["team"]))
    return {
        "status": "available" if result else "insufficient_sample",
        "reason": (
            None
            if result
            else f"No active team has at least {MIN_STRENGTH_MATCHES} completed matches."
        ),
        "method": "time-decayed-poisson-rates-v1",
        "minimum_matches": MIN_STRENGTH_MATCHES,
        "data_through_utc": iso_utc(anchor),
        "comparison_scope": "this_competition_only",
        "teams": result,
    }


def _workload(frame: pd.DataFrame, teams: list[str], as_of: pd.Timestamp) -> dict[str, Any]:
    """Rest and congestion per team, counted across every competition in the index.

    Takes the whole frame, not the competition's slice: a Bundesliga side's rest
    days must count the cup tie it played midweek.
    """
    completed = completed_view(frame, as_of_utc=as_of).rows
    rows: list[dict[str, Any]] = []
    for team in teams:
        team_rows = completed.loc[
            completed["home_team"].eq(team) | completed["away_team"].eq(team)
        ].sort_values(ORDER_INSTANT, kind="mergesort")
        if team_rows.empty:
            continue
        last_match = team_rows[ORDER_INSTANT].iloc[-1]
        rest_days = max(0, int((as_of - last_match).total_seconds() // 86400))

        match_dates = team_rows[ORDER_INSTANT]
        matches_7 = int((match_dates > as_of - pd.Timedelta(days=7)).sum())
        matches_14 = int((match_dates > as_of - pd.Timedelta(days=14)).sum())
        matches_28 = int((match_dates > as_of - pd.Timedelta(days=28)).sum())
        if rest_days < 3 or matches_14 >= 4:
            congestion = "high"
        elif rest_days < 5 or matches_14 >= 3:
            congestion = "elevated"
        else:
            congestion = "normal"
        rows.append(
            {
                "team": team,
                "last_indexed_match_utc": iso_utc(last_match),
                "rest_days": rest_days,
                "matches_last_7_days": matches_7,
                "matches_last_14_days": matches_14,
                "matches_last_28_days": matches_28,
                "congestion": congestion,
            }
        )
    rows.sort(key=lambda item: (item["rest_days"], item["team"]))
    return {
        "status": "available" if rows else "unavailable",
        "reason": None if rows else "No indexed matches exist for these teams before the cutoff.",
        "method": "indexed-match-counts-v1",
        "coverage_note": "Counts include only competitions present in Golavo's local index.",
        "teams": rows,
    }


def competition_analytics(
    frame: pd.DataFrame,
    competition_id: str,
    *,
    as_of_utc: str | pd.Timestamp | None = None,
) -> dict[str, Any]:
    """Build strength and workload analytics for one declared competition."""
    competition = competition_by_id(competition_id)
    if competition is None:
        raise ValueError(f"unknown competition_id: {competition_id}")
    as_of = _utc(as_of_utc)
    played = completed_view(frame, as_of_utc=as_of).rows
    source_names = set(competition["source_competition_names"])
    competition_rows = played.loc[played["competition"].isin(source_names)].copy()
    strength = _strength_trends(competition_rows)
    active_teams = [str(item["team"]) for item in strength.get("teams", [])]
    if not active_teams and not competition_rows.empty:
        active_teams = _active_teams(competition_rows, competition_rows[ORDER_INSTANT].max())
    workload = _workload(frame, active_teams, as_of)
    workload_rows = played.loc[
        played["home_team"].isin(active_teams) | played["away_team"].isin(active_teams)
    ]
    source_ids = sorted(
        {
            str(value)
            for value in pd.concat(
                [competition_rows["source_id"], workload_rows["source_id"]],
                ignore_index=True,
            ).dropna()
        }
    )
    return {
        "schema_version": ANALYTICS_SCHEMA_VERSION,
        "competition_id": competition_id,
        "competition_name": competition["display_name"],
        "as_of_utc": iso_utc(as_of),
        "scope": {
            "team_category": competition["team_scope"],
            "strength_comparison": "this_competition_only",
            "model_input": False,
        },
        "provenance": {"source_ids": source_ids},
        "strength_trends": strength,
        "rest_congestion": workload,
        "schedule_difficulty": {
            "status": "blocked",
            "reason": (
                "Golavo has no completeness certificate for this competition's remaining "
                "fixtures. A partial schedule cannot produce an honest difficulty rating."
            ),
            "required_capability": "complete_remaining_fixtures",
        },
    }
