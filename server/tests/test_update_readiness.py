"""Post-update readiness is read-only, token-gated, and fail-closed."""

from __future__ import annotations

import json
import sqlite3

from fastapi.testclient import TestClient
from golavo_server import follows, runtime
from golavo_server import main as server_main


def _roots(tmp_path, monkeypatch):
    ledger = tmp_path / "ledger"
    corrections = tmp_path / "corrections"
    research = tmp_path / "research"
    ledger.mkdir()
    monkeypatch.setattr(server_main, "ARTIFACT_DIR", ledger)
    monkeypatch.setattr(server_main, "CORRECTIONS_DIR", corrections)
    monkeypatch.setattr(server_main, "RESEARCH_DIR", research)
    return ledger, corrections, research


def test_update_readiness_is_token_gated_and_empty_state_is_ready(tmp_path, monkeypatch) -> None:
    _roots(tmp_path, monkeypatch)
    monkeypatch.setenv("GOLAVO_TOKEN", "launch-token")
    client = TestClient(server_main.app)

    assert client.get("/api/v1/update-readiness").status_code == 401
    response = client.get(
        "/api/v1/update-readiness", headers={runtime.TOKEN_HEADER: "launch-token"}
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "protected_files_checked": 0}


def test_update_readiness_checks_sqlite_and_json_without_writing(tmp_path, monkeypatch) -> None:
    ledger, corrections, research = _roots(tmp_path, monkeypatch)
    follow_db = ledger / "follows" / follows.DATABASE_NAME
    follow_db.parent.mkdir()
    connection = sqlite3.connect(follow_db)
    connection.execute(f"PRAGMA user_version = {follows.DATABASE_VERSION}")
    connection.execute("CREATE TABLE example(id TEXT PRIMARY KEY)")
    connection.commit()
    connection.close()
    pick = ledger / "picks" / "drafts" / "example.json"
    pick.parent.mkdir(parents=True)
    pick.write_text(json.dumps({"saved": True}), encoding="utf-8")
    research.mkdir()
    raw = research / "capture.bin"
    raw.write_bytes(b"preserved")
    before = {path: path.read_bytes() for path in (follow_db, pick, raw)}

    response = TestClient(server_main.app).get("/api/v1/update-readiness")

    assert response.status_code == 200
    assert response.json()["protected_files_checked"] == 3
    assert {path: path.read_bytes() for path in before} == before
    assert not corrections.exists()


def test_update_readiness_rejects_corrupt_database_without_replacing_it(
    tmp_path, monkeypatch
) -> None:
    ledger, _corrections, _research = _roots(tmp_path, monkeypatch)
    database = ledger / "follows" / follows.DATABASE_NAME
    database.parent.mkdir()
    original = b"not a sqlite database"
    database.write_bytes(original)

    response = TestClient(server_main.app).get("/api/v1/update-readiness")

    assert response.status_code == 503
    assert response.json()["detail"]["reason_code"] == "protected_state_not_ready"
    assert database.read_bytes() == original


def test_update_readiness_rejects_newer_store_schema(tmp_path, monkeypatch) -> None:
    ledger, _corrections, _research = _roots(tmp_path, monkeypatch)
    database = ledger / "follows" / follows.DATABASE_NAME
    database.parent.mkdir()
    connection = sqlite3.connect(database)
    connection.execute(f"PRAGMA user_version = {follows.DATABASE_VERSION + 1}")
    connection.commit()
    connection.close()

    response = TestClient(server_main.app).get("/api/v1/update-readiness")

    assert response.status_code == 503
    assert database.exists()


def test_update_readiness_rejects_malformed_user_json(tmp_path, monkeypatch) -> None:
    ledger, _corrections, _research = _roots(tmp_path, monkeypatch)
    pick = ledger / "picks" / "drafts" / "broken.json"
    pick.parent.mkdir(parents=True)
    pick.write_text("{", encoding="utf-8")

    response = TestClient(server_main.app).get("/api/v1/update-readiness")

    assert response.status_code == 503
    assert pick.read_text(encoding="utf-8") == "{"
