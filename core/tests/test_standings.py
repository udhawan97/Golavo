from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from golavo_core.standings import football_season, standings_table

ROOT = Path(__file__).resolve().parents[2]

EXPECTED_2023_24 = {
    "england-premier-league": (
        "English Premier League",
        [
            "Manchester City",
            "Arsenal",
            "Liverpool",
            "Aston Villa",
            "Tottenham Hotspur",
            "Chelsea",
            "Newcastle United",
            "Manchester United",
            "West Ham United",
            "Crystal Palace",
            "Brighton & Hove Albion",
            "Bournemouth",
            "Fulham",
            "Wolverhampton Wanderers",
            "Everton",
            "Brentford",
            "Nottingham Forest",
            "Luton Town",
            "Burnley",
            "Sheffield United",
        ],
    ),
    "spain-la-liga": (
        "La Liga",
        [
            "Real Madrid",
            "Barcelona",
            "Girona",
            "Atlético Madrid",
            "Athletic Club",
            "Real Sociedad",
            "Real Betis",
            "Villarreal",
            "Valencia",
            "Alavés",
            "Osasuna",
            "Getafe",
            "Celta Vigo",
            "Sevilla",
            "Mallorca",
            "Las Palmas",
            "Rayo Vallecano",
            "Cádiz",
            "Almería",
            "Granada",
        ],
    ),
    "germany-bundesliga": (
        "Bundesliga",
        [
            "Bayer Leverkusen",
            "Stuttgart",
            "Bayern München",
            "RB Leipzig",
            "Borussia Dortmund",
            "Eintracht Frankfurt",
            "Hoffenheim",
            "Heidenheim",
            "Werder Bremen",
            "Freiburg",
            "Augsburg",
            "Wolfsburg",
            "Mainz",
            "Borussia Mönchengladbach",
            "Union Berlin",
            "Bochum",
            "Köln",
            "Darmstadt",
        ],
    ),
    "italy-serie-a": (
        "Serie A",
        [
            "Inter",
            "Milan",
            "Juventus",
            "Atalanta",
            "Bologna",
            "Roma",
            "Lazio",
            "Fiorentina",
            "Torino",
            "Napoli",
            "Genoa",
            "Monza",
            "Hellas Verona",
            "Lecce",
            "Udinese",
            "Cagliari",
            "Empoli",
            "Frosinone",
            "Sassuolo",
            "Salernitana",
        ],
    ),
    "france-ligue-1": (
        "Ligue 1",
        [
            "Paris Saint-Germain",
            "Monaco",
            "Stade Brestois",
            "Lille",
            "Nice",
            "Lyon",
            "Lens",
            "Marseille",
            "Stade de Reims",
            "Stade Rennais",
            "Toulouse",
            "Montpellier",
            "Strasbourg",
            "Nantes",
            "Le Havre",
            "Lorient",
            "Metz",
            "Clermont Foot",
        ],
    ),
}


@pytest.mark.parametrize("competition_id", sorted(EXPECTED_2023_24))
def test_final_2023_24_table_matches_the_independently_checked_order(
    competition_id: str,
) -> None:
    source_name, expected = EXPECTED_2023_24[competition_id]
    frame = pd.read_parquet(ROOT / "data" / "index" / "matches_index.parquet")
    kickoff = pd.to_datetime(frame["kickoff_utc"], utc=True)
    season = kickoff.map(football_season)
    rows = frame.loc[frame["competition"].astype("string").eq(source_name) & season.eq("2023-24")]
    table = standings_table(rows, competition_id, season="2023-24")
    assert [row["team"] for row in table] == expected
    assert all(row["played"] in {34, 38} for row in table)


def test_points_deductions_are_explicit_and_season_scoped() -> None:
    frame = pd.read_parquet(ROOT / "data" / "index" / "matches_index.parquet")
    kickoff = pd.to_datetime(frame["kickoff_utc"], utc=True)
    rows = frame.loc[
        frame["competition"].astype("string").eq("English Premier League")
        & kickoff.map(football_season).eq("2023-24")
    ]
    table = {
        row["team"]: row
        for row in standings_table(rows, "england-premier-league", season="2023-24")
    }
    assert (table["Everton"]["points"], table["Everton"]["points_adjustment"]) == (40, -8)
    assert (
        table["Nottingham Forest"]["points"],
        table["Nottingham Forest"]["points_adjustment"],
    ) == (32, -4)


def test_head_to_head_rule_is_applied_only_after_complete_pairing() -> None:
    rows = pd.DataFrame(
        [
            {
                "home_team": "A",
                "away_team": "B",
                "home_score": 0,
                "away_score": 2,
                "is_complete": True,
            },
            {
                "home_team": "B",
                "away_team": "A",
                "home_score": 0,
                "away_score": 1,
                "is_complete": True,
            },
            {
                "home_team": "A",
                "away_team": "C",
                "home_score": 5,
                "away_score": 0,
                "is_complete": True,
            },
            {
                "home_team": "C",
                "away_team": "A",
                "home_score": 0,
                "away_score": 1,
                "is_complete": True,
            },
            {
                "home_team": "B",
                "away_team": "C",
                "home_score": 1,
                "away_score": 0,
                "is_complete": True,
            },
            {
                "home_team": "C",
                "away_team": "B",
                "home_score": 0,
                "away_score": 1,
                "is_complete": True,
            },
        ]
    )
    table = standings_table(rows, "spain-la-liga")
    # A and B have nine points; their complete head-to-head puts B first despite
    # A's much stronger overall goal difference.
    assert [row["team"] for row in table[:2]] == ["B", "A"]


def test_unknown_competition_fails_closed() -> None:
    with pytest.raises(ValueError, match="no verified standings rule"):
        standings_table(pd.DataFrame(), "uefa-champions-league")
