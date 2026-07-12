"""The opt-in fixture-freshness check: report only genuinely-new upcoming games."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
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
