"""Private foreground research API and Phase 6 queue integration tests."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from golavo_server import correction_store, jobs
from golavo_server import main as server_main
from golavo_server.research import store
from golavo_server.research.fetch import FetchResponse
from golavo_server.research.orchestrator import run_capture
from jsonschema import Draft202012Validator, FormatChecker

FINGERPRINT = "f" * 64
URL = "https://www.wikidata.org/w/rest.php/wikibase/v1/entities/items/Q142"
MATCH = {
    "match_id": "match-1",
    "kickoff_utc": "2026-07-20T18:00:00Z",
    "kickoff_precision": "exact",
    "home_team": "France",
    "away_team": "Spain",
    "home_score": None,
    "away_score": None,
    "competition": "World Cup",
    "city": "Dallas",
    "country": "United States",
    "is_complete": False,
    "source_id": "openfootball-worldcup-json",
    "upstream_fixture_key": "openfootball-worldcup-json:2026:72",
    "provenance": {
        "identity": "openfootball-worldcup-json",
        "kickoff": "openfootball-worldcup-json",
        "venue": "openfootball-worldcup-json",
        "result": "openfootball-worldcup-json",
    },
}


@pytest.fixture
def client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[TestClient, dict[str, str], Path, Path]:
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    seal = ledger / "fa_keep.json"
    seal.write_bytes(b'{"sealed":"unchanged"}\n')
    research = tmp_path / "research"
    corrections = tmp_path / "corrections"
    monkeypatch.setenv("GOLAVO_TOKEN", "test-token")
    monkeypatch.setattr(server_main, "ARTIFACT_DIR", ledger)
    monkeypatch.setattr(server_main, "RESEARCH_DIR", research)
    monkeypatch.setattr(server_main, "CORRECTIONS_DIR", corrections)
    monkeypatch.setattr(
        server_main,
        "_match_for_correction",
        lambda match_id: MATCH if match_id == "match-1" else None,
    )
    monkeypatch.setattr(server_main.matches, "index_fingerprint", lambda: FINGERPRINT)
    return TestClient(server_main.app), {"x-golavo-token": "test-token"}, seal, research


def _candidate(research: Path) -> dict:
    raw = json.dumps(
        {
            "id": "Q142",
            "labels": {"en": "France"},
            "aliases": {"en": ["Les Bleus"]},
            "descriptions": {"en": "national association football team"},
            "revision": 123,
        }
    ).encode()

    def fetcher(url: str, **_kwargs: object) -> FetchResponse:
        return FetchResponse(
            canonical_url=url,
            source_id="wikidata",
            status=200,
            content_type="application/json",
            body=raw,
            etag='"123"',
            last_modified=None,
        )

    run = run_capture(
        research,
        match=MATCH,
        index_fingerprint=FINGERPRINT,
        selected_urls=[URL],
        fetcher=fetcher,
    )
    return store.list_candidates(research, run["run_id"])[0]


def test_research_routes_require_private_desktop_token(
    client: tuple[TestClient, dict[str, str], Path, Path],
) -> None:
    api, _headers, _seal, _research = client
    assert api.get("/api/v1/research/capabilities").status_code == 401


def test_capabilities_validate_and_consent_starts_off(
    client: tuple[TestClient, dict[str, str], Path, Path],
) -> None:
    api, headers, _seal, _research = client
    response = api.get("/api/v1/research/capabilities", headers=headers)
    assert response.status_code == 200
    schema = json.loads(
        (Path(__file__).resolve().parents[2] / "docs/contracts/research_api.schema.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(response.json())
    body = response.json()
    assert body["enabled"] is False
    assert body["automatic_fetch"] is False
    assert body["built_in_general_search"] is False
    assert body["cloud_ai_extraction"] is False
    assert body["authoritative_output"] is False


def test_discovery_requires_both_consent_and_explicit_action(
    client: tuple[TestClient, dict[str, str], Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api, headers, _seal, _research = client
    disabled = api.post(
        "/api/v1/research/discoveries",
        headers=headers,
        json={"query": "France Spain", "provider": "wikimedia", "confirm": "discover_sources"},
    )
    assert disabled.status_code == 409
    enabled = api.put(
        "/api/v1/research/settings",
        headers=headers,
        json={"enabled": True, "retention_days": 30, "searxng_enabled": False},
    )
    assert enabled.status_code == 200

    calls: list[str] = []
    monkeypatch.setattr(
        server_main.match_research,
        "discover",
        lambda query, **_kwargs: (
            calls.append(query)
            or [
                {
                    "provider": "wikidata",
                    "title": "France",
                    "url": URL,
                    "source_id": "wikidata",
                    "permitted": True,
                    "license_namespace": "enrichment-cc0",
                }
            ]
        ),
    )
    missing_confirmation = api.post(
        "/api/v1/research/discoveries",
        headers=headers,
        json={"query": "France Spain", "provider": "wikimedia"},
    )
    assert missing_confirmation.status_code == 422
    assert calls == []
    found = api.post(
        "/api/v1/research/discoveries",
        headers=headers,
        json={"query": "France Spain", "provider": "wikimedia", "confirm": "discover_sources"},
    )
    assert found.status_code == 200
    assert calls == ["France Spain"]
    assert found.json()["items"][0]["url"] == URL


def test_candidate_queues_as_untrusted_draft_without_mutating_seal(
    client: tuple[TestClient, dict[str, str], Path, Path],
) -> None:
    api, headers, seal, research = client
    candidate = _candidate(research)
    sealed_bytes = seal.read_bytes()
    response = api.post(
        f"/api/v1/research/candidates/{candidate['candidate_id']}/queue",
        headers=headers,
        json={
            "expected_candidate_sha256": candidate["candidate_id"][3:],
            "expected_index_fingerprint": FINGERPRINT,
            "confirm": "add_to_correction_queue",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["candidate"]["state"] == "queued_as_draft"
    assert body["proposal"]["state"] == "evidence_attached"
    assert body["proposal"]["verification_level"] == "none"
    assert body["proposal"]["local_visibility"] == "queue_only"
    assert body["proposal"]["evidence"][0]["untrusted"] is True
    proposal_with_events = correction_store.get_proposal(
        Path(server_main.CORRECTIONS_DIR), body["proposal"]["proposal_id"], include_events=True
    )
    assert any(
        event["event_type"] == "evidence_imported_from_research"
        for event in proposal_with_events["events"]
    )
    assert seal.read_bytes() == sealed_bytes

    repeated = api.post(
        f"/api/v1/research/candidates/{candidate['candidate_id']}/queue",
        headers=headers,
        json={
            "expected_candidate_sha256": candidate["candidate_id"][3:],
            "expected_index_fingerprint": FINGERPRINT,
            "confirm": "add_to_correction_queue",
        },
    )
    assert repeated.status_code == 200
    assert repeated.json()["proposal"]["proposal_id"] == body["proposal"]["proposal_id"]


def test_stale_candidate_fails_closed(
    client: tuple[TestClient, dict[str, str], Path, Path],
) -> None:
    api, headers, _seal, research = client
    candidate = _candidate(research)
    response = api.post(
        f"/api/v1/research/candidates/{candidate['candidate_id']}/queue",
        headers=headers,
        json={
            "expected_candidate_sha256": candidate["candidate_id"][3:],
            "expected_index_fingerprint": "0" * 64,
            "confirm": "add_to_correction_queue",
        },
    )
    assert response.status_code == 409
    assert "stale" in response.json()["detail"]


def test_history_delete_preserves_research_consent(
    client: tuple[TestClient, dict[str, str], Path, Path],
) -> None:
    api, headers, _seal, research = client
    api.put(
        "/api/v1/research/settings",
        headers=headers,
        json={"enabled": True, "retention_days": 30, "searxng_enabled": False},
    )
    _candidate(research)
    removed = api.request(
        "DELETE",
        "/api/v1/research/history",
        headers=headers,
        json={"confirm": "remove_local_research_history"},
    )
    assert removed.status_code == 200
    assert removed.json()["settings_preserved"] is True
    current = api.get("/api/v1/research/settings", headers=headers).json()
    assert current["enabled"] is True
    assert not (research / "control.sqlite3").exists()


def test_match_run_history_survives_navigation_and_recovers_interruption(
    client: tuple[TestClient, dict[str, str], Path, Path],
) -> None:
    api, headers, _seal, research = client
    run = store.create_run(
        research,
        match_id="match-1",
        index_fingerprint=FINGERPRINT,
        selected_urls=[URL],
        allow_local_ai=False,
    )
    response = api.get(
        "/api/v1/research/runs", headers=headers, params={"match_id": "match-1", "limit": 1}
    )
    assert response.status_code == 200
    restored = response.json()["items"][0]
    assert restored["run_id"] == run["run_id"]
    assert restored["state"] == "cancelled"
    assert restored["reason_codes"] == ["app_interrupted"]


def test_history_delete_refuses_an_active_run(
    client: tuple[TestClient, dict[str, str], Path, Path],
) -> None:
    api, headers, _seal, research = client
    run = store.create_run(
        research,
        match_id="match-1",
        index_fingerprint=FINGERPRINT,
        selected_urls=[URL],
        allow_local_ai=False,
    )
    jobs.store().start(run["run_id"])
    try:
        response = api.request(
            "DELETE",
            "/api/v1/research/history",
            headers=headers,
            json={"confirm": "remove_local_research_history"},
        )
        assert response.status_code == 409
        assert response.json()["detail"]["reason_code"] == "research_run_active"
        assert (research / "control.sqlite3").is_file()
    finally:
        jobs.store().cancel(run["run_id"])


def test_tampered_candidate_cannot_enter_correction_queue(
    client: tuple[TestClient, dict[str, str], Path, Path],
) -> None:
    api, headers, _seal, research = client
    candidate = _candidate(research)
    database = research / "enrichment-cc0" / "research.sqlite3"
    connection = sqlite3.connect(database)
    row = connection.execute(
        "SELECT payload_json FROM candidates WHERE candidate_id=?",
        (candidate["candidate_id"],),
    ).fetchone()
    payload = json.loads(row[0])
    payload["proposed"]["alias"] = "Invented FC"
    with connection:
        connection.execute(
            "UPDATE candidates SET payload_json=? WHERE candidate_id=?",
            (json.dumps(payload, sort_keys=True, separators=(",", ":")), candidate["candidate_id"]),
        )
    connection.close()
    response = api.post(
        f"/api/v1/research/candidates/{candidate['candidate_id']}/queue",
        headers=headers,
        json={
            "expected_candidate_sha256": candidate["candidate_id"][3:],
            "expected_index_fingerprint": FINGERPRINT,
            "confirm": "add_to_correction_queue",
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"]["reason_code"] == "candidate_verification_failed"
    assert not Path(server_main.CORRECTIONS_DIR).exists()
