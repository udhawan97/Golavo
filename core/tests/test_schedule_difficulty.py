"""Remaining-schedule difficulty, which exists only behind a fixture certificate.

The capability was declared blocked for as long as no competition had a proven
complete remaining-fixture list. The 2026-27 domestic schedules now certify, so
the number is computable — but the certificate stays the gate, because a
difficulty rating over a partial fixture list would silently rank teams on how
much of their schedule Golavo happens to hold.
"""

from __future__ import annotations

import pandas as pd
import pytest
from golavo_core.analytics import schedule_difficulty
from golavo_core.standings import LEAGUE_RULES, LeagueRule

COMPETITION = "english-test-league"
SOURCE_NAME = "English Premier League"


@pytest.fixture(autouse=True)
def compact_rule(monkeypatch: pytest.MonkeyPatch) -> None:
    """A four-team double round-robin under a real competition's source name."""
    monkeypatch.setitem(
        LEAGUE_RULES,
        COMPETITION,
        LeagueRule(
            COMPETITION,
            SOURCE_NAME,
            "test-2026.1",
            4,
            4,
            1,
            ("points", "goal_difference", "goals_for"),
        ),
    )


def _row(
    match_id: str,
    date: str,
    home: str,
    away: str,
    *,
    home_score: int | None = None,
    away_score: int | None = None,
) -> dict[str, object]:
    complete = home_score is not None and away_score is not None
    return {
        "match_id": match_id,
        "date": pd.Timestamp(date),
        "kickoff_utc": pd.Timestamp(date, tz="UTC"),
        "home_team": home,
        "away_team": away,
        "home_score": home_score,
        "away_score": away_score,
        "is_complete": complete,
        "neutral": False,
        "competition": SOURCE_NAME,
        "source_id": "openfootball-football-json",
        "source_kind": "club",
    }


TEAMS = ("Alpha", "Bravo", "Charlie", "Delta")


def _history() -> list[dict[str, object]]:
    """Prior seasons that make Alpha strong and Delta weak, in that order."""
    strength = {"Alpha": 4, "Bravo": 3, "Charlie": 2, "Delta": 1}
    rows: list[dict[str, object]] = []
    for cycle in range(6):
        for home in TEAMS:
            for away in TEAMS:
                if home == away:
                    continue
                rows.append(
                    _row(
                        f"history-{len(rows)}",
                        f"202{cycle}-03-{len(rows) % 27 + 1:02d}",
                        home,
                        away,
                        home_score=strength[home],
                        away_score=strength[away],
                    )
                )
    return rows


def _season(played: int = 0) -> list[dict[str, object]]:
    """The certified 12-fixture season; the first ``played`` are already results."""
    pairs = [(home, away) for home in TEAMS for away in TEAMS if home != away]
    rows: list[dict[str, object]] = []
    for index, (home, away) in enumerate(pairs):
        complete = index < played
        rows.append(
            _row(
                f"season-{index}",
                f"2026-08-{index + 1:02d}" if complete else f"2027-03-{index + 1:02d}",
                home,
                away,
                home_score=1 if complete else None,
                away_score=0 if complete else None,
            )
        )
    return rows


def _frame(rows: list[dict[str, object]]) -> pd.DataFrame:
    return pd.DataFrame(rows)


CUTOFF = "2026-09-01T00:00:00Z"


def test_difficulty_is_blocked_until_the_fixture_list_certifies() -> None:
    """A missing fixture must block the number, not quietly shrink a team's run-in."""
    rows = _history() + _season()[:-1]

    result = schedule_difficulty(_frame(rows), COMPETITION, as_of_utc=CUTOFF)

    assert result["status"] == "blocked"
    assert "certificate" in result["reason"].lower() or "complete" in result["reason"].lower()
    assert result["teams"] == []


def test_a_competition_with_no_verified_standings_rule_is_blocked() -> None:
    """No verified rule means no expected team count, so nothing can be certified."""
    result = schedule_difficulty(
        _frame(_history() + _season()), "uefa-champions-league", as_of_utc=CUTOFF
    )
    assert result["status"] == "blocked"
    assert "standings rule" in result["reason"].lower()


def test_every_team_is_rated_by_the_opponents_it_still_has_to_play() -> None:
    result = schedule_difficulty(_frame(_history() + _season()), COMPETITION, as_of_utc=CUTOFF)

    assert result["status"] == "available"
    assert {team["team"] for team in result["teams"]} == set(TEAMS)
    # A full double round-robin: each side has six fixtures left, three at home.
    assert all(team["matches_remaining"] == 6 for team in result["teams"])
    assert all(team["home_remaining"] == 3 for team in result["teams"])

    # Alpha won every prior meeting and Delta lost every one, so Delta's run-in —
    # which includes Alpha twice and never itself — is the hardest of the four.
    ranked = [team["team"] for team in result["teams"]]
    assert ranked[0] == "Delta"
    assert ranked[-1] == "Alpha"
    assert [team["rank"] for team in result["teams"]] == [1, 2, 3, 4]
    hardest, easiest = result["teams"][0], result["teams"][-1]
    assert hardest["mean_opponent_rating"] > easiest["mean_opponent_rating"]


def test_a_played_fixture_leaves_the_remaining_schedule() -> None:
    result = schedule_difficulty(
        _frame(_history() + _season(played=4)), COMPETITION, as_of_utc=CUTOFF
    )

    assert result["status"] == "available"
    assert sum(team["matches_remaining"] for team in result["teams"]) == 2 * (12 - 4)


def test_difficulty_never_reads_a_result_from_beyond_the_cutoff() -> None:
    """The rating driving it is a replay of the past; a later match cannot leak in.

    The leak is placed in a LATER season, not this one: a thirteenth fixture in
    the rated season would (rightly) fail the certificate, and the test would
    then pass for the wrong reason.
    """
    rows = _history() + _season()
    before = schedule_difficulty(_frame(rows), COMPETITION, as_of_utc=CUTOFF)

    leak = _row("leak", "2027-09-01", "Delta", "Alpha", home_score=9, away_score=0)
    after = schedule_difficulty(_frame([*rows, leak]), COMPETITION, as_of_utc=CUTOFF)

    assert before["status"] == "available"
    assert after["teams"] == before["teams"]
