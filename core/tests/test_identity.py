"""The one fold and the one fixture key, proven once for every caller.

Before this module existed the NFKD fold was copy-pasted into the index builder,
the search reader, result settlement, the fixture check and the World Cup
overlay, and the composite fixture key was rebuilt in five places from three
different date expressions. Settlement grades a sealed forecast only when two
sources agree on a fixture, so those copies agreeing was load-bearing and
enforced by nothing but a docstring. These tests pin the fold, the date
coercion and every key encoding to one interface.
"""

from __future__ import annotations

import pandas as pd
import pytest
from golavo_core.identity import (
    fixture_date,
    fixture_key,
    fixture_key_strings,
    fixture_keys,
    normalize,
)


class TestNormalize:
    def test_folds_diacritics_and_case(self) -> None:
        assert normalize("Atlético") == normalize("ATLETICO") == "atletico"

    def test_strips_surrounding_whitespace(self) -> None:
        assert normalize("  Bayern  ") == "bayern"

    def test_is_idempotent(self) -> None:
        """Callers pass already-folded index columns (``home_norm``) straight in."""
        once = normalize("Beşiktaş")
        assert normalize(once) == once

    def test_accepts_non_string_input(self) -> None:
        assert normalize(1860) == "1860"

    def test_keeps_distinct_clubs_distinct(self) -> None:
        assert normalize("1860 München") != normalize("München 1860")


class TestFixtureDate:
    @pytest.mark.parametrize(
        "value",
        [
            "2026-06-11",
            "2026-06-11T18:00:00Z",
            "2026-06-11 18:00:00+00:00",
            pd.Timestamp("2026-06-11T18:00:00Z"),
            pd.Timestamp("2026-06-11"),
        ],
    )
    def test_coerces_every_caller_shape_to_iso_day(self, value: object) -> None:
        assert fixture_date(value) == "2026-06-11"

    def test_iso_string_day_is_taken_verbatim(self) -> None:
        """A late-evening UTC kickoff keeps its own UTC day, never a local one."""
        assert fixture_date("2026-06-11T23:30:00Z") == "2026-06-11"

    def test_rejects_an_unparseable_date(self) -> None:
        with pytest.raises(ValueError):
            fixture_date("not a date")


class TestFixtureKey:
    def test_folds_the_team_names(self) -> None:
        assert fixture_key("2026-06-11", "Atlético", "Bayern") == (
            "2026-06-11",
            "atletico",
            "bayern",
        )

    def test_coerces_the_date(self) -> None:
        assert fixture_key("2026-06-11T18:00:00Z", "A", "B")[0] == "2026-06-11"

    def test_scope_parts_are_folded_and_appended(self) -> None:
        assert fixture_key("2026-06-11", "A", "B", "Süper Lig") == (
            "2026-06-11",
            "a",
            "b",
            "super lig",
        )

    def test_a_prefolded_row_and_a_raw_upstream_row_agree(self) -> None:
        """The invariant settlement rests on: index columns and upstream spellings
        produce the same key, so a graded fixture cannot miss on diacritics."""
        from_index = fixture_key("2026-06-11", "atletico", "bayern")
        from_upstream = fixture_key("2026-06-11T18:00:00Z", "Atlético", "Bayern")
        assert from_index == from_upstream


class TestVectorisedKeys:
    @pytest.fixture
    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "date": ["2026-06-11", "2026-06-12"],
                "home_team": ["Atlético", "Bayern"],
                "away_team": ["Bayern", "Atlético"],
                "tournament": ["Friendly", "Friendly"],
            }
        )

    def test_tuple_encoding_matches_the_scalar_key(self, frame: pd.DataFrame) -> None:
        keys = fixture_keys(frame)
        assert list(keys) == [
            fixture_key("2026-06-11", "Atlético", "Bayern"),
            fixture_key("2026-06-12", "Bayern", "Atlético"),
        ]

    def test_string_encoding_is_the_pipe_joined_tuple(self, frame: pd.DataFrame) -> None:
        assert list(fixture_key_strings(frame)) == [
            "2026-06-11|atletico|bayern",
            "2026-06-12|bayern|atletico",
        ]

    def test_scope_columns_extend_both_encodings(self, frame: pd.DataFrame) -> None:
        assert list(fixture_keys(frame, scope=("tournament",)))[0] == (
            "2026-06-11",
            "atletico",
            "bayern",
            "friendly",
        )
        assert list(fixture_key_strings(frame, scope=("tournament",)))[0] == (
            "2026-06-11|atletico|bayern|friendly"
        )

    def test_index_is_preserved_for_alignment(self, frame: pd.DataFrame) -> None:
        """Callers assign the result back onto a filtered frame."""
        subset = frame.iloc[[1]]
        assert list(fixture_keys(subset).index) == [1]
