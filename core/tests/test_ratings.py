"""Golavo Ratings — a leak-safe in-house Elo table for national teams.

These test the trajectory engine directly: it replays the same Elo update the
forecast model uses, over completed rows at or before a cutoff, and emits both a
current table and a monthly checkpoint history. The defining property is that a
rating as of some instant is fixed — appending later matches cannot change it.
"""

from __future__ import annotations

import pandas as pd
import pytest
from golavo_core.ratings import elo_trajectory


def _rows(rows: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    frame["date"] = pd.to_datetime(frame["date"])
    frame["kickoff_utc"] = pd.to_datetime(frame["date"], utc=True)
    frame["match_id"] = [f"m{i}" for i in range(len(frame))]
    frame["is_complete"] = True
    if "neutral" not in frame:
        frame["neutral"] = False
    return frame


def _match(date: str, home: str, away: str, hs: int, as_: int, *, neutral: bool = False) -> dict:
    return {
        "date": date,
        "home_team": home,
        "away_team": away,
        "home_score": hs,
        "away_score": as_,
        "neutral": neutral,
    }


def test_a_team_that_wins_rises_above_the_team_it_beat() -> None:
    rows = _rows(
        [
            _match("2026-01-10", "Spain", "Italy", 3, 0),
            _match("2026-02-10", "Spain", "France", 2, 1),
        ]
    )
    table = elo_trajectory(rows, as_of_utc="2026-07-01T00:00:00Z")

    ratings = {row["team"]: row["rating"] for row in table["teams"]}
    assert ratings["Spain"] > 1500.0
    assert ratings["Italy"] < 1500.0
    assert table["teams"][0]["team"] == "Spain"
    assert table["teams"][0]["rank"] == 1
    # Every team carries its own sample size and last-seen date.
    spain = next(row for row in table["teams"] if row["team"] == "Spain")
    assert spain["matches"] == 2
    assert spain["last_match_date"] == "2026-02-10"


def test_a_rating_as_of_an_instant_is_frozen_against_later_matches() -> None:
    early_rows = _rows([_match("2026-01-10", "Spain", "Italy", 1, 0)])
    later_rows = _rows(
        [
            _match("2026-01-10", "Spain", "Italy", 1, 0),
            _match("2026-09-01", "Italy", "Spain", 4, 0),
        ]
    )
    early = elo_trajectory(early_rows, as_of_utc="2026-03-01T00:00:00Z")
    # The same cutoff, but with a later thrashing appended to the data.
    later = elo_trajectory(later_rows, as_of_utc="2026-03-01T00:00:00Z")

    assert early["teams"] == later["teams"]


def test_only_completed_matches_before_the_cutoff_are_counted() -> None:
    rows = _rows(
        [
            _match("2026-01-10", "Spain", "Italy", 1, 0),
            _match("2026-08-01", "Spain", "Brazil", 5, 0),  # after the cutoff
        ]
    )
    rows.loc[rows["date"].eq(pd.Timestamp("2026-08-01")), "is_complete"] = True
    table = elo_trajectory(rows, as_of_utc="2026-03-01T00:00:00Z")

    teams = {row["team"] for row in table["teams"]}
    assert "Brazil" not in teams
    assert table["matches_counted"] == 1


def test_a_neutral_win_earns_more_than_the_same_win_at_home() -> None:
    home = elo_trajectory(
        _rows([_match("2026-01-10", "Spain", "Italy", 1, 0, neutral=False)]),
        as_of_utc="2026-07-01T00:00:00Z",
    )
    neutral = elo_trajectory(
        _rows([_match("2026-01-10", "Spain", "Italy", 1, 0, neutral=True)]),
        as_of_utc="2026-07-01T00:00:00Z",
    )
    home_gain = next(r["rating"] for r in home["teams"] if r["team"] == "Spain")
    neutral_gain = next(r["rating"] for r in neutral["teams"] if r["team"] == "Spain")
    # An expected home win is already priced in by the home advantage, so beating
    # the same opponent on neutral ground is the bigger surprise and bigger gain.
    assert neutral_gain > home_gain


def test_the_checkpoint_history_tracks_a_rising_team_over_time() -> None:
    rows = _rows(
        [
            _match("2026-01-10", "Spain", "Italy", 1, 0),
            _match("2026-03-10", "Spain", "Italy", 1, 0),
            _match("2026-05-10", "Spain", "Italy", 1, 0),
        ]
    )
    table = elo_trajectory(rows, as_of_utc="2026-06-01T00:00:00Z")

    spain = next(row for row in table["teams"] if row["team"] == "Spain")
    history = [point["rating"] for point in spain["history"]]
    assert len(history) >= 2
    # A team winning repeatedly climbs monotonically across the checkpoints.
    assert history == sorted(history)
    assert history[-1] == spain["rating"]


def test_the_engine_is_deterministic() -> None:
    rows = _rows(
        [
            _match("2026-01-10", "Spain", "Italy", 3, 1),
            _match("2026-02-10", "France", "Italy", 2, 2),
            _match("2026-03-10", "Spain", "France", 0, 1, neutral=True),
        ]
    )
    first = elo_trajectory(rows, as_of_utc="2026-07-01T00:00:00Z")
    second = elo_trajectory(rows, as_of_utc="2026-07-01T00:00:00Z")
    assert first == second


def test_the_table_is_labelled_as_an_estimate_not_the_official_ranking() -> None:
    rows = _rows([_match("2026-01-10", "Spain", "Italy", 1, 0)])
    table = elo_trajectory(rows, as_of_utc="2026-07-01T00:00:00Z")
    assert "not the FIFA" in table["label"] or "not an official" in table["label"].lower()
    assert table["method"].startswith("elo")


def test_a_naive_cutoff_is_rejected() -> None:
    rows = _rows([_match("2026-01-10", "Spain", "Italy", 1, 0)])
    with pytest.raises(ValueError, match="as_of"):
        elo_trajectory(rows, as_of_utc=None)
