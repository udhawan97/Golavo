"""Leak-safe competition scorer and shootout boards over the vendored side tables.

The boards join the internationals goalscorers/shootouts side tables to the match
index, scoped to one competition and cut off at an instant, so nothing later than
the cutoff can appear. Own goals never credit the scorer, and the ordering is
deterministic so the committed answer is reproducible.
"""

from __future__ import annotations

import pandas as pd
import pytest
from golavo_core.scorers import competition_shootout_ledger, competition_top_scorers


def _index(rows: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    frame["date"] = pd.to_datetime(frame["date"])
    frame["kickoff_utc"] = pd.to_datetime(frame["kickoff_utc"], utc=True)
    frame["home_norm"] = frame["home_team"].str.casefold()
    frame["away_norm"] = frame["away_team"].str.casefold()
    if "is_complete" not in frame:
        frame["is_complete"] = True
    return frame


def _goals(rows: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(
        rows,
        columns=[
            "date",
            "home_team",
            "away_team",
            "team",
            "scorer",
            "minute",
            "own_goal",
            "penalty",
        ],
    )
    frame["date"] = pd.to_datetime(frame["date"])
    frame["own_goal"] = frame["own_goal"].astype(bool)
    frame["penalty"] = frame["penalty"].astype(bool)
    return frame


WC = "FIFA World Cup"


def _match(date: str, home: str, away: str, competition: str = WC) -> dict:
    return {
        "date": date,
        "kickoff_utc": f"{date}T18:00:00Z",
        "home_team": home,
        "away_team": away,
        "competition": competition,
        "is_complete": True,
    }


def _goal(
    date: str, home: str, away: str, team: str, scorer: str, *, own: bool = False, pen: bool = False
) -> dict:
    return {
        "date": date,
        "home_team": home,
        "away_team": away,
        "team": team,
        "scorer": scorer,
        "minute": "50",
        "own_goal": own,
        "penalty": pen,
    }


def test_board_ranks_by_goals_with_a_deterministic_tiebreak() -> None:
    index = _index(
        [_match("2026-06-01", "Brazil", "Spain"), _match("2026-06-05", "Brazil", "France")]
    )
    goals = _goals(
        [
            _goal("2026-06-01", "Brazil", "Spain", "Brazil", "Vinícius"),
            _goal("2026-06-01", "Brazil", "Spain", "Brazil", "Vinícius"),
            _goal("2026-06-05", "Brazil", "France", "Brazil", "Rodrygo"),
            _goal("2026-06-05", "Brazil", "France", "France", "Mbappé"),
        ]
    )
    board = competition_top_scorers(index, goals, competition=WC, as_of_utc="2026-07-01T00:00:00Z")

    names = [(row["scorer"], row["goals"], row["rank"]) for row in board["scorers"]]
    assert names == [("Vinícius", 2, 1), ("Mbappé", 1, 2), ("Rodrygo", 1, 2)]
    assert board["matches_counted"] == 2
    assert board["scorers"][0]["team"] == "Brazil"


def test_a_goal_after_the_cutoff_is_never_counted() -> None:
    index = _index(
        [_match("2026-06-01", "Brazil", "Spain"), _match("2026-07-19", "Brazil", "Argentina")]
    )
    goals = _goals(
        [
            _goal("2026-06-01", "Brazil", "Spain", "Brazil", "Rodrygo"),
            _goal("2026-07-19", "Brazil", "Argentina", "Brazil", "Rodrygo"),
        ]
    )
    board = competition_top_scorers(index, goals, competition=WC, as_of_utc="2026-07-01T00:00:00Z")

    assert [(row["scorer"], row["goals"]) for row in board["scorers"]] == [("Rodrygo", 1)]
    assert board["matches_counted"] == 1


def test_own_goals_never_credit_the_scorer_but_penalties_are_tallied() -> None:
    index = _index([_match("2026-06-01", "Brazil", "Spain")])
    goals = _goals(
        [
            _goal("2026-06-01", "Brazil", "Spain", "Brazil", "Marquinhos", own=True),
            _goal("2026-06-01", "Brazil", "Spain", "Brazil", "Neymar", pen=True),
            _goal("2026-06-01", "Brazil", "Spain", "Brazil", "Neymar"),
        ]
    )
    board = competition_top_scorers(index, goals, competition=WC, as_of_utc="2026-07-01T00:00:00Z")

    scorers = {row["scorer"]: row for row in board["scorers"]}
    assert "Marquinhos" not in scorers
    assert scorers["Neymar"]["goals"] == 2
    assert scorers["Neymar"]["penalties"] == 1


def test_only_the_target_competition_is_counted() -> None:
    index = _index(
        [
            _match("2026-06-01", "Brazil", "Spain", competition=WC),
            _match("2026-03-01", "Brazil", "Chile", competition="Copa América"),
        ]
    )
    goals = _goals(
        [
            _goal("2026-06-01", "Brazil", "Spain", "Brazil", "Raphinha"),
            _goal("2026-03-01", "Brazil", "Chile", "Brazil", "Raphinha"),
        ]
    )
    board = competition_top_scorers(index, goals, competition=WC, as_of_utc="2026-07-01T00:00:00Z")

    assert [(row["scorer"], row["goals"]) for row in board["scorers"]] == [("Raphinha", 1)]


def test_min_goals_hides_the_long_tail_of_single_scorers() -> None:
    index = _index([_match("2026-06-01", "Brazil", "Spain")])
    goals = _goals(
        [
            _goal("2026-06-01", "Brazil", "Spain", "Brazil", "Vinícius"),
            _goal("2026-06-01", "Brazil", "Spain", "Brazil", "Vinícius"),
            _goal("2026-06-01", "Brazil", "Spain", "Spain", "Oyarzabal"),
        ]
    )
    board = competition_top_scorers(
        index, goals, competition=WC, as_of_utc="2026-07-01T00:00:00Z", min_goals=2
    )

    assert [row["scorer"] for row in board["scorers"]] == ["Vinícius"]


def test_a_competition_with_no_scorer_data_returns_an_honest_empty_board() -> None:
    index = _index([_match("2026-06-01", "Brazil", "Spain")])
    goals = _goals([])
    board = competition_top_scorers(index, goals, competition=WC, as_of_utc="2026-07-01T00:00:00Z")

    assert board["scorers"] == []
    assert board["matches_counted"] == 0
    assert board["competition_names"] == [WC]


def test_shootout_ledger_counts_wins_and_losses_before_the_cutoff() -> None:
    index = _index(
        [
            _match("2026-06-20", "Brazil", "Spain"),
            _match("2026-06-25", "Brazil", "France"),
            _match("2026-07-19", "Brazil", "Argentina"),
        ]
    )
    shootouts = pd.DataFrame(
        [
            {
                "date": "2026-06-20",
                "home_team": "Brazil",
                "away_team": "Spain",
                "winner": "Brazil",
                "first_shooter": "Brazil",
            },
            {
                "date": "2026-06-25",
                "home_team": "Brazil",
                "away_team": "France",
                "winner": "France",
                "first_shooter": "Brazil",
            },
            {
                "date": "2026-07-19",
                "home_team": "Brazil",
                "away_team": "Argentina",
                "winner": "Brazil",
                "first_shooter": "Brazil",
            },
        ]
    )
    shootouts["date"] = pd.to_datetime(shootouts["date"])

    ledger = competition_shootout_ledger(
        index, shootouts, competition=WC, as_of_utc="2026-07-01T00:00:00Z"
    )

    teams = {row["team"]: row for row in ledger["teams"]}
    # The 2026-07-19 shootout is after the cutoff and must not appear.
    assert ledger["shootouts_counted"] == 2
    assert (teams["Brazil"]["won"], teams["Brazil"]["lost"]) == (1, 1)
    assert (teams["Spain"]["won"], teams["Spain"]["lost"]) == (0, 1)
    assert (teams["France"]["won"], teams["France"]["lost"]) == (1, 0)


def test_a_competition_may_be_addressed_by_several_source_names() -> None:
    # One catalog competition can map to more than one source competition string
    # (e.g. a tournament and its qualification), so the board accepts a set.
    index = _index(
        [
            _match("2026-06-01", "Brazil", "Spain", competition="UEFA Euro"),
            _match("2026-03-01", "Spain", "Malta", competition="UEFA Euro qualification"),
        ]
    )
    goals = _goals(
        [
            _goal("2026-06-01", "Brazil", "Spain", "Spain", "Morata"),
            _goal("2026-03-01", "Spain", "Malta", "Spain", "Morata"),
        ]
    )
    board = competition_top_scorers(
        index,
        goals,
        competition=["UEFA Euro", "UEFA Euro qualification"],
        as_of_utc="2026-07-01T00:00:00Z",
    )
    assert [(row["scorer"], row["goals"]) for row in board["scorers"]] == [("Morata", 2)]


def test_no_source_competition_names_is_an_honest_empty_board() -> None:
    index = _index([_match("2026-06-01", "Brazil", "Spain")])
    goals = _goals([_goal("2026-06-01", "Brazil", "Spain", "Brazil", "Rodrygo")])
    board = competition_top_scorers(index, goals, competition=[], as_of_utc="2026-07-01T00:00:00Z")
    assert board["scorers"] == []
    assert board["matches_counted"] == 0


def test_boards_reject_a_naive_cutoff() -> None:
    index = _index([_match("2026-06-01", "Brazil", "Spain")])
    with pytest.raises(ValueError, match="as_of_utc"):
        competition_top_scorers(index, _goals([]), competition=WC, as_of_utc=None)
