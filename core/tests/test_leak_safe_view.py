"""The one leak-safe training view: cutoff, scoping, self-exclusion, guard.

These pin the invariant the whole app rests on — no data at or after a fixture's
kickoff may train that fixture's forecast — at the single interface that now owns
it. Before this module the cutoff was derived in four places and the source
scoping was duplicated verbatim between the server's analysis path and the core
retrospective, kept in agreement by a comment. Each test below is one of the ways
that duplication could silently drift.
"""

from __future__ import annotations

import pandas as pd
import pytest
from golavo_core.ingest import NoKickoffAnchor, leak_safe_training_view


def _row(
    mid: str,
    day: str,
    home: str,
    away: str,
    *,
    source_id: str = "martj42-international-results",
    source_kind: str = "international",
    competition: str = "Friendly",
    complete: bool = True,
) -> dict:
    stamp = pd.Timestamp(day, tz="UTC")
    return {
        "match_id": mid,
        "date": stamp,
        "kickoff_utc": stamp,
        "home_team": home,
        "away_team": away,
        "home_score": 1 if complete else None,
        "away_score": 0 if complete else None,
        "is_complete": complete,
        "neutral": False,
        "competition": competition,
        "source_id": source_id,
        "source_kind": source_kind,
    }


def _fixture(**overrides) -> dict:
    row = {
        "match_id": "m_target",
        "kickoff_utc": pd.Timestamp("2026-06-20T12:00:00Z"),
        "home_team": "France",
        "away_team": "Spain",
        "is_complete": True,
        "neutral": True,
        "competition": "FIFA World Cup",
        "source_id": "martj42-international-results",
        "source_kind": "international",
    }
    row.update(overrides)
    return row


def _history() -> list[dict]:
    return [
        _row("m_h1", "2026-06-01", "France", "Spain"),
        _row("m_h2", "2026-06-02", "Spain", "France"),
    ]


def test_cutoff_is_one_second_before_kickoff() -> None:
    frame = pd.DataFrame(_history())

    view = leak_safe_training_view(frame, _fixture())

    assert view.cutoff_utc == "2026-06-20T11:59:59Z"


def test_excludes_the_fixtures_own_row() -> None:
    """Belt-and-braces: a malformed snapshot dating the fixture before its own
    kickoff must never let the match train its own forecast."""
    poisoned = _row("m_target", "2026-06-01", "France", "Spain")
    frame = pd.DataFrame([*_history(), poisoned])

    view = leak_safe_training_view(frame, _fixture())

    assert "m_target" not in set(view.rows["match_id"].astype("string"))


def test_excludes_rows_at_or_after_the_cutoff() -> None:
    frame = pd.DataFrame([*_history(), _row("m_future", "2026-07-01", "France", "Spain")])

    view = leak_safe_training_view(frame, _fixture())

    assert "m_future" not in set(view.rows["match_id"].astype("string"))


def test_scopes_to_the_fixtures_own_source_id() -> None:
    """The scoping half of the invariant, previously duplicated between
    server/golavo_server/analysis.py and core/golavo_core/retrospective.py.

    A second international source sharing team strings must never merge into a
    fixture's training history.
    """
    other = _row("m_other", "2026-06-03", "France", "Spain", source_id="another-source")
    frame = pd.DataFrame([*_history(), other])

    view = leak_safe_training_view(frame, _fixture())

    assert "m_other" not in set(view.rows["match_id"].astype("string"))
    assert set(view.rows["match_id"].astype("string")) == {"m_h1", "m_h2"}


def test_club_fixtures_are_also_scoped_to_their_own_competition() -> None:
    same_source_other_competition = _row(
        "m_cup",
        "2026-06-03",
        "Aland",
        "Borda",
        source_id="openfootball-football-json",
        source_kind="club",
        competition="Some Cup",
    )
    league = _row(
        "m_league",
        "2026-06-04",
        "Aland",
        "Borda",
        source_id="openfootball-football-json",
        source_kind="club",
        competition="Test League",
    )
    frame = pd.DataFrame([same_source_other_competition, league])

    view = leak_safe_training_view(
        frame,
        _fixture(
            source_id="openfootball-football-json",
            source_kind="club",
            competition="Test League",
        ),
    )

    assert set(view.rows["match_id"].astype("string")) == {"m_league"}


def test_international_fixtures_are_not_scoped_by_competition() -> None:
    """An international fixture trains on the source's whole history — a World Cup
    forecast may learn from friendlies. Scoping by competition here would starve
    every tournament fit."""
    friendly = _row("m_friendly", "2026-06-03", "France", "Spain", competition="Friendly")
    frame = pd.DataFrame([*_history(), friendly])

    view = leak_safe_training_view(frame, _fixture(competition="FIFA World Cup"))

    assert "m_friendly" in set(view.rows["match_id"].astype("string"))


def test_frame_without_source_columns_is_not_scoped() -> None:
    bare = [
        {k: v for k, v in row.items() if k not in ("source_id", "source_kind")}
        for row in _history()
    ]
    frame = pd.DataFrame(bare)

    view = leak_safe_training_view(frame, _fixture(source_id=None, source_kind=None))

    assert set(view.rows["match_id"].astype("string")) == {"m_h1", "m_h2"}


def test_missing_kickoff_raises_no_kickoff_anchor() -> None:
    frame = pd.DataFrame(_history())

    with pytest.raises(NoKickoffAnchor):
        leak_safe_training_view(frame, _fixture(kickoff_utc=None))


def test_nat_kickoff_raises_no_kickoff_anchor() -> None:
    frame = pd.DataFrame(_history())

    with pytest.raises(NoKickoffAnchor):
        leak_safe_training_view(frame, _fixture(kickoff_utc=pd.NaT))


def test_as_of_before_kickoff_tightens_the_cutoff() -> None:
    """The seal path's rule: a forward seal may know less than kickoff-1s, never
    more. min(as_of, kickoff-1s) is the one cutoff, owned here."""
    frame = pd.DataFrame(_history())

    view = leak_safe_training_view(
        frame, _fixture(), as_of_utc="2026-06-01T00:00:00Z"
    )

    assert view.cutoff_utc == "2026-06-01T00:00:00Z"
    assert set(view.rows["match_id"].astype("string")) == {"m_h1"}


def test_as_of_after_kickoff_never_loosens_the_cutoff() -> None:
    frame = pd.DataFrame(_history())

    view = leak_safe_training_view(
        frame, _fixture(), as_of_utc="2026-07-01T00:00:00Z"
    )

    assert view.cutoff_utc == "2026-06-20T11:59:59Z"


def test_kickoff_is_carried_for_callers_that_need_the_instant() -> None:
    frame = pd.DataFrame(_history())

    view = leak_safe_training_view(frame, _fixture())

    assert view.kickoff_utc == pd.Timestamp("2026-06-20T12:00:00Z")
