"""The fixture pack builder's provenance rows must describe the data, not assume it.

The builder runs again whenever the pinned bytes move, and upstream appends
scores to the same .txt file as matches are played. So its provenance must be
derived from each parsed row, never hardcoded to the state the season happened
to be in on the day it was first run.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.build_domestic_fixtures import _fetch, _provenance_rows  # noqa: E402
from scripts.packlib import PackBuildError  # noqa: E402


def test_fetch_pins_the_url_from_the_league_table() -> None:
    """The pinned commit and path reach the transport verbatim, no live GitHub."""
    seen: dict[str, object] = {}

    def transport(url: str, max_bytes: int) -> bytes:
        seen["url"] = url
        return b"Matchday 1\n"

    assert _fetch("england", "2026-27/1-premierleague.txt", "abc123", transport=transport) == (
        b"Matchday 1\n"
    )
    assert seen["url"] == (
        "https://raw.githubusercontent.com/openfootball/england/abc123/"
        "2026-27/1-premierleague.txt"
    )


def test_fetch_refuses_an_oversized_fixture_file() -> None:
    """A pinned path resolving to something huge must not be written into a pack."""

    def transport(url: str, max_bytes: int) -> bytes:
        return b"x" * (max_bytes + 1)

    with pytest.raises(PackBuildError, match="exceeds"):
        _fetch("england", "p.txt", "abc123", transport=transport)


def _frame(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows).assign(co_source_id="openfootball-england")


def test_unplayed_fixtures_claim_no_result_and_never_train() -> None:
    rows = _provenance_rows(
        _frame(
            [
                {
                    "date": pd.Timestamp("2026-08-21"),
                    "matchday": 1,
                    "home_team": "Arsenal",
                    "away_team": "Coventry City",
                    "is_complete": False,
                }
            ]
        )
    )
    assert rows[0]["result_source_id"] == ""
    assert rows[0]["training_source_id"] == ""
    assert rows[0]["training_eligible"] == "false"
    assert rows[0]["identity_source_id"] == "openfootball-england"
    assert rows[0]["kickoff_source_id"] == "openfootball-england"


def test_a_played_fixture_becomes_a_real_result_that_may_train() -> None:
    """Once upstream appends a score, the row is a genuine league result.

    Forcing training_eligible=false here would null training_source_id in the
    index and silently exclude real results from the models forever.
    """
    rows = _provenance_rows(
        _frame(
            [
                {
                    "date": pd.Timestamp("2026-08-21"),
                    "matchday": 1,
                    "home_team": "Arsenal",
                    "away_team": "Coventry City",
                    "is_complete": True,
                }
            ]
        )
    )
    assert rows[0]["result_source_id"] == "openfootball-england"
    assert rows[0]["training_source_id"] == "openfootball-england"
    assert rows[0]["training_eligible"] == "true"


def test_every_fixture_in_a_matchday_gets_its_own_upstream_key() -> None:
    """A matchday-wide key would let a correction resolve to the wrong match."""
    rows = _provenance_rows(
        _frame(
            [
                {
                    "date": pd.Timestamp("2026-08-21"),
                    "matchday": 1,
                    "home_team": "Arsenal",
                    "away_team": "Coventry City",
                    "is_complete": False,
                },
                {
                    "date": pd.Timestamp("2026-08-22"),
                    "matchday": 1,
                    "home_team": "Everton",
                    "away_team": "Fulham",
                    "is_complete": False,
                },
            ]
        )
    )
    keys = [row["upstream_fixture_key"] for row in rows]
    assert len(set(keys)) == len(keys), keys
    # The key stays legible and carries the matchday it came from.
    assert all(key.startswith("openfootball-england:2026-27:1:") for key in keys)
