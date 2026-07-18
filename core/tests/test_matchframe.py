"""Minting a match id, owned once for every source loader.

Each source keeps its OWN identity fields — martj42 needs the venue to separate
two same-day meetings, footballcsv prefixes its source id, football.txt adds the
season — and re-hashing a merged frame would silently corrupt them. What was
copy-pasted four times is the *mechanism* around those fields: stable sort, join
with a pipe, number repeat occurrences, hash to ``m_<sha256[:16]>``. A change to
any of it had to land in four files at once or the committed index would move.
"""

from __future__ import annotations

import hashlib

import pandas as pd
import pytest
from golavo_core.ingest.matchframe import (
    match_identities,
    mint_match_ids,
    with_day_precision_kickoff,
)


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-06-11", "2026-06-11"]),
            "home_team": ["Bayern", "Bayern"],
            "away_team": ["Köln", "Köln"],
            "tournament": ["Bundesliga", "Bundesliga"],
            "neutral": pd.array([False, True], dtype="boolean"),
            "home_score": pd.array([1, 2], dtype="Int16"),
            "away_score": pd.array([0, None], dtype="Int16"),
        }
    )


class TestMatchIdentities:
    def test_joins_the_named_columns_with_a_pipe(self) -> None:
        identities = match_identities(_frame(), ["date", "home_team", "away_team"])
        assert identities.iloc[0] == "2026-06-11|Bayern|Köln"

    def test_a_date_column_becomes_its_calendar_day(self) -> None:
        """Never the full timestamp — the identity is day-precision by design."""
        frame = _frame()
        frame["date"] = pd.to_datetime(["2026-06-11T18:00:00", "2026-06-11T20:00:00"])
        identities = match_identities(frame, ["date", "home_team"])
        assert list(identities) == ["2026-06-11|Bayern", "2026-06-11|Bayern"]

    def test_a_boolean_column_becomes_python_bool_text(self) -> None:
        identities = match_identities(_frame(), ["neutral"])
        assert list(identities) == ["False", "True"]

    def test_a_prefix_scopes_the_identity_to_its_source(self) -> None:
        identities = match_identities(_frame(), ["home_team"], prefix="footballcsv")
        assert identities.iloc[0] == "footballcsv|Bayern"

    def test_diacritics_are_kept_verbatim(self) -> None:
        """The id is not the search key: folding here would merge distinct clubs."""
        assert "Köln" in match_identities(_frame(), ["away_team"]).iloc[0]


class TestMintMatchIds:
    def test_inserts_match_id_as_the_first_column(self) -> None:
        minted = mint_match_ids(_frame(), ["date", "home_team", "away_team"])
        assert list(minted.columns)[0] == "match_id"

    def test_the_id_is_the_documented_hash_of_identity_and_occurrence(self) -> None:
        minted = mint_match_ids(_frame(), ["date", "home_team", "away_team"])
        expected = hashlib.sha256(b"2026-06-11|Bayern|K\xc3\xb6ln|0").hexdigest()[:16]
        assert minted["match_id"].iloc[0] == f"m_{expected}"

    def test_repeat_fixtures_are_separated_by_occurrence(self) -> None:
        """Two identical identities must not collapse to one id."""
        minted = mint_match_ids(_frame(), ["date", "home_team", "away_team"])
        assert minted["match_id"].nunique() == 2

    def test_occurrence_numbering_follows_frame_order(self) -> None:
        frame = _frame()
        minted_forward = mint_match_ids(frame, ["date", "home_team", "away_team"])
        minted_reversed = mint_match_ids(
            frame.iloc[::-1].reset_index(drop=True), ["date", "home_team", "away_team"]
        )
        assert list(minted_forward["match_id"]) == list(minted_reversed["match_id"])

    def test_the_caller_frame_is_not_mutated(self) -> None:
        frame = _frame()
        mint_match_ids(frame, ["date", "home_team"])
        assert "match_id" not in frame.columns

    def test_a_missing_identity_column_fails_loudly(self) -> None:
        with pytest.raises(KeyError):
            mint_match_ids(_frame(), ["date", "stadium"])


class TestDayPrecisionKickoff:
    def test_kickoff_is_the_dates_midnight_utc(self) -> None:
        """Upstream clocks are venue-local; calling one UTC would be a false instant."""
        result = with_day_precision_kickoff(_frame())
        assert result["kickoff_utc"].iloc[0] == pd.Timestamp("2026-06-11T00:00:00Z")

    def test_precision_is_declared_as_day(self) -> None:
        result = with_day_precision_kickoff(_frame())
        assert set(result["kickoff_precision"]) == {"day"}
        assert result["kickoff_precision"].dtype == "string"

    def test_completeness_needs_both_scores(self) -> None:
        result = with_day_precision_kickoff(_frame())
        assert list(result["is_complete"]) == [True, False]
