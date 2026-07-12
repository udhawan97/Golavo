"""The opt-in fixture-freshness check: report only genuinely-new upcoming games."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from golavo_server import fixtures, matches
from golavo_server import main as server_main

_NOW = datetime(2026, 7, 12, 10, 0, tzinfo=UTC)
# Norway-England 07-11 (proxy passed), Spain-Brazil 07-19 (upcoming, no score),
# France-Argentina 07-19 (already played).
_CSV = """date,home_team,away_team,home_score,away_score,tournament,city,country,neutral
2026-07-11,Norway,England,NA,NA,FIFA World Cup,Miami,United States,TRUE
2026-07-19,Spain,Brazil,NA,NA,FIFA World Cup,East Rutherford,United States,TRUE
2026-07-19,France,Argentina,3,1,FIFA World Cup,East Rutherford,United States,TRUE"""


def _index(*rows: dict) -> pd.DataFrame:
    cols = ["date", "home_norm", "away_norm"]
    return pd.DataFrame(list(rows), columns=cols) if rows else pd.DataFrame(columns=cols)


def test_reports_only_upcoming_fixtures_not_in_the_index() -> None:
    frame = _index({"date": pd.Timestamp("2020-01-01"), "home_norm": "foo", "away_norm": "bar"})
    result = fixtures.check_new_fixtures(frame, _NOW, fetch=lambda: ("abc123def456", _CSV))
    assert [(f["home_team"], f["away_team"]) for f in result["new_fixtures"]] == [
        ("Spain", "Brazil")
    ]
    assert result["source_ref"] == "abc123def456"


def test_excludes_a_fixture_already_in_the_index() -> None:
    frame = _index(
        {"date": pd.Timestamp("2026-07-19"), "home_norm": "spain", "away_norm": "brazil"}
    )
    result = fixtures.check_new_fixtures(frame, _NOW, fetch=lambda: ("r", _CSV))
    assert result["new_fixtures"] == []


def test_check_endpoint_reports_new_fixtures(monkeypatch) -> None:
    monkeypatch.setattr(matches, "_load_index", lambda: _index())
    monkeypatch.setattr(fixtures, "_fetch_latest", lambda: ("ref9", _CSV))
    body = TestClient(server_main.app).get("/api/v1/fixtures/check").json()
    assert {(f["home_team"], f["away_team"]) for f in body["new_fixtures"]} == {("Spain", "Brazil")}


def test_check_endpoint_503_when_source_unreachable(monkeypatch) -> None:
    monkeypatch.setattr(matches, "_load_index", lambda: _index())

    def _boom() -> tuple[str, str]:
        raise fixtures.FixtureCheckError("offline")

    monkeypatch.setattr(fixtures, "_fetch_latest", _boom)
    resp = TestClient(server_main.app).get("/api/v1/fixtures/check")
    assert resp.status_code == 503
    assert resp.json()["detail"]["reason_code"] == "fixture_source_unreachable"


# --- A7: malformed-but-200 upstream must 503, never 500 ----------------------


def test_fetch_latest_raises_fixture_check_error_on_bad_shape(monkeypatch) -> None:
    # A 200 whose JSON is the wrong shape (here a list, so ``["sha"]`` TypeErrors)
    # must become a typed FixtureCheckError, not a raw KeyError/TypeError.
    monkeypatch.setattr(fixtures, "_fetch", lambda url: b"[]")
    with pytest.raises(fixtures.FixtureCheckError, match="unexpected upstream response"):
        fixtures._fetch_latest()


def test_check_endpoint_503_on_malformed_upstream_200(monkeypatch) -> None:
    # A 200 whose JSON lacks "sha" used to raise KeyError -> an uncaught 500; the
    # shape guard now turns it into the same honest 503 as an unreachable source.
    monkeypatch.setattr(matches, "_load_index", lambda: _index())
    monkeypatch.setattr(fixtures, "_fetch", lambda url: b'{"message": "unexpected"}')
    resp = TestClient(server_main.app).get("/api/v1/fixtures/check")
    assert resp.status_code == 503
    assert resp.json()["detail"]["reason_code"] == "fixture_source_unreachable"
    assert resp.json()["detail"]["message"] == "unexpected upstream response"


# --- A8: vectorized index diff still filters correctly (incl. null dates) -----


def test_null_date_row_does_not_crash_the_vectorized_diff() -> None:
    # The old iterrows path guarded ``row["date"] is not None``; the vectorized
    # diff must likewise tolerate a missing date (coerced to "") while still
    # excluding a genuinely-present fixture.
    frame = _index(
        {"date": None, "home_norm": "ghost", "away_norm": "team"},
        {"date": pd.Timestamp("2026-07-19"), "home_norm": "spain", "away_norm": "brazil"},
    )
    result = fixtures.check_new_fixtures(frame, _NOW, fetch=lambda: ("r", _CSV))
    assert result["new_fixtures"] == []
