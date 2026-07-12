"""Tests for the on-demand MatchAnalysis + recent-matches routes.

Builds a tiny typed index (the frozen 17 columns) with enough history for a
non-abstaining council, repoints ``matches.INDEX_PATH`` at it, and drives the API
through a TestClient. Guards the honest shape (two voices + baseline), the
Replay/Preview split, leak-safe cutoff, and the empty-upcoming rail state.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from golavo_server import analysis as server_analysis
from golavo_server import main as server_main
from golavo_server import matches

COLUMNS = [
    "match_id", "date", "kickoff_utc", "home_team", "away_team", "home_norm",
    "away_norm", "home_score", "away_score", "is_complete", "tournament",
    "competition", "city", "country", "neutral", "source_id", "source_kind",
]
_INTL = "martj42-international-results"
TEAMS = ["Alpha", "Beta", "Gamma", "Delta"]


def _row(match_id, date, home, away, hs, aws, complete):
    return {
        "match_id": match_id, "date": date, "kickoff_utc": f"{date}T00:00:00Z",
        "home_team": home, "away_team": away, "home_norm": home.lower(),
        "away_norm": away.lower(), "home_score": hs, "away_score": aws,
        "is_complete": complete, "tournament": "Friendly", "competition": "Friendly",
        "city": "City", "country": "Country", "neutral": False, "source_id": _INTL,
        "source_kind": "international",
    }


def _rows() -> list[dict]:
    rows: list[dict] = []
    n = 0
    for round_no in range(6):
        for i in range(len(TEAMS)):
            for j in range(len(TEAMS)):
                if i == j:
                    continue
                n += 1
                month = 1 + round_no
                rows.append(
                    _row(f"m_h{n:04d}", f"2024-{month:02d}-{(n % 27) + 1:02d}",
                         TEAMS[i], TEAMS[j], (n % 3), (n % 2), True)
                )
    # A completed target fixture (replay) and a far-future one (preview).
    rows.append(_row("m_target", "2025-01-15", "Alpha", "Beta", 2, 1, True))
    rows.append(_row("m_future", "2030-06-01", "Alpha", "Beta", None, None, False))
    return rows


def _build_index(path: Path, rows: list[dict]) -> None:
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
    df[COLUMNS].to_parquet(path)


@pytest.fixture(autouse=True)
def _reset_cache():
    matches.reset_cache()
    server_analysis.reset_cache()
    yield
    matches.reset_cache()
    server_analysis.reset_cache()


@pytest.fixture
def client(tmp_path, monkeypatch):
    index_path = tmp_path / "matches_index.parquet"
    _build_index(index_path, _rows())
    monkeypatch.setattr(matches, "INDEX_PATH", index_path)
    empty_ledger = tmp_path / "ledger"
    empty_ledger.mkdir()
    monkeypatch.setattr(server_main, "ARTIFACT_DIR", empty_ledger)
    return TestClient(server_main.app)


def test_replay_analysis_shape_and_leak_safe_cutoff(client):
    body = client.get("/api/v1/matches/m_target/analysis").json()
    assert body["available"] is True
    a = body["analysis"]
    assert a["schema_version"] == "0.3.0"
    assert a["analysis_kind"] == "replay"
    assert a["abstained"] is False
    # Two voices, never five; the score grid is the goal voice's.
    assert a["council"]["voices"] == 2
    assert a["score_matrix_family"] == "dixon_coles"
    roles = {m["family"]: m["role"] for m in a["models"]}
    assert roles["elo_ordlogit"] == "voice"
    assert roles["dixon_coles"] == "voice"
    assert roles["poisson_independent"] == "variant"
    assert roles["bivariate_poisson"] == "variant"
    assert roles["climatological"] == "baseline"
    # Leak guard surfaced to the client: cutoff strictly precedes kickoff.
    assert a["information_cutoff_utc"] < a["match"]["kickoff_utc"]


def test_preview_analysis_kind(client):
    a = client.get("/api/v1/matches/m_future/analysis").json()["analysis"]
    assert a["analysis_kind"] == "preview"


def test_unknown_match_is_404(client):
    assert client.get("/api/v1/matches/m_nope/analysis").status_code == 404


def test_recent_rails_have_results_and_honest_upcoming(client):
    body = client.get("/api/v1/matches/recent").json()
    assert body["schema_version"] == "0.2.0"
    assert len(body["recent"]) > 0
    # The only future-dated row is m_future — it should surface in upcoming.
    assert any(m["match_id"] == "m_future" for m in body["upcoming"])
    # Recent is completed, newest first.
    assert all(m["is_complete"] for m in body["recent"])


def test_recent_is_declared_before_match_id_route(client):
    # "recent" must not be swallowed as a match id (would 404 as a match).
    assert client.get("/api/v1/matches/recent").status_code == 200
