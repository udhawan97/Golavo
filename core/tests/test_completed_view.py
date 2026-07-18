"""The read path's cutoff, owned once — the companion to test_leak_safe_view.

Fitting a forecast goes through ``leak_safe_training_view``. Reading a board —
Golavo Ratings, the Golden Boot, competition analytics — used to derive its own
"completed at this instant" filter, and the three copies disagreed: one cut on
the raw kickoff column (dropping rows whose kickoff was blank), one cut on the
calendar day (shipped as the bug fixed in 7b5f2d8), one filled a missing
kickoff from the date. These tests pin the one rule every board now shares.
"""

from __future__ import annotations

import pandas as pd
import pytest
from golavo_core.ingest.snapshot import (
    ORDER_INSTANT,
    completed_view,
    leak_safe_cutoff,
    order_instants,
)


def _frame(rows: list[dict[str, object]]) -> pd.DataFrame:
    return pd.DataFrame(rows)


class TestLeakSafeCutoff:
    def test_is_one_second_before_kickoff(self) -> None:
        assert leak_safe_cutoff("2026-06-11T18:00:00Z") == pd.Timestamp("2026-06-11T17:59:59Z")

    def test_naive_input_is_read_as_utc(self) -> None:
        assert leak_safe_cutoff("2026-06-11 18:00:00") == pd.Timestamp("2026-06-11T17:59:59Z")


class TestOrderInstants:
    def test_prefers_the_exact_kickoff_over_the_calendar_day(self) -> None:
        frame = _frame([{"date": "2026-06-11", "kickoff_utc": "2026-06-11T20:00:00Z"}])
        assert order_instants(frame).iloc[0] == pd.Timestamp("2026-06-11T20:00:00Z")

    def test_falls_back_to_the_date_when_a_kickoff_is_missing(self) -> None:
        """analytics dropped these rows; the fit path always kept them."""
        frame = _frame(
            [
                {"date": "2026-06-11", "kickoff_utc": None},
                {"date": "2026-06-12", "kickoff_utc": "2026-06-12T20:00:00Z"},
            ]
        )
        assert list(order_instants(frame)) == [
            pd.Timestamp("2026-06-11T00:00:00Z"),
            pd.Timestamp("2026-06-12T20:00:00Z"),
        ]

    def test_uses_the_date_when_there_is_no_kickoff_column(self) -> None:
        frame = _frame([{"date": "2026-06-11"}])
        assert order_instants(frame).iloc[0] == pd.Timestamp("2026-06-11T00:00:00Z")


class TestCompletedView:
    @pytest.fixture
    def frame(self) -> pd.DataFrame:
        return _frame(
            [
                {
                    "match_id": "m_before",
                    "date": "2026-06-11",
                    "kickoff_utc": "2026-06-11T12:00:00Z",
                    "is_complete": True,
                },
                {
                    "match_id": "m_later_same_day",
                    "date": "2026-06-11",
                    "kickoff_utc": "2026-06-11T21:00:00Z",
                    "is_complete": True,
                },
                {
                    "match_id": "m_incomplete",
                    "date": "2026-06-10",
                    "kickoff_utc": "2026-06-10T12:00:00Z",
                    "is_complete": False,
                },
            ]
        )

    def test_keeps_only_completed_matches(self, frame: pd.DataFrame) -> None:
        view = completed_view(frame, as_of_utc="2026-06-30T00:00:00Z")
        assert "m_incomplete" not in set(view.rows["match_id"])

    def test_cuts_on_the_kickoff_instant_not_the_calendar_day(self, frame: pd.DataFrame) -> None:
        """The 7b5f2d8 regression: a 21:00 kickoff has not happened at 18:00."""
        view = completed_view(frame, as_of_utc="2026-06-11T18:00:00Z")
        assert set(view.rows["match_id"]) == {"m_before"}

    def test_a_row_exactly_on_the_cutoff_is_included(self, frame: pd.DataFrame) -> None:
        view = completed_view(frame, as_of_utc="2026-06-11T12:00:00Z")
        assert set(view.rows["match_id"]) == {"m_before"}

    def test_attaches_the_ordering_instant(self, frame: pd.DataFrame) -> None:
        view = completed_view(frame, as_of_utc="2026-06-30T00:00:00Z")
        assert view.rows[ORDER_INSTANT].max() == pd.Timestamp("2026-06-11T21:00:00Z")

    def test_reports_the_cutoff_it_applied(self, frame: pd.DataFrame) -> None:
        view = completed_view(frame, as_of_utc="2026-06-11T18:00:00Z")
        assert view.cutoff_utc == pd.Timestamp("2026-06-11T18:00:00Z")
        assert view.as_of_iso == "2026-06-11T18:00:00Z"

    def test_demands_an_explicit_cutoff(self, frame: pd.DataFrame) -> None:
        """No board may quietly read "everything"."""
        with pytest.raises(ValueError):
            completed_view(frame, as_of_utc=None)

    def test_an_empty_frame_stays_empty(self) -> None:
        empty = _frame([]).reindex(columns=["match_id", "date", "kickoff_utc", "is_complete"])
        view = completed_view(empty, as_of_utc="2026-06-11T18:00:00Z")
        assert view.rows.empty

    def test_does_not_mutate_the_caller_frame(self, frame: pd.DataFrame) -> None:
        completed_view(frame, as_of_utc="2026-06-30T00:00:00Z")
        assert ORDER_INSTANT not in frame.columns

    def test_agrees_with_the_fit_path_on_the_same_cutoff(self, frame: pd.DataFrame) -> None:
        """A board read at kickoff-1s sees exactly what the seal trained on."""
        from golavo_core.ingest.snapshot import training_rows

        cutoff = leak_safe_cutoff("2026-06-11T21:00:00Z")
        read = completed_view(frame, as_of_utc=cutoff)
        fit = training_rows(frame, cutoff)
        assert set(read.rows["match_id"]) == set(fit["match_id"])
