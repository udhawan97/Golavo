"""The match-narrative route: off-by-default, honest failures, guard-validated ok.

Uses the same tiny typed index as the analysis tests. The happy path injects a
canned transport via ``make_transport`` so the WHOLE pipeline — bundle build,
prompt, JSON extraction, review — runs for real with no live model.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from golavo_server import ai_gateway, matches
from golavo_server import analysis as server_analysis
from golavo_server import main as server_main

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
    rows, n = [], 0
    for round_no in range(6):
        for i in range(len(TEAMS)):
            for j in range(len(TEAMS)):
                if i == j:
                    continue
                n += 1
                rows.append(
                    _row(f"m_h{n:04d}", f"2024-{1 + round_no:02d}-{(n % 27) + 1:02d}",
                         TEAMS[i], TEAMS[j], (n % 3), (n % 2), True)
                )
    rows.append(_row("m_target", "2025-01-15", "Alpha", "Beta", 2, 1, True))
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
def _reset():
    matches.reset_cache()
    server_analysis.reset_cache()
    ai_gateway._CACHE._store.clear()
    yield
    matches.reset_cache()
    server_analysis.reset_cache()
    ai_gateway._CACHE._store.clear()


@pytest.fixture(autouse=True)
def _stub_local_models(monkeypatch):
    # These tests inject a canned transport via make_transport; stub the local
    # model probe too so they exercise the pipeline deterministically and never
    # depend on a real Ollama/llama.cpp being up on the test machine.
    monkeypatch.setattr(ai_gateway, "list_local_models", lambda config: ["llama3.2:latest"])


@pytest.fixture
def client(tmp_path, monkeypatch):
    index_path = tmp_path / "matches_index.parquet"
    _build_index(index_path, _rows())
    monkeypatch.setattr(matches, "INDEX_PATH", index_path)
    empty_ledger = tmp_path / "ledger"
    empty_ledger.mkdir()
    monkeypatch.setattr(server_main, "ARTIFACT_DIR", empty_ledger)
    return TestClient(server_main.app)


def test_default_is_disabled_no_model_contacted(client):
    body = client.post("/api/v1/matches/m_target/narrative", json={}).json()
    assert body["status"] == "disabled"
    assert body["match_id"] == "m_target"
    # The bundle was still built and disclosed: its numbers are listed for the UI.
    assert any(n["id"].startswith("mc_") for n in body["numbers"])


def test_unknown_match_is_404(client):
    assert client.post("/api/v1/matches/m_nope/narrative", json={}).status_code == 404


def test_local_models_endpoint_lists_installed_models(client, monkeypatch):
    monkeypatch.setattr(
        ai_gateway,
        "inspect_local_models",
        lambda config: {
            "provider": "ollama",
            "status": "ready",
            "reason": None,
            "models": [
                {"name": "llama3.2:latest", "parameter_size": "3.2B", "params_b": 3.2, "size_bytes": 1},
                {"name": "gemma:12b", "parameter_size": "12B", "params_b": 12.0, "size_bytes": 2},
            ],
        },
    )
    body = client.get("/api/v1/ai/local-models?provider=ollama").json()
    assert body["provider"] == "ollama"
    assert body["status"] == "ready"
    assert body["reason"] is None
    assert [m["name"] for m in body["models"]] == ["llama3.2:latest", "gemma:12b"]


def test_local_models_endpoint_empty_for_non_local_provider(client):
    body = client.get("/api/v1/ai/local-models?provider=openai").json()
    assert body == {
        "provider": "openai",
        "status": "unsupported",
        "models": [],
        "reason": "This provider does not expose local models.",
    }


def test_unknown_provider_is_400(client):
    r = client.post("/api/v1/matches/m_target/narrative", json={"provider": "skynet"})
    assert r.status_code == 400


def _echo_transport(system: str, user: str) -> str:
    """A canned model: cites the goal voice's home probability from the prompt.

    Parses the allowed-numbers line the real prompt carries, so the response is
    grounded in the actual bundle — the review then accepts it for real. The line
    reads ``id=display (label); id=display (label); …`` so the display ends at the
    label's " (", the next entry's ";", or the trailing ".".
    """
    marker = "`mc_dixon_coles_prob_home` = "
    start = user.index(marker) + len(marker)
    # The allowed-numbers list is one entry per line: "- `id` = display  (label)".
    # The display ends at the label's "  (" or the end of the line.
    display = re.split(r"\s\(|\n", user[start:], maxsplit=1)[0].strip()
    narration = {
        "claims": [
            {
                "text": f"The goal model puts the home side at {display}.",
                "source_ids": ["engine:match_analysis"],
                "number_refs": ["mc_dixon_coles_prob_home"],
            }
        ],
        "scenarios": [],
        "candidate_facts": [],
    }
    return json.dumps(narration)


def test_happy_path_runs_the_real_guards(client, monkeypatch):
    monkeypatch.setattr(ai_gateway, "make_transport", lambda config: _echo_transport)
    body = client.post(
        "/api/v1/matches/m_target/narrative", json={"provider": "ollama"}
    ).json()
    assert body["status"] == "ok", body
    assert body["narration"]["claims"], "the grounded claim must survive review"
    assert body["cached"] is False

    # Second call is served from cache; refresh=true regenerates.
    again = client.post(
        "/api/v1/matches/m_target/narrative", json={"provider": "ollama"}
    ).json()
    assert again["cached"] is True
    fresh = client.post(
        "/api/v1/matches/m_target/narrative", json={"provider": "ollama", "refresh": True}
    ).json()
    assert fresh["status"] == "ok"
    assert fresh["cached"] is False


def test_async_job_returns_and_exposes_completed_result(client, monkeypatch):
    """A slow WebView request is split into start + result collection.

    TestClient waits for Starlette background tasks before returning, so the GET
    is already terminal here; a real HTTP client receives the 202 first.
    """
    monkeypatch.setattr(ai_gateway, "make_transport", lambda config: _echo_transport)
    monkeypatch.setattr(
        ai_gateway, "list_local_models", lambda config: ["gemma4:12b-it-qat"]
    )
    job_id = "cl-gemma4result123"
    response = client.post(
        "/api/v1/matches/m_target/narrative",
        json={
            "provider": "ollama",
            "model": "gemma4:12b-it-qat",
            "depth": "deep",
            "timeout_s": 480,
            "job_id": job_id,
            "async_job": True,
        },
    )
    assert response.status_code == 202
    assert response.json() == {"job_id": job_id, "state": "running"}

    completed = client.get(f"/api/v1/ai/jobs/{job_id}").json()
    assert completed["state"] == "done"
    assert completed["result"]["status"] == "ok"
    assert completed["result"]["model"] == "gemma4:12b-it-qat"
    assert completed["result"]["narration"]["claims"]


def test_ungrounded_output_falls_to_local_only(client, monkeypatch):
    def _liar(system: str, user: str) -> str:
        return json.dumps(
            {
                "claims": [
                    {
                        "text": "The home side wins 99.9% of the time.",
                        "source_ids": ["engine:match_analysis"],
                        "number_refs": [],
                    }
                ],
                "scenarios": [],
                "candidate_facts": [],
            }
        )

    monkeypatch.setattr(ai_gateway, "make_transport", lambda config: _liar)
    body = client.post(
        "/api/v1/matches/m_target/narrative", json={"provider": "ollama"}
    ).json()
    assert body["status"] == "local_only"
    assert body["narration"] is None
