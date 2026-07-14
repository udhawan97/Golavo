from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from golavo_server import analysis, matches, picks
from golavo_server import main as server_main


def _build_index(path: Path) -> None:
    rows = [
        {
            "match_id": "m_up",
            "date": "2026-08-01",
            "kickoff_utc": "2026-08-01T12:00:00Z",
            "home_team": "Aland",
            "away_team": "Borda",
            "home_norm": "aland",
            "away_norm": "borda",
            "home_score": None,
            "away_score": None,
            "is_complete": False,
            "tournament": "Test Cup",
            "competition": "Test Cup",
            "city": "City",
            "country": "Country",
            "neutral": False,
            "source_id": "test",
            "source_kind": "club",
        }
    ]
    frame = pd.DataFrame(rows)
    frame["date"] = pd.to_datetime(frame["date"])
    frame["kickoff_utc"] = pd.to_datetime(frame["kickoff_utc"], utc=True)
    frame["home_score"] = pd.array(frame["home_score"], dtype="Int16")
    frame["away_score"] = pd.array(frame["away_score"], dtype="Int16")
    frame["is_complete"] = frame["is_complete"].astype(bool)
    frame["neutral"] = pd.array(frame["neutral"], dtype="boolean")
    for column in (
        "match_id",
        "home_team",
        "away_team",
        "home_norm",
        "away_norm",
        "tournament",
        "competition",
        "city",
        "country",
        "source_id",
        "source_kind",
    ):
        frame[column] = frame[column].astype("string")
    frame.to_parquet(path)


def _analysis() -> dict:
    return {
        "available": True,
        "reason": None,
        "analysis": {
            "schema_version": "0.4.1",
            "information_cutoff_utc": "2026-08-01T11:59:59Z",
            "models": [
                {
                    "family": family,
                    "abstained": False,
                    "probs": {"home": 0.6, "draw": 0.2, "away": 0.2},
                    "score_matrix": (
                        {"most_likely": {"home": 2, "away": 1, "probability": 0.15}}
                        if family in {"dixon_coles", "poisson_independent", "bivariate_poisson"}
                        else None
                    ),
                }
                for family in (
                    "dixon_coles",
                    "poisson_independent",
                    "bivariate_poisson",
                    "elo_ordlogit",
                    "climatological",
                )
            ],
        },
    }


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    index = tmp_path / "index.parquet"
    _build_index(index)
    monkeypatch.setattr(matches, "INDEX_PATH", index)
    monkeypatch.setattr(matches, "index_fingerprint", lambda: "idx-api")
    monkeypatch.setattr(analysis, "match_analysis", lambda match_id: _analysis())
    monkeypatch.setattr(server_main, "ARTIFACT_DIR", tmp_path / "ledger")
    monkeypatch.setattr(
        picks, "_now", lambda now=None: now or datetime(2026, 8, 1, 10, 0, tzinfo=UTC)
    )
    matches.reset_cache()
    return TestClient(server_main.app)


def test_put_get_delete_and_match_summary(client: TestClient) -> None:
    saved = client.put("/api/v1/matches/m_up/pick", json={"home_goals": 2, "away_goals": 1})
    assert saved.status_code == 200
    assert saved.json()["pick"]["record"]["user_pick"]["outcome"] == "home"
    assert saved.json()["editable"] is True

    fetched = client.get("/api/v1/matches/m_up/pick").json()
    assert fetched["pick"]["status"] == "draft"
    detail = client.get("/api/v1/matches/m_up").json()
    assert detail["pick"] == {"id": None, "status": "draft"}

    removed = client.delete("/api/v1/matches/m_up/pick")
    assert removed.status_code == 200
    assert removed.json()["pick"] is None
    assert client.get("/api/v1/picks").json()["total"] == 0


def test_api_typed_errors_and_no_write_on_analysis_failure(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    invalid = client.put("/api/v1/matches/m_up/pick", json={"home_goals": 21, "away_goals": 0})
    assert invalid.status_code == 422
    assert invalid.json()["detail"]["reason_code"] == "invalid_score"

    monkeypatch.setattr(
        analysis,
        "match_analysis",
        lambda match_id: {"available": False, "reason": "no", "analysis": None},
    )
    unavailable = client.put("/api/v1/matches/m_up/pick", json={"home_goals": 1, "away_goals": 0})
    assert unavailable.status_code == 503
    assert unavailable.json()["detail"]["reason_code"] == "analysis_unavailable"
    assert not (server_main.ARTIFACT_DIR / "picks" / "drafts" / "m_up.json").exists()
    assert client.get("/api/v1/matches/missing/pick").status_code == 404


def test_lock_list_summary_integrity_and_cors(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    client.put("/api/v1/matches/m_up/pick", json={"home_goals": 1, "away_goals": 0})
    monkeypatch.setattr(
        picks,
        "_now",
        lambda now=None: now or datetime(2026, 8, 1, 12, 0, tzinfo=UTC),
    )
    locked = client.get("/api/v1/matches/m_up/pick")
    assert locked.json()["pick"]["status"] == "locked"
    assert locked.json()["editable"] is False
    assert (
        client.put("/api/v1/matches/m_up/pick", json={"home_goals": 2, "away_goals": 0}).status_code
        == 409
    )
    assert client.get("/api/v1/picks", params={"status": "locked"}).json()["total"] == 1
    assert client.get("/api/v1/picks/summary").json()["counts"]["locked"] == 1

    for method in ("PUT", "DELETE"):
        preflight = client.options(
            "/api/v1/matches/m_up/pick",
            headers={
                "Origin": "tauri://localhost",
                "Access-Control-Request-Method": method,
            },
        )
        assert preflight.status_code == 200
        assert method in preflight.headers["access-control-allow-methods"]

    path = next((server_main.ARTIFACT_DIR / "picks").glob("pk_*.json"))
    raw = json.loads(path.read_text())
    raw["user_pick"]["away_goals"] = 9
    path.write_text(json.dumps(raw))
    corrupt = client.get("/api/v1/matches/m_up/pick")
    assert corrupt.status_code == 500
    assert corrupt.json()["detail"]["reason_code"] == "integrity_error"
    assert client.get("/api/v1/picks").json()["total"] == 0
