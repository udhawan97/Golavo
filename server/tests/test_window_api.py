"""Tests for GET /api/v1/matches/window — the Matchday home's results-first feed.

Anchor semantics: week/month bound to the freshest COMPLETED kickoff in the
index, so a stale bundled snapshot degrades to "the most recent week of results"
rather than an empty page. Upcoming stays calendar-relative and is honestly empty.
"""

from __future__ import annotations

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from golavo_server import main as server_main
from golavo_server import matches

COLUMNS = [
    "match_id", "date", "kickoff_utc", "home_team", "away_team", "home_norm",
    "away_norm", "home_score", "away_score", "is_complete", "tournament",
    "competition", "city", "country", "neutral", "source_id", "source_kind",
]
_CLUB = "openfootball-football-json"
_INTL = "martj42-international-results"


def _row(mid, date, comp, source_id, source_kind, *, complete=True, hs=1, aws=0):
    return {
        "match_id": mid, "date": date, "kickoff_utc": f"{date}T00:00:00Z",
        "home_team": f"H{mid}", "away_team": f"A{mid}", "home_norm": f"h{mid}",
        "away_norm": f"a{mid}", "home_score": hs if complete else None,
        "away_score": aws if complete else None, "is_complete": complete,
        "tournament": comp, "competition": comp, "city": "City", "country": "Country",
        "neutral": False, "source_id": source_id, "source_kind": source_kind,
    }


# Freshest completed result is 2024-06-10. A cluster within the 7 days ending
# there, an older completed row (outside week, inside month), and a far-future
# upcoming fixture.
_ROWS = [
    _row("m_wc1", "2024-06-10", "FIFA World Cup", _INTL, "international"),
    _row("m_wc2", "2024-06-08", "FIFA World Cup", _INTL, "international"),
    _row("m_ll1", "2024-06-05", "La Liga", _CLUB, "club"),
    _row("m_old", "2024-05-20", "Serie A", _CLUB, "club"),        # inside month, outside week
    _row("m_ancient", "2024-01-01", "Ligue 1", _CLUB, "club"),    # outside both
    _row("m_up", "2030-01-01", "Asian Cup", _INTL, "international", complete=False),
]


def _build_index(path) -> None:
    df = pd.DataFrame(_ROWS)
    df["date"] = pd.to_datetime(df["date"])
    df["kickoff_utc"] = pd.to_datetime(df["kickoff_utc"], utc=True)
    df["home_score"] = pd.array(list(df["home_score"]), dtype="Int16")
    df["away_score"] = pd.array(list(df["away_score"]), dtype="Int16")
    df["is_complete"] = df["is_complete"].astype(bool)
    df["neutral"] = pd.array(list(df["neutral"]), dtype="boolean")
    for col in ("match_id", "home_team", "away_team", "home_norm", "away_norm",
                "tournament", "competition", "city", "country", "source_id", "source_kind"):
        df[col] = df[col].astype("string")
    df[COLUMNS].to_parquet(path)


@pytest.fixture(autouse=True)
def _reset_cache():
    matches.reset_cache()
    yield
    matches.reset_cache()


@pytest.fixture
def client(tmp_path, monkeypatch):
    index_path = tmp_path / "matches_index.parquet"
    _build_index(index_path)
    monkeypatch.setattr(matches, "INDEX_PATH", index_path)
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    monkeypatch.setattr(server_main, "ARTIFACT_DIR", ledger)
    return TestClient(server_main.app)


def _ids(body):
    return [m["match_id"] for m in body["matches"]]


def test_week_is_anchored_to_the_freshest_result(client) -> None:
    body = client.get("/api/v1/matches/window?window=week").json()
    # 7 days ending 2024-06-10 -> 06-04..06-10 inclusive: wc1, wc2, ll1 (not m_old).
    assert set(_ids(body)) == {"m_wc1", "m_wc2", "m_ll1"}
    assert body["latest_result_utc"].startswith("2024-06-10")
    assert body["window_end_utc"].startswith("2024-06-10")
    assert body["window_start_utc"].startswith("2024-06-04")
    # Newest first.
    assert _ids(body)[0] == "m_wc1"


def test_month_widens_the_window(client) -> None:
    body = client.get("/api/v1/matches/window?window=month").json()
    # 30 days ending 06-10 -> back to 05-12: adds m_old (05-20), still excludes ancient.
    assert set(_ids(body)) == {"m_wc1", "m_wc2", "m_ll1", "m_old"}


def test_upcoming_is_calendar_relative(client) -> None:
    body = client.get("/api/v1/matches/window?window=upcoming").json()
    assert _ids(body) == ["m_up"]
    assert body["window_end_utc"] is None
    # latest_result is still reported so the UI can show a staleness note.
    assert body["latest_result_utc"].startswith("2024-06-10")


def test_competition_counts_are_computed_before_truncation(client) -> None:
    body = client.get("/api/v1/matches/window?window=week&limit=1").json()
    assert len(body["matches"]) == 1          # page truncated
    assert body["total"] == 3                 # but total is the full window
    counts = {c["competition"]: c["n_matches"] for c in body["competitions"]}
    assert counts == {"FIFA World Cup": 2, "La Liga": 1}


def test_invalid_window_is_422(client) -> None:
    assert client.get("/api/v1/matches/window?window=year").status_code == 422


def test_empty_index_yields_null_anchor_and_empty_arrays(tmp_path, monkeypatch) -> None:
    # An index with no completed rows: week/month anchor is null, arrays empty.
    only_upcoming = [_row("m_up", "2030-01-01", "Asian Cup", _INTL, "international", complete=False)]
    df = pd.DataFrame(only_upcoming)
    df["date"] = pd.to_datetime(df["date"])
    df["kickoff_utc"] = pd.to_datetime(df["kickoff_utc"], utc=True)
    df["home_score"] = pd.array([None], dtype="Int16")
    df["away_score"] = pd.array([None], dtype="Int16")
    df["is_complete"] = df["is_complete"].astype(bool)
    df["neutral"] = pd.array([False], dtype="boolean")
    for col in ("match_id", "home_team", "away_team", "home_norm", "away_norm",
                "tournament", "competition", "city", "country", "source_id", "source_kind"):
        df[col] = df[col].astype("string")
    path = tmp_path / "matches_index.parquet"
    df[COLUMNS].to_parquet(path)
    monkeypatch.setattr(matches, "INDEX_PATH", path)
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    monkeypatch.setattr(server_main, "ARTIFACT_DIR", ledger)
    client = TestClient(server_main.app)

    body = client.get("/api/v1/matches/window?window=week").json()
    assert body["matches"] == []
    assert body["latest_result_utc"] is None
    assert body["window_start_utc"] is None
    # Upcoming still finds the forward fixture.
    assert _ids(client.get("/api/v1/matches/window?window=upcoming").json()) == ["m_up"]


def test_recent_endpoint_is_unchanged(client) -> None:
    # Regression: the windowed route must not disturb /matches/recent's envelope.
    body = client.get("/api/v1/matches/recent").json()
    assert set(body.keys()) == {"schema_version", "upcoming", "recent"}
    assert body["upcoming"][0]["match_id"] == "m_up"
