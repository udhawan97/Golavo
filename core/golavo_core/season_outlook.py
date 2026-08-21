"""Leak-safe domestic season outlooks from Golavo's separate model voices.

The simulator is intentionally downstream of a schedule certificate and the
competition-aware standings engine.  It never invents missing fixtures or past
results, never blends council voices, and never enters the sealed forecast
ledger.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from functools import cache
from typing import Any

import numpy as np
import pandas as pd

from golavo_core.artifacts import DECAY_WINDOW_DAYS, MIN_TEAM_MATCHES
from golavo_core.ingest import training_rows
from golavo_core.models import fit_model
from golavo_core.outlook import knockout_advance_probability
from golavo_core.standings import LeagueRule, football_season, league_rule, standings_table

SEASON_OUTLOOK_SCHEMA_VERSION = "0.3.0"
SEASON_OUTLOOK_RULE = "season-mc-2026.07.1"
SEASON_OUTLOOK_LABEL = (
    "Season outlook — a seeded simulation from current model fits. Not a sealed forecast."
)
DEFAULT_ITERATIONS = 10_000
DEFAULT_SEED = 20_260_715
MIN_TRAINING_MATCHES = 20
STAKES = ("title", "top_four", "relegation")
#: Importance is reported from one named voice; council voices are never blended.
IMPORTANCE_VOICE_ID = "elo_ordlogit"
#: A conditional branch thinner than this is sampling noise, so it abstains instead.
MIN_BRANCH_RUNS = 200


def _utc(value: str | pd.Timestamp | None) -> pd.Timestamp:
    timestamp = pd.Timestamp(value or datetime.now(UTC))
    return timestamp.tz_localize("UTC") if timestamp.tzinfo is None else timestamp.tz_convert("UTC")


def _iso(value: pd.Timestamp) -> str:
    return value.isoformat().replace("+00:00", "Z")


def certify_schedule(
    matches: pd.DataFrame,
    *,
    expected_teams: int,
    as_of_utc: str | pd.Timestamp,
) -> dict[str, Any]:
    """Prove whether a double round-robin schedule is structurally complete."""
    as_of = _utc(as_of_utc)
    home = matches.get("home_team", pd.Series(dtype="string")).dropna().astype("string")
    away = matches.get("away_team", pd.Series(dtype="string")).dropna().astype("string")
    teams = sorted(set(home) | set(away))
    pairs = list(zip(home.astype(str), away.astype(str), strict=False))
    unique_pairs = set(pairs)
    self_fixtures = sum(home_team == away_team for home_team, away_team in pairs)
    expected_matches = expected_teams * (expected_teams - 1)
    declared_complete = (
        matches["is_complete"].astype("boolean").fillna(False)
        if "is_complete" in matches
        else pd.Series(False, index=matches.index, dtype="boolean")
    )
    scored = (
        matches["home_score"].notna() & matches["away_score"].notna()
        if {"home_score", "away_score"}.issubset(matches.columns)
        else pd.Series(False, index=matches.index)
    )
    complete_mask = declared_complete & scored
    kickoff = (
        pd.to_datetime(matches["kickoff_utc"], utc=True)
        if "kickoff_utc" in matches
        else pd.Series(pd.NaT, index=matches.index, dtype="datetime64[ns, UTC]")
    )
    incomplete_mask = ~complete_mask
    past_gaps = incomplete_mask & (kickoff < as_of)
    future_completed = complete_mask & (kickoff > as_of)
    duplicate_pairs = max(0, len(pairs) - len(unique_pairs))
    schedule_complete = (
        len(teams) == expected_teams
        and len(matches) == expected_matches
        and len(unique_pairs) == expected_matches
        and duplicate_pairs == 0
        and self_fixtures == 0
    )
    return {
        "expected_teams": expected_teams,
        "observed_teams": len(teams),
        "teams": teams,
        "expected_matches": expected_matches,
        "observed_matches": int(len(matches)),
        "unique_ordered_pairs": len(unique_pairs),
        "duplicate_ordered_pairs": duplicate_pairs,
        "self_fixtures": self_fixtures,
        "incomplete_fixtures": int(incomplete_mask.sum()),
        "past_result_gaps": int(past_gaps.sum()),
        "future_completed_results": int(future_completed.sum()),
        "complete_fixture_list": schedule_complete,
    }


def _blocked(
    *,
    competition_id: str,
    competition_name: str,
    season: str,
    as_of: pd.Timestamp,
    rule: LeagueRule,
    certificate: dict[str, Any],
    reason_code: str,
    reason: str,
    table: list[dict[str, Any]],
    source_ids: list[str],
    remaining_fixtures: list[dict[str, Any]],
    scenario: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "schema_version": SEASON_OUTLOOK_SCHEMA_VERSION,
        "status": "blocked",
        "label": SEASON_OUTLOOK_LABEL,
        "competition_id": competition_id,
        "competition_name": competition_name,
        "season": season,
        "as_of_utc": _iso(as_of),
        "simulation_rule": SEASON_OUTLOOK_RULE,
        "ledger_status": "never_persisted_or_scored_as_a_seal",
        "reason_code": reason_code,
        "reason": reason,
        "standings_rule_id": rule.rule_id,
        "fixture_certificate": certificate,
        "current_table": table,
        "iterations": 0,
        "seed": None,
        "voices": [],
        "remaining_fixtures": remaining_fixtures,
        "scenario": scenario,
        "provenance": {"source_ids": source_ids},
    }


def _remaining_fixtures(schedule: pd.DataFrame, as_of: pd.Timestamp) -> list[dict[str, Any]]:
    complete = schedule["is_complete"].astype("boolean").fillna(False)
    kickoff = pd.to_datetime(schedule["kickoff_utc"], utc=True)
    rows = schedule.loc[~complete & (kickoff > as_of)]
    return [
        {
            "match_id": str(row.match_id),
            "kickoff_utc": _iso(pd.Timestamp(row.kickoff_utc)),
            "home_team": str(row.home_team),
            "away_team": str(row.away_team),
        }
        for row in rows.itertuples(index=False)
    ]


def _apply_forced_results(
    schedule: pd.DataFrame,
    forced_results: list[dict[str, Any]] | None,
    *,
    as_of: pd.Timestamp,
) -> tuple[pd.DataFrame, dict[str, Any] | None]:
    if not forced_results:
        return schedule, None
    if len(forced_results) > 12:
        raise ValueError("a scenario may force at most 12 fixtures")
    result = schedule.copy()
    seen: set[str] = set()
    applied: list[dict[str, Any]] = []
    for item in forced_results:
        match_id = str(item.get("match_id") or "")
        if not match_id or match_id in seen:
            raise ValueError("scenario fixture ids must be non-empty and unique")
        seen.add(match_id)
        try:
            home_score = item["home_score"]
            away_score = item["away_score"]
        except (KeyError, TypeError) as exc:
            raise ValueError("scenario scores must be integers") from exc
        if type(home_score) is not int or type(away_score) is not int:
            raise ValueError("scenario scores must be integers")
        if not 0 <= home_score <= 20 or not 0 <= away_score <= 20:
            raise ValueError("scenario scores must be between 0 and 20")
        selected = result["match_id"].astype("string").eq(match_id)
        if int(selected.sum()) != 1:
            raise ValueError(f"scenario fixture is not in this season: {match_id}")
        row = result.loc[selected].iloc[0]
        kickoff = _utc(row["kickoff_utc"])
        if bool(row["is_complete"]) or kickoff <= as_of:
            raise ValueError(f"scenario fixture is not an unplayed future match: {match_id}")
        result.loc[selected, ["home_score", "away_score", "is_complete"]] = [
            home_score,
            away_score,
            True,
        ]
        applied.append(
            {
                "match_id": match_id,
                "home_team": str(row["home_team"]),
                "away_team": str(row["away_team"]),
                "home_score": home_score,
                "away_score": away_score,
            }
        )
    return result, {
        "hypothetical_only": True,
        "persisted": False,
        "model_input": False,
        "forced_results": applied,
    }


def _conditional_score_matrix(
    matrix: np.ndarray,
    outcome_probabilities: tuple[float, float, float],
) -> np.ndarray:
    """Preserve a voice's 1X2 mass while borrowing only DC score shape."""
    home_mask = np.tril(np.ones_like(matrix, dtype=bool), -1)
    draw_mask = np.eye(matrix.shape[0], matrix.shape[1], dtype=bool)
    away_mask = np.triu(np.ones_like(matrix, dtype=bool), 1)
    combined = np.zeros_like(matrix, dtype=float)
    for probability, mask, fallback in (
        (outcome_probabilities[0], home_mask, (1, 0)),
        (outcome_probabilities[1], draw_mask, (0, 0)),
        (outcome_probabilities[2], away_mask, (0, 1)),
    ):
        shaped = np.where(mask, matrix, 0.0)
        total = float(shaped.sum())
        if total > 0.0:
            combined += float(probability) * shaped / total
        else:
            combined[fallback] += float(probability)
    combined /= combined.sum()
    return combined


def _sample_scores(
    rng: np.random.Generator,
    matrix: np.ndarray,
    iterations: int,
) -> tuple[np.ndarray, np.ndarray]:
    flat = matrix.ravel()
    cdf = np.cumsum(flat)
    cdf[-1] = 1.0
    sampled = np.searchsorted(cdf, rng.random(iterations), side="right")
    width = matrix.shape[1]
    return sampled // width, sampled % width


def _apply_scores(
    points: np.ndarray,
    goals_for: np.ndarray,
    goals_against: np.ndarray,
    wins: np.ndarray,
    home_index: int,
    away_index: int,
    home_goals: np.ndarray,
    away_goals: np.ndarray,
) -> None:
    goals_for[:, home_index] += home_goals
    goals_against[:, home_index] += away_goals
    goals_for[:, away_index] += away_goals
    goals_against[:, away_index] += home_goals
    home_win = home_goals > away_goals
    away_win = home_goals < away_goals
    draw = ~(home_win | away_win)
    points[:, home_index] += 3 * home_win + draw
    points[:, away_index] += 3 * away_win + draw
    wins[:, home_index] += home_win
    wins[:, away_index] += away_win


def _overall_order(
    rule: LeagueRule,
    teams: list[str],
    points: np.ndarray,
    goals_for: np.ndarray,
    goals_against: np.ndarray,
    wins: np.ndarray,
) -> list[int]:
    def key(index: int) -> tuple[Any, ...]:
        values: list[Any] = [-int(points[index])]
        for item in rule.primary[1:]:
            if item == "goal_difference":
                values.append(-int(goals_for[index] - goals_against[index]))
            elif item == "goals_for":
                values.append(-int(goals_for[index]))
            elif item == "wins":
                values.append(-int(wins[index]))
        values.append(teams[index])
        return tuple(values)

    return sorted(range(len(teams)), key=key)


def _head_to_head_order(
    rule: LeagueRule,
    teams: list[str],
    points: np.ndarray,
    goals_for: np.ndarray,
    goals_against: np.ndarray,
    wins: np.ndarray,
    home_indices: np.ndarray,
    away_indices: np.ndarray,
    home_scores: np.ndarray,
    away_scores: np.ndarray,
) -> list[int]:
    overall = _overall_order(rule, teams, points, goals_for, goals_against, wins)
    groups: dict[int, list[int]] = {}
    for team_index in overall:
        groups.setdefault(int(points[team_index]), []).append(team_index)
    ranked: list[int] = []
    for group_points in sorted(groups, reverse=True):
        group = groups[group_points]
        if len(group) == 1:
            ranked.extend(group)
            continue
        member = set(group)
        mini_points = {index: 0 for index in group}
        mini_for = {index: 0 for index in group}
        mini_against = {index: 0 for index in group}
        for match_index, (home, away) in enumerate(zip(home_indices, away_indices, strict=True)):
            home_index = int(home)
            away_index = int(away)
            if home_index not in member or away_index not in member:
                continue
            home_goals = int(home_scores[match_index])
            away_goals = int(away_scores[match_index])
            mini_for[home_index] += home_goals
            mini_against[home_index] += away_goals
            mini_for[away_index] += away_goals
            mini_against[away_index] += home_goals
            if home_goals > away_goals:
                mini_points[home_index] += 3
            elif home_goals < away_goals:
                mini_points[away_index] += 3
            else:
                mini_points[home_index] += 1
                mini_points[away_index] += 1
        group.sort(
            key=lambda index: (
                -mini_points[index],
                -(mini_for[index] - mini_against[index]),
                -mini_for[index],
                -(goals_for[index] - goals_against[index]),
                -goals_for[index],
                -wins[index],
                teams[index],
            )
        )
        ranked.extend(group)
    return ranked


def _largest_remainder_percent(
    counts: np.ndarray,
    *,
    iterations: int,
    slots: int,
    teams: list[str],
) -> np.ndarray:
    exact_units = counts.astype(float) * 1000.0 / iterations
    units = np.floor(exact_units).astype(int)
    remaining = slots * 1000 - int(units.sum())
    order = sorted(
        range(len(teams)),
        key=lambda index: (-(exact_units[index] - units[index]), teams[index]),
    )
    for index in order[:remaining]:
        units[index] += 1
    return units.astype(float) / 10.0


def fixture_importance(
    *,
    home_scores: np.ndarray,
    away_scores: np.ndarray,
    home_flags: Mapping[str, np.ndarray],
    away_flags: Mapping[str, np.ndarray],
    home_team: str,
    away_team: str,
    min_branch_runs: int = MIN_BRANCH_RUNS,
) -> dict[str, Any]:
    """How far one fixture's result moves each club's season stakes.

    Partitions simulation runs that already happened by this fixture's outcome
    and compares the two branches; nothing is re-simulated.  A branch thinner
    than ``min_branch_runs`` abstains rather than reporting a noisy conditional.
    """
    home_win = home_scores > away_scores
    away_win = home_scores < away_scores
    home_wins = int(np.count_nonzero(home_win))
    away_wins = int(np.count_nonzero(away_win))
    coverage = {
        "home_wins": home_wins,
        "draws": int(home_scores.size) - home_wins - away_wins,
        "away_wins": away_wins,
    }
    sides = (
        (home_team, "home", home_flags, home_win, away_win),
        (away_team, "away", away_flags, away_win, home_win),
    )
    if min(home_wins, away_wins) < min_branch_runs:
        return {
            "status": "insufficient_coverage",
            "score": None,
            "coverage": coverage,
            "clubs": [
                {"team": team, "side": side, "score": None, "swings": None}
                for team, side, _, _, _ in sides
            ],
        }
    clubs: list[dict[str, Any]] = []
    for team, side, flags, won, lost in sides:
        won_runs = int(np.count_nonzero(won))
        lost_runs = int(np.count_nonzero(lost))
        swings = {
            stake: round(
                float(
                    abs(
                        int(np.count_nonzero(flags[stake] & won)) / won_runs
                        - int(np.count_nonzero(flags[stake] & lost)) / lost_runs
                    )
                ),
                9,
            )
            for stake in STAKES
        }
        clubs.append(
            {
                "team": team,
                "side": side,
                "score": max(swings.values()),
                "swings": swings,
            }
        )
    return {
        "status": "ok",
        "score": max(club["score"] for club in clubs),
        "coverage": coverage,
        "clubs": clubs,
    }


def team_history_coverage(
    training: pd.DataFrame,
    as_of: pd.Timestamp,
    teams: list[str],
    source_ids: list[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Each team's trainable history, on the exact floor a seal abstains below.

    A promoted club can have no history in this competition at all, and the
    simulation still has to place it somewhere in the table — so it produces a
    number for a club the per-match council refuses to forecast. Coventry City
    enters 2026-27 with 0 trainable matches, and two voices put its relegation at
    64% and 9%: that spread is the models' priors talking, not evidence about
    Coventry.

    Suppressing the row is not an option — the club really is in the league, and
    the other 19 projections only mean anything if it is simulated. So the count
    travels beside the number and the reader is told which is which.

    It has to be the same count the seal path abstains on, or the outlook and the
    council can disagree about which clubs are forecastable — the one thing this
    field exists to prevent. That path scopes a fixture's training view to its own
    competition AND its own source, so ``source_ids`` narrows the same way here.
    The Premier League already carries two source ids (footballcsv deep history
    and football.json), and they only fail to collide today because footballcsv
    stops eight years outside the window.
    """
    start = pd.Timestamp(as_of) - pd.Timedelta(days=DECAY_WINDOW_DAYS)
    dates = pd.to_datetime(training["date"], utc=True)
    window = training.loc[dates >= start]
    if source_ids:
        window = window.loc[window["source_id"].astype("string").isin(list(source_ids))]
    home = window["home_team"].astype("string")
    away = window["away_team"].astype("string")
    coverage: dict[str, dict[str, Any]] = {}
    for team in teams:
        matches = int((home.eq(team) | away.eq(team)).sum())
        coverage[team] = {
            "matches": matches,
            "model_floor": MIN_TEAM_MATCHES,
            "status": "ok" if matches >= MIN_TEAM_MATCHES else "below_model_floor",
        }
    return coverage


def _voice_simulation(
    *,
    voice_id: str,
    label: str,
    role: str,
    rule: LeagueRule,
    season: str,
    teams: list[str],
    schedule: pd.DataFrame,
    iterations: int,
    seed: int,
    dixon_coles: Any,
    model: Any | None,
    history_coverage: dict[str, dict[str, Any]],
    importance_match_ids: set[str] | None = None,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]] | None]:
    team_index = {team: index for index, team in enumerate(teams)}
    current = standings_table(schedule, rule.competition_id, season=season, teams=teams)
    by_team = {row["team"]: row for row in current}
    shape = (iterations, len(teams))
    points = np.zeros(shape, dtype=np.int16)
    goals_for = np.zeros(shape, dtype=np.int16)
    goals_against = np.zeros(shape, dtype=np.int16)
    wins = np.zeros(shape, dtype=np.int16)
    for team, index in team_index.items():
        row = by_team[team]
        points[:, index] = int(row["points"])
        goals_for[:, index] = int(row["goals_for"])
        goals_against[:, index] = int(row["goals_against"])
        wins[:, index] = int(row["won"])

    rng = np.random.default_rng(seed)
    home_indices = np.array(
        [team_index[str(value)] for value in schedule["home_team"]], dtype=np.int16
    )
    away_indices = np.array(
        [team_index[str(value)] for value in schedule["away_team"]], dtype=np.int16
    )
    all_home_scores = np.zeros((iterations, len(schedule)), dtype=np.int8)
    all_away_scores = np.zeros((iterations, len(schedule)), dtype=np.int8)
    complete = schedule["is_complete"].astype("boolean").fillna(False).to_numpy()
    for match_index, row in enumerate(schedule.itertuples(index=False)):
        home = str(row.home_team)
        away = str(row.away_team)
        if complete[match_index]:
            all_home_scores[:, match_index] = int(row.home_score)
            all_away_scores[:, match_index] = int(row.away_score)
            continue
        dc_prediction = dixon_coles.predict(home, away, False)
        if dc_prediction.matrix is None:
            raise RuntimeError("Dixon-Coles score matrix unexpectedly unavailable")
        if voice_id == "dixon_coles":
            matrix = dc_prediction.matrix
        else:
            probabilities = (
                (1 / 3, 1 / 3, 1 / 3)
                if model is None
                else tuple(float(value) for value in model.predict(home, away, False).probs)
            )
            matrix = _conditional_score_matrix(dc_prediction.matrix, probabilities)
        home_goals, away_goals = _sample_scores(rng, matrix, iterations)
        all_home_scores[:, match_index] = home_goals
        all_away_scores[:, match_index] = away_goals
        _apply_scores(
            points,
            goals_for,
            goals_against,
            wins,
            team_index[home],
            team_index[away],
            home_goals,
            away_goals,
        )

    @cache
    def playoff_probability(first: int, second: int) -> float:
        if model is None:
            return 0.5
        return knockout_advance_probability(model, teams[first], teams[second])

    stake_flags = {
        stake: np.zeros((iterations, len(teams)), dtype=bool) for stake in STAKES
    }
    top_slots = min(4, len(teams))
    for iteration in range(iterations):
        if rule.head_to_head_on_points:
            order = _head_to_head_order(
                rule,
                teams,
                points[iteration],
                goals_for[iteration],
                goals_against[iteration],
                wins[iteration],
                home_indices,
                away_indices,
                all_home_scores[iteration],
                all_away_scores[iteration],
            )
        else:
            order = _overall_order(
                rule,
                teams,
                points[iteration],
                goals_for[iteration],
                goals_against[iteration],
                wins[iteration],
            )
        if "title" in rule.playoff_boundaries and len(order) > 1:
            first, second = order[:2]
            if points[iteration, first] == points[iteration, second]:
                if rng.random() > playoff_probability(first, second):
                    order[0], order[1] = order[1], order[0]
        safe_index = len(teams) - rule.relegation_slots - 1
        relegated_index = safe_index + 1
        if (
            "last-relegation-place" in rule.playoff_boundaries
            and safe_index >= 0
            and points[iteration, order[safe_index]] == points[iteration, order[relegated_index]]
        ):
            safe = order[safe_index]
            relegated = order[relegated_index]
            if rng.random() > playoff_probability(safe, relegated):
                order[safe_index], order[relegated_index] = relegated, safe
        stake_flags["title"][iteration, order[0]] = True
        stake_flags["top_four"][iteration, order[:top_slots]] = True
        stake_flags["relegation"][iteration, order[-rule.relegation_slots :]] = True

    title_counts = stake_flags["title"].sum(axis=0)
    top_four_counts = stake_flags["top_four"].sum(axis=0)
    relegation_counts = stake_flags["relegation"].sum(axis=0)
    expected_points = points.mean(axis=0)
    title_display = _largest_remainder_percent(
        title_counts, iterations=iterations, slots=1, teams=teams
    )
    top_display = _largest_remainder_percent(
        top_four_counts, iterations=iterations, slots=top_slots, teams=teams
    )
    relegation_display = _largest_remainder_percent(
        relegation_counts,
        iterations=iterations,
        slots=rule.relegation_slots,
        teams=teams,
    )
    rows = [
        {
            "team": team,
            "title": round(float(title_counts[index] / iterations), 9),
            "top_four": round(float(top_four_counts[index] / iterations), 9),
            "relegation": round(float(relegation_counts[index] / iterations), 9),
            "expected_points": round(float(expected_points[index]), 6),
            "display_percent": {
                "title": float(title_display[index]),
                "top_four": float(top_display[index]),
                "relegation": float(relegation_display[index]),
            },
            # Whether this club's number rests on evidence or on the model's
            # prior. Simulating it is unavoidable; showing it unlabelled is not.
            "history_coverage": history_coverage[team],
        }
        for index, team in enumerate(teams)
    ]
    rows.sort(key=lambda row: (-row["title"], -row["top_four"], row["team"]))
    importance: dict[str, dict[str, Any]] | None = None
    if importance_match_ids is not None:
        importance = {}
        for match_index, value in enumerate(schedule["match_id"].astype("string")):
            match_id = str(value)
            if match_id not in importance_match_ids:
                continue
            home_index = int(home_indices[match_index])
            away_index = int(away_indices[match_index])
            importance[match_id] = fixture_importance(
                home_scores=all_home_scores[:, match_index],
                away_scores=all_away_scores[:, match_index],
                home_flags={stake: flags[:, home_index] for stake, flags in stake_flags.items()},
                away_flags={stake: flags[:, away_index] for stake, flags in stake_flags.items()},
                home_team=teams[home_index],
                away_team=teams[away_index],
            )
    voice = {
        "voice_id": voice_id,
        "label": label,
        "role": role,
        "scoreline_method": (
            "Dixon-Coles joint score matrix"
            if voice_id == "dixon_coles"
            else (
                "equal 1X2 mass with Dixon-Coles conditional score shape"
                if model is None
                else "Elo 1X2 mass with Dixon-Coles conditional score shape"
            )
        ),
        "teams": rows,
        "totals": {
            "title": round(float(title_counts.sum() / iterations), 9),
            "top_four": round(float(top_four_counts.sum() / iterations), 9),
            "relegation": round(float(relegation_counts.sum() / iterations), 9),
        },
    }
    return voice, importance


def season_outlook(
    frame: pd.DataFrame,
    competition_id: str,
    *,
    as_of_utc: str | pd.Timestamp | None = None,
    season: str | None = None,
    iterations: int = DEFAULT_ITERATIONS,
    seed: int = DEFAULT_SEED,
    forced_results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a typed season state, simulating only a certified future schedule."""
    if iterations <= 0:
        raise ValueError("iterations must be positive")
    rule = league_rule(competition_id)
    as_of = _utc(as_of_utc)
    season_id = season or football_season(as_of)
    competition_rows = frame.loc[frame["competition"].astype("string").eq(rule.source_name)].copy()
    row_seasons = pd.to_datetime(competition_rows["kickoff_utc"], utc=True).map(football_season)
    schedule = competition_rows.loc[row_seasons.eq(season_id)].copy()
    schedule = schedule.sort_values(["kickoff_utc", "match_id"], kind="mergesort")
    certificate = certify_schedule(
        schedule,
        expected_teams=rule.expected_teams,
        as_of_utc=as_of,
    )
    source_ids = sorted(
        str(value)
        for value in schedule.get("source_id", pd.Series(dtype="string")).dropna().unique()
    )
    teams = certificate["teams"]
    remaining_fixtures = _remaining_fixtures(schedule, as_of)
    scenario_schedule, scenario = _apply_forced_results(
        schedule, forced_results, as_of=as_of
    )
    visible_schedule = scenario_schedule.copy()
    future_mask = pd.to_datetime(visible_schedule["kickoff_utc"], utc=True) > as_of
    forced_ids = {
        str(item["match_id"])
        for item in (scenario or {}).get("forced_results", [])
    }
    visible_schedule.loc[
        future_mask & ~visible_schedule["match_id"].astype("string").isin(forced_ids),
        "is_complete",
    ] = False
    table = (
        standings_table(visible_schedule, competition_id, season=season_id, teams=teams)
        if len(schedule)
        else []
    )
    common = {
        "competition_id": competition_id,
        "competition_name": rule.source_name,
        "season": season_id,
        "as_of": as_of,
        "rule": rule,
        "certificate": certificate,
        "table": table,
        "source_ids": source_ids,
        "remaining_fixtures": remaining_fixtures,
        "scenario": scenario,
    }
    display_season = season_id.replace("-", "–")
    if schedule.empty:
        return _blocked(
            **common,
            reason_code="fixtures_not_published",
            reason=(f"No {display_season} fixtures are present in Golavo's pinned lawful source."),
        )
    if certificate["future_completed_results"]:
        return _blocked(
            **common,
            reason_code="future_result_leak",
            reason=(
                f"{certificate['future_completed_results']} future fixture(s) are marked complete; "
                "Golavo rejected the snapshot to protect the cutoff."
            ),
        )
    if certificate["past_result_gaps"]:
        return _blocked(
            **common,
            reason_code="past_result_gaps",
            reason=(
                f"{certificate['past_result_gaps']} fixture(s) have passed without a result; "
                "refresh the source before simulating."
            ),
        )
    if not certificate["complete_fixture_list"]:
        return _blocked(
            **common,
            reason_code="incomplete_fixture_list",
            reason=(
                "The fixture list failed the double round-robin completeness certificate; "
                "Golavo will not invent missing matches."
            ),
        )
    if certificate["incomplete_fixtures"] == 0:
        return {
            **_blocked(
                **common,
                reason_code="season_complete",
                reason="All fixtures are complete; the table is final and no projection is needed.",
            ),
            "status": "complete",
        }

    training = training_rows(competition_rows, as_of)
    if len(training) < MIN_TRAINING_MATCHES:
        return _blocked(
            **common,
            reason_code="insufficient_training_history",
            reason=(
                f"Only {len(training)} completed pre-cutoff matches are available; "
                f"{MIN_TRAINING_MATCHES} are required."
            ),
        )
    cutoff = _iso(as_of)
    coverage = team_history_coverage(training, as_of, teams, source_ids)
    elo = fit_model("elo_ordlogit", training, cutoff)
    dixon_coles = fit_model("dixon_coles", training, cutoff)
    ratings_voice, importance = _voice_simulation(
        voice_id=IMPORTANCE_VOICE_ID,
        label="Ratings voice",
        role="voice",
        rule=rule,
        season=season_id,
        teams=teams,
        schedule=scenario_schedule,
        iterations=iterations,
        seed=seed,
        dixon_coles=dixon_coles,
        history_coverage=coverage,
        model=elo,
        importance_match_ids={fixture["match_id"] for fixture in remaining_fixtures},
    )
    goal_voice, _ = _voice_simulation(
        voice_id="dixon_coles",
        label="Goal-model voice",
        role="voice",
        rule=rule,
        season=season_id,
        teams=teams,
        schedule=scenario_schedule,
        iterations=iterations,
        seed=seed + 1,
        dixon_coles=dixon_coles,
        history_coverage=coverage,
        model=dixon_coles,
    )
    baseline_voice, _ = _voice_simulation(
        voice_id="equal-chance-baseline",
        label="Equal-chance baseline",
        role="baseline",
        rule=rule,
        season=season_id,
        teams=teams,
        schedule=scenario_schedule,
        iterations=iterations,
        seed=seed + 2,
        dixon_coles=dixon_coles,
        history_coverage=coverage,
        model=None,
    )
    voices = [ratings_voice, goal_voice, baseline_voice]
    for fixture in remaining_fixtures:
        entry = (importance or {}).get(fixture["match_id"])
        if entry is not None:
            fixture["importance"] = {"voice_id": IMPORTANCE_VOICE_ID, **entry}
    return {
        "schema_version": SEASON_OUTLOOK_SCHEMA_VERSION,
        "status": "available",
        "label": SEASON_OUTLOOK_LABEL,
        "competition_id": competition_id,
        "competition_name": rule.source_name,
        "season": season_id,
        "as_of_utc": cutoff,
        "simulation_rule": SEASON_OUTLOOK_RULE,
        "ledger_status": "never_persisted_or_scored_as_a_seal",
        "reason_code": None,
        "reason": None,
        "standings_rule_id": rule.rule_id,
        "fixture_certificate": certificate,
        "current_table": table,
        "iterations": iterations,
        "seed": seed,
        "voices": voices,
        "remaining_fixtures": remaining_fixtures,
        "scenario": scenario,
        "provenance": {
            "source_ids": source_ids,
            "training_source_ids": sorted(
                str(value) for value in training["source_id"].dropna().unique()
            ),
            "training_data_through_utc": _iso(
                pd.to_datetime(training["kickoff_utc"], utc=True).max()
            ),
        },
    }
