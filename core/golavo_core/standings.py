"""Competition-aware domestic league tables from completed indexed results.

The table engine is deliberately separate from season simulation.  It can be
validated byte-for-byte on completed seasons, then reused as the terminal ranker
inside a seeded outlook.  Every rule has a stable id and an explicit fallback;
alphabetical order is only a final deterministic representation tie-break, never
presented as a sporting rule.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

STANDINGS_SCHEMA_VERSION = "0.1.0"

# Match results cannot encode disciplinary points deductions.  Keep each known
# adjustment season-scoped and reviewable instead of silently changing source
# scores.  Values are applied after result points and exposed in every row.
POINT_ADJUSTMENTS: dict[tuple[str, str, str], int] = {
    ("england-premier-league", "2023-24", "Everton"): -8,
    ("england-premier-league", "2023-24", "Nottingham Forest"): -4,
    ("france-ligue-1", "2023-24", "Montpellier"): -1,
}


@dataclass(frozen=True)
class LeagueRule:
    competition_id: str
    source_name: str
    rule_id: str
    expected_teams: int
    champions_league_slots: int
    relegation_slots: int
    primary: tuple[str, ...]
    head_to_head_on_points: bool = False
    playoff_boundaries: tuple[str, ...] = ()


LEAGUE_RULES: dict[str, LeagueRule] = {
    "england-premier-league": LeagueRule(
        "england-premier-league",
        "English Premier League",
        "england-2024.1",
        20,
        4,
        3,
        ("points", "goal_difference", "goals_for", "head_to_head"),
    ),
    "spain-la-liga": LeagueRule(
        "spain-la-liga",
        "La Liga",
        "spain-2024.1",
        20,
        4,
        3,
        ("points", "head_to_head", "goal_difference", "goals_for"),
        head_to_head_on_points=True,
    ),
    "germany-bundesliga": LeagueRule(
        "germany-bundesliga",
        "Bundesliga",
        "germany-2024.1",
        18,
        4,
        2,
        ("points", "goal_difference", "goals_for", "wins", "head_to_head"),
    ),
    "italy-serie-a": LeagueRule(
        "italy-serie-a",
        "Serie A",
        "italy-2024.1",
        20,
        4,
        3,
        ("points", "head_to_head", "goal_difference", "goals_for"),
        head_to_head_on_points=True,
        playoff_boundaries=("title", "last-relegation-place"),
    ),
    "france-ligue-1": LeagueRule(
        "france-ligue-1",
        "Ligue 1",
        "france-2024.1",
        18,
        4,
        2,
        ("points", "goal_difference", "goals_for", "head_to_head"),
    ),
}


def league_rule(competition_id: str) -> LeagueRule:
    try:
        return LEAGUE_RULES[competition_id]
    except KeyError as exc:
        raise ValueError(
            f"no verified standings rule for competition_id: {competition_id}"
        ) from exc


def football_season(value: Any) -> str:
    timestamp = pd.Timestamp(value)
    start = timestamp.year if timestamp.month >= 7 else timestamp.year - 1
    return f"{start}-{str(start + 1)[-2:]}"


def _blank(team: str) -> dict[str, Any]:
    return {
        "team": team,
        "played": 0,
        "won": 0,
        "drawn": 0,
        "lost": 0,
        "goals_for": 0,
        "goals_against": 0,
        "goal_difference": 0,
        "points_adjustment": 0,
        "points": 0,
    }


def _apply(table: dict[str, dict[str, Any]], home: str, away: str, hg: int, ag: int) -> None:
    home_row = table.setdefault(home, _blank(home))
    away_row = table.setdefault(away, _blank(away))
    home_row["played"] += 1
    away_row["played"] += 1
    home_row["goals_for"] += hg
    home_row["goals_against"] += ag
    away_row["goals_for"] += ag
    away_row["goals_against"] += hg
    if hg > ag:
        home_row["won"] += 1
        away_row["lost"] += 1
        home_row["points"] += 3
    elif hg < ag:
        away_row["won"] += 1
        home_row["lost"] += 1
        away_row["points"] += 3
    else:
        home_row["drawn"] += 1
        away_row["drawn"] += 1
        home_row["points"] += 1
        away_row["points"] += 1


def _mini_table(matches: pd.DataFrame, teams: set[str]) -> dict[str, dict[str, Any]]:
    mini = {team: _blank(team) for team in teams}
    scoped = matches.loc[
        matches["home_team"].astype("string").isin(teams)
        & matches["away_team"].astype("string").isin(teams)
    ]
    for row in scoped.itertuples(index=False):
        _apply(
            mini,
            str(row.home_team),
            str(row.away_team),
            int(row.home_score),
            int(row.away_score),
        )
    for row in mini.values():
        row["goal_difference"] = row["goals_for"] - row["goals_against"]
    return mini


def _head_to_head_complete(matches: pd.DataFrame, teams: set[str]) -> bool:
    if len(teams) < 2:
        return True
    scoped = matches.loc[
        matches["home_team"].astype("string").isin(teams)
        & matches["away_team"].astype("string").isin(teams)
    ]
    pairs = {(str(row.home_team), str(row.away_team)) for row in scoped.itertuples(index=False)}
    return len(pairs) == len(teams) * (len(teams) - 1)


def _overall_key(row: dict[str, Any], rule: LeagueRule) -> tuple[Any, ...]:
    values: list[Any] = [-int(row["points"])]
    for item in rule.primary[1:]:
        if item == "head_to_head":
            continue
        if item == "goal_difference":
            values.append(-int(row["goal_difference"]))
        elif item == "goals_for":
            values.append(-int(row["goals_for"]))
        elif item == "wins":
            values.append(-int(row["won"]))
    values.append(str(row["team"]))
    return tuple(values)


def _rank_with_head_to_head(
    rows: list[dict[str, Any]],
    matches: pd.DataFrame,
    rule: LeagueRule,
) -> list[dict[str, Any]]:
    by_points: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        by_points.setdefault(int(row["points"]), []).append(row)
    ranked: list[dict[str, Any]] = []
    for points in sorted(by_points, reverse=True):
        group = by_points[points]
        teams = {str(row["team"]) for row in group}
        if len(group) == 1 or not _head_to_head_complete(matches, teams):
            ranked.extend(sorted(group, key=lambda row: _overall_key(row, rule)))
            continue
        mini = _mini_table(matches, teams)
        ranked.extend(
            sorted(
                group,
                key=lambda row: (
                    -int(mini[str(row["team"])]["points"]),
                    -int(mini[str(row["team"])]["goal_difference"]),
                    -int(mini[str(row["team"])]["goals_for"]),
                    -int(row["goal_difference"]),
                    -int(row["goals_for"]),
                    -int(row["won"]),
                    str(row["team"]),
                ),
            )
        )
    return ranked


def standings_table(
    matches: pd.DataFrame,
    competition_id: str,
    *,
    season: str | None = None,
    teams: list[str] | tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    """Return a stable league table from completed results only."""
    rule = league_rule(competition_id)
    required = {"home_team", "away_team", "home_score", "away_score", "is_complete"}
    missing = required - set(matches.columns)
    if missing:
        raise ValueError(f"standings input missing columns: {sorted(missing)}")
    completed = matches.loc[matches["is_complete"].astype("boolean").fillna(False)].copy()
    completed = completed.loc[completed["home_score"].notna() & completed["away_score"].notna()]
    table = {str(team): _blank(str(team)) for team in (teams or [])}
    for row in completed.itertuples(index=False):
        _apply(
            table,
            str(row.home_team),
            str(row.away_team),
            int(row.home_score),
            int(row.away_score),
        )
    rows = list(table.values())
    for row in rows:
        row["goal_difference"] = row["goals_for"] - row["goals_against"]
        adjustment = (
            POINT_ADJUSTMENTS.get(
                (competition_id, season, str(row["team"])),
                0,
            )
            if season is not None
            else 0
        )
        row["points_adjustment"] = adjustment
        row["points"] += adjustment
    if rule.head_to_head_on_points:
        rows = _rank_with_head_to_head(rows, completed, rule)
    else:
        rows.sort(key=lambda row: _overall_key(row, rule))
    return [{"position": position, **row} for position, row in enumerate(rows, start=1)]


def standings_snapshot(
    matches: pd.DataFrame,
    competition_id: str,
    *,
    season: str,
    teams: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    rule = league_rule(competition_id)
    return {
        "schema_version": STANDINGS_SCHEMA_VERSION,
        "competition_id": competition_id,
        "season": season,
        "rule_id": rule.rule_id,
        "tie_break_order": list(rule.primary),
        "playoff_boundaries": list(rule.playoff_boundaries),
        "table": standings_table(matches, competition_id, season=season, teams=teams),
    }
