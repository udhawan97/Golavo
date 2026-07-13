"""Tests for GET /api/v1/status — the UI's staged-splash warm-up hint.

The status handler must report the match-index warm state WITHOUT ever triggering
the (slow) index load itself, so it answers in microseconds even mid-warmup. It
also reads the row count from a small meta.json (no pandas), so it must be robust
to a missing/corrupt meta.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from golavo_server import main as server_main
from golavo_server import matches
from golavo_server import runtime

# The frozen index schema, verbatim (order matters for the parquet round-trip).
COLUMNS = [
    "match_id", "date", "kickoff_utc", "home_team", "away_team", "home_norm",
    "away_norm", "home_score", "away_score", "is_complete", "tournament",
    "competition", "city", "country", "neutral", "source_id", "source_kind",
]

# Two rows are enough to warm the index; the status surface never inspects them.
_ROWS = [
    {"match_id": "m1", "date": "2024-05-01", "kickoff_utc": "2024-05-01T00:00:00Z",
     "home_team": "Brazil", "away_team": "Chile", "home_norm": "brazil",
     "away_norm": "chile", "home_score": 2, "away_score": 0, "is_complete": True,
     "tournament": "Friendly", "competition": "Friendly", "city": "Rio",
     "country": "Brazil", "neutral": False, "source_id": "martj42-international-results",
     "source_kind": "international"},
    {"match_id": "m2", "date": "2024-05-05", "kickoff_utc": "2024-05-05T00:00:00Z",
     "home_team": "Brazil", "away_team": "Peru", "home_norm": "brazil",
     "away_norm": "peru", "home_score": 3, "away_score": 1, "is_complete": True,
     "tournament": "Friendly", "competition": "Friendly", "city": "Rio",
     "country": "Brazil", "neutral": False, "source_id": "martj42-international-results",
     "source_kind": "international"},
]


def _build_index(path, rows) -> None:
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df["kickoff_utc"] = pd.to_datetime(df["kickoff_utc"], utc=True)
    df["home_score"] = pd.array(list(df["home_score"]), dtype="Int16")
    df["away_score"] = pd.array(list(df["away_score"]), dtype="Int16")
    df["is_complete"] = df["is_complete"].astype(bool)
    df["neutral"] = pd.array(list(df["neutral"]), dtype="boolean")
    for col in ("match_id", "home_team", "away_team", "home_norm", "away_norm",
                "tournament", "competition", "city", "country", "source_id", "source_kind"):
        df[col] = df[col].astype("string")
    df = df[COLUMNS]
    df.to_parquet(path)


@pytest.fixture(autouse=True)
def _reset_cache():
    matches.reset_cache()
    yield
    matches.reset_cache()


@pytest.fixture
def index_at(tmp_path, monkeypatch):
    """Build a tiny index + a matching meta.json and repoint the module globals."""
    index_path = tmp_path / "matches_index.parquet"
    _build_index(index_path, _ROWS)
    meta_path = tmp_path / "matches_index.meta.json"
    meta_path.write_text(json.dumps({"row_count": len(_ROWS)}), encoding="utf-8")
    monkeypatch.setattr(matches, "INDEX_PATH", index_path)
    monkeypatch.setattr(matches, "INDEX_META_PATH", meta_path)
    empty_ledger = tmp_path / "ledger"
    empty_ledger.mkdir()
    monkeypatch.setattr(server_main, "ARTIFACT_DIR", empty_ledger)
    return TestClient(server_main.app)


def test_status_is_cold_before_any_index_use(index_at) -> None:
    body = index_at.get("/api/v1/status").json()
    assert body["index_ready"] is False
    assert body["index_state"] == "cold"
    assert body["warming_since"] is None
    # Row count comes from meta.json, so it's known even while the frame is cold.
    assert body["index_rows"] == len(_ROWS)


def test_status_flips_to_ready_after_the_index_loads(index_at) -> None:
    # Any real query warms the index.
    assert index_at.get("/api/v1/matches/recent").status_code == 200
    body = index_at.get("/api/v1/status").json()
    assert body["index_ready"] is True
    assert body["index_state"] == "ready"
    assert body["index_rows"] == len(_ROWS)


def test_status_never_triggers_the_load_itself(index_at) -> None:
    # Two status calls, then confirm the frame is STILL cold — status reports, it
    # does not warm.
    index_at.get("/api/v1/status")
    index_at.get("/api/v1/status")
    assert matches._CACHE is None
    assert index_at.get("/api/v1/status").json()["index_state"] == "cold"


def test_status_answers_even_when_the_index_is_missing(tmp_path, monkeypatch) -> None:
    # A missing index must not make /status raise: it reports "cold" (nothing has
    # tried to load yet) and a null row count, and only a real query surfaces the
    # error state.
    monkeypatch.setattr(matches, "INDEX_PATH", tmp_path / "absent.parquet")
    monkeypatch.setattr(matches, "INDEX_META_PATH", tmp_path / "absent.meta.json")
    empty_ledger = tmp_path / "ledger"
    empty_ledger.mkdir()
    monkeypatch.setattr(server_main, "ARTIFACT_DIR", empty_ledger)
    client = TestClient(server_main.app)

    body = client.get("/api/v1/status").json()
    assert body["index_ready"] is False
    assert body["index_rows"] is None

    # A search over a missing index 503s and flips the warm state to "error".
    assert client.get("/api/v1/matches/recent").status_code == 503
    assert client.get("/api/v1/status").json()["index_state"] == "error"


def test_status_is_token_gated(index_at, monkeypatch) -> None:
    monkeypatch.setenv("GOLAVO_TOKEN", "launch-token-xyz")
    client = TestClient(server_main.app)
    assert client.get("/api/v1/status").status_code == 401
    ok = client.get("/api/v1/status", headers={runtime.TOKEN_HEADER: "launch-token-xyz"})
    assert ok.status_code == 200


def test_reset_cache_returns_state_to_cold(index_at) -> None:
    # Refresh repoint hygiene: after a warm load, reset_cache() (called by
    # repoint_to_refreshed) must drop us back to cold so the next warm is honest.
    index_at.get("/api/v1/matches/recent")
    assert matches.index_status()["index_state"] == "ready"
    matches.reset_cache()
    assert matches.index_status()["index_state"] == "cold"
    assert matches._CACHE is None
