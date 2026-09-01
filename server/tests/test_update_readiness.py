"""Post-update readiness is read-only, token-gated, and fail-closed."""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient
from golavo_server import (
    correction_sanitize,
    correction_store,
    follows,
    ledger_checkpoints,
    runtime,
)
from golavo_server import main as server_main
from golavo_server.research import store as research_store

ROOT = Path(__file__).resolve().parents[2]
SAMPLE_FORECAST = sorted((ROOT / "ui" / "src" / "mocks" / "forecasts").glob("fa_*.json"))[0]


def _roots(tmp_path, monkeypatch):
    ledger = tmp_path / "ledger"
    corrections = tmp_path / "corrections"
    research = tmp_path / "research"
    ledger.mkdir()
    monkeypatch.setattr(server_main, "ARTIFACT_DIR", ledger)
    monkeypatch.setattr(server_main, "CORRECTIONS_DIR", corrections)
    monkeypatch.setattr(server_main, "RESEARCH_DIR", research)
    return ledger, corrections, research


def _research_capture(
    root: Path, *, schema_version: str = research_store.SCHEMA_VERSION
) -> Path:
    raw = b"France v Spain: 18:00 UTC"
    raw_hash = hashlib.sha256(raw).hexdigest()
    text = raw.decode("utf-8")
    source_id = "wikipedia-en"
    namespace = "research-cc-by-sa-4.0"
    document_url = "https://en.wikipedia.org/wiki/France_national_football_team"
    capture_id = research_store.capture_id_for(
        run_id="rr_test",
        source_id=source_id,
        canonical_url=document_url,
        document_url=document_url,
        entity_id=None,
        raw_sha256=raw_hash,
    )
    research_store.add_capture(
        root,
        {
            "schema_version": schema_version,
            "capture_id": capture_id,
            "run_id": "rr_test",
            "source_id": source_id,
            "license_namespace": namespace,
            "canonical_url": document_url,
            "document_url": document_url,
            "entity_id": None,
            "raw_sha256": raw_hash,
            "raw_bytes": len(raw),
            "canonical_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "canonical_text": text,
        },
        raw,
    )
    return root / namespace / "captures" / f"{raw_hash}.bin"


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
    connection = follows._connect(ledger, create=True)
    assert connection is not None
    connection.close()
    notebook = ledger / "notebooks" / "example.json"
    notebook.parent.mkdir(parents=True)
    notebook.write_text(json.dumps({"saved": True}), encoding="utf-8")
    research.mkdir()
    raw = research / "capture.bin"
    raw.write_bytes(b"preserved")
    before = {path: path.read_bytes() for path in (follow_db, notebook, raw)}

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


def test_update_readiness_rejects_unsupported_forecast_schema_without_mutation(
    tmp_path, monkeypatch
) -> None:
    ledger, _corrections, _research = _roots(tmp_path, monkeypatch)
    target = ledger / SAMPLE_FORECAST.name
    artifact = json.loads(SAMPLE_FORECAST.read_text(encoding="utf-8"))
    artifact["schema_version"] = "999.0.0"
    target.write_text(json.dumps(artifact), encoding="utf-8")
    before = target.read_bytes()

    response = TestClient(server_main.app).get("/api/v1/update-readiness")

    assert response.status_code == 503
    assert response.json()["detail"]["reason_code"] == "protected_state_not_ready"
    assert target.read_bytes() == before


def test_update_readiness_accepts_a_canonical_forecast_without_mutation(
    tmp_path, monkeypatch
) -> None:
    ledger, _corrections, _research = _roots(tmp_path, monkeypatch)
    target = ledger / SAMPLE_FORECAST.name
    shutil.copyfile(SAMPLE_FORECAST, target)
    before = target.read_bytes()

    response = TestClient(server_main.app).get("/api/v1/update-readiness")

    assert response.status_code == 200
    assert response.json()["protected_files_checked"] == 1
    assert target.read_bytes() == before


def test_update_readiness_rejects_checkpoint_with_missing_artifact_without_mutation(
    tmp_path, monkeypatch
) -> None:
    ledger, _corrections, _research = _roots(tmp_path, monkeypatch)
    target = ledger / SAMPLE_FORECAST.name
    shutil.copyfile(SAMPLE_FORECAST, target)
    ledger_checkpoints.create(ledger)
    target.unlink()
    remaining = {path: path.read_bytes() for path in ledger.rglob("*") if path.is_file()}

    response = TestClient(server_main.app).get("/api/v1/update-readiness")

    assert response.status_code == 503
    assert response.json()["detail"]["reason_code"] == "protected_state_not_ready"
    assert ledger_checkpoints.status(ledger)["missing_artifacts"] == [target.stem]
    assert {path: path.read_bytes() for path in remaining} == remaining


def test_update_readiness_rejects_tampered_forecast_hash_without_mutation(
    tmp_path, monkeypatch
) -> None:
    ledger, _corrections, _research = _roots(tmp_path, monkeypatch)
    target = ledger / SAMPLE_FORECAST.name
    shutil.copyfile(SAMPLE_FORECAST, target)
    artifact = json.loads(target.read_text(encoding="utf-8"))
    artifact["provenance"]["payload_sha256"] = "0" * 64
    target.write_text(json.dumps(artifact), encoding="utf-8")
    before = target.read_bytes()

    response = TestClient(server_main.app).get("/api/v1/update-readiness")

    assert response.status_code == 503
    assert response.json()["detail"]["reason_code"] == "protected_state_not_ready"
    assert target.read_bytes() == before


def test_update_readiness_rejects_tampered_correction_chain_without_mutation(
    tmp_path, monkeypatch
) -> None:
    _ledger, corrections, _research = _roots(tmp_path, monkeypatch)
    correction_store.create_proposal(
        corrections,
        correction_type="kickoff_time",
        target={"kind": "match", "match_id": "match-1"},
        original=None,
        proposed={"kickoff_utc": "2026-09-01T18:00:00Z"},
        source_id="openfootball-worldcup-json",
    )
    database = next(corrections.glob(f"*/{correction_store.DATABASE_NAME}"))
    connection = sqlite3.connect(database)
    connection.execute("DROP TRIGGER proposal_events_no_update")
    connection.execute("UPDATE proposal_events SET payload_json='{}'")
    connection.commit()
    connection.close()
    before = database.read_bytes()

    response = TestClient(server_main.app).get("/api/v1/update-readiness")

    assert response.status_code == 503
    assert response.json()["detail"]["reason_code"] == "protected_state_not_ready"
    assert database.read_bytes() == before


def test_update_readiness_accepts_canonical_correction_evidence_without_mutation(
    tmp_path, monkeypatch
) -> None:
    _ledger, corrections, _research = _roots(tmp_path, monkeypatch)
    proposal, _created = correction_store.create_proposal(
        corrections,
        correction_type="kickoff_time",
        target={"kind": "match", "match_id": "match-1"},
        original=None,
        proposed={"kickoff_utc": "2026-09-01T18:00:00Z"},
        source_id="openfootball-worldcup-json",
    )
    raw, display = correction_sanitize.sanitize("France v Spain: 18:00 UTC")
    correction_store.attach_evidence(
        corrections,
        proposal["proposal_id"],
        source_url="https://example.test/correction",
        hostname="example.test",
        source_revision=None,
        raw=raw,
        evidence_receipt=correction_sanitize.receipt(raw, display),
    )
    before = {path: path.read_bytes() for path in corrections.rglob("*") if path.is_file()}

    response = TestClient(server_main.app).get("/api/v1/update-readiness")

    assert response.status_code == 200
    assert {path: path.read_bytes() for path in before} == before


def test_update_readiness_accepts_canonical_research_capture_without_mutation(
    tmp_path, monkeypatch
) -> None:
    _ledger, _corrections, research = _roots(tmp_path, monkeypatch)
    _research_capture(research)
    before = {path: path.read_bytes() for path in research.rglob("*") if path.is_file()}

    response = TestClient(server_main.app).get("/api/v1/update-readiness")

    assert response.status_code == 200
    assert {path: path.read_bytes() for path in before} == before


def test_update_readiness_rejects_tampered_research_capture_without_mutation(
    tmp_path, monkeypatch
) -> None:
    _ledger, _corrections, research = _roots(tmp_path, monkeypatch)
    raw_path = _research_capture(research)
    raw_path.write_bytes(b"tampered")
    before = {path: path.read_bytes() for path in research.rglob("*") if path.is_file()}

    response = TestClient(server_main.app).get("/api/v1/update-readiness")

    assert response.status_code == 503
    assert response.json()["detail"]["reason_code"] == "protected_state_not_ready"
    assert {path: path.read_bytes() for path in before} == before


def test_update_readiness_rejects_unsupported_research_schema_without_mutation(
    tmp_path, monkeypatch
) -> None:
    _ledger, _corrections, research = _roots(tmp_path, monkeypatch)
    _research_capture(research, schema_version="999.0.0")
    before = {path: path.read_bytes() for path in research.rglob("*") if path.is_file()}

    response = TestClient(server_main.app).get("/api/v1/update-readiness")

    assert response.status_code == 503
    assert response.json()["detail"]["reason_code"] == "protected_state_not_ready"
    assert {path: path.read_bytes() for path in before} == before


def test_readiness_failure_cannot_reach_backup_retirement() -> None:
    lifecycle = (ROOT / "desktop" / "src-tauri" / "src" / "lib.rs").read_text(
        encoding="utf-8"
    )
    readiness = lifecycle.index("health::wait_for_update_readiness_or_exit")
    finalization = lifecycle.index("updater::finalize_update_if_pending", readiness)
    failure_branch = lifecycle.index("HealthOutcome::TimedOut", readiness)

    assert readiness < failure_branch < finalization
    assert "return;" in lifecycle[failure_branch:finalization]
