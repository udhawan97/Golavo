"""Private loopback correction API and authoritative-data non-mutation tests."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient
from golavo_server import main as server_main
from jsonschema import Draft202012Validator, FormatChecker


@pytest.fixture
def client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[TestClient, dict[str, str], Path]:
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    seal = ledger / "fa_keep.json"
    seal.write_bytes(b'{"sealed":"unchanged"}\n')
    match = {
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
    monkeypatch.setenv("GOLAVO_TOKEN", "test-token")
    monkeypatch.setattr(server_main, "ARTIFACT_DIR", ledger)
    monkeypatch.setattr(server_main, "CORRECTIONS_DIR", tmp_path / "corrections")
    monkeypatch.setattr(
        server_main,
        "_match_for_correction",
        lambda match_id, snapshot=None: match if match_id == "match-1" else None,
    )
    snapshot = server_main.matches.IndexSnapshot(object(), "f" * 64, 1)
    monkeypatch.setattr(server_main.matches, "index_snapshot", lambda: snapshot)
    monkeypatch.setattr(server_main.matches, "snapshot_is_current", lambda value: True)
    monkeypatch.setattr(
        server_main.matches,
        "apply_if_snapshot_current",
        lambda value, operation: (operation() or True),
    )
    monkeypatch.setattr(server_main.matches, "index_fingerprint", lambda: "f" * 64)
    monkeypatch.setattr(
        server_main.refresh_jobs,
        "status",
        lambda: {"active_generation": None, "sources": [], "refresh_supported": False},
    )
    return TestClient(server_main.app), {"x-golavo-token": "test-token"}, seal


def test_end_to_end_local_annotation_export_and_no_seal_mutation(
    client: tuple[TestClient, dict[str, str], Path],
) -> None:
    api, headers, seal = client
    sealed_bytes = seal.read_bytes()
    created = api.post(
        "/api/v1/corrections",
        headers=headers,
        json={
            "correction_type": "kickoff_time",
            "source_id": "openfootball-worldcup-json",
            "target": {"match_id": "match-1"},
            "proposed": {
                "kickoff_utc": "2026-07-20T19:00:00Z",
                "kickoff_precision": "exact",
            },
        },
    )
    assert created.status_code == 201, created.text
    proposal = created.json()
    attached = api.post(
        f"/api/v1/corrections/{proposal['proposal_id']}/evidence",
        headers=headers,
        json={
            "source_url": "https://github.com/openfootball/worldcup.json/blob/master/2026/worldcup.json",
            "captured_text": "France Spain 2026-07-20 19:00",
            "source_revision": "a" * 40,
        },
    )
    assert attached.status_code == 201, attached.text
    validated = api.post(f"/api/v1/corrections/{proposal['proposal_id']}/validate", headers=headers)
    assert validated.status_code == 200, validated.text
    value = validated.json()
    assert value["state"] == "validated_candidate"
    accepted = api.post(
        f"/api/v1/corrections/{proposal['proposal_id']}/accept-local",
        headers=headers,
        json={
            "confirm": "local_annotation_only",
            "expected_head_event_id": value["head_event_id"],
        },
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["local_visibility"] == "local_annotation"
    by_match = api.get("/api/v1/matches/match-1/corrections", headers=headers)
    assert by_match.status_code == 200
    assert by_match.json()["total"] == 1

    stale_export = api.post(
        f"/api/v1/corrections/{proposal['proposal_id']}/exports",
        headers=headers,
        json={
            "confirm": "reviewed_for_public_export",
            "expected_head_event_id": value["head_event_id"],
        },
    )
    assert stale_export.status_code == 409
    assert stale_export.json()["detail"]["reason_code"] == "proposal_changed"

    exported = api.post(
        f"/api/v1/corrections/{proposal['proposal_id']}/exports",
        headers=headers,
        json={
            "confirm": "reviewed_for_public_export",
            "expected_head_event_id": accepted.json()["head_event_id"],
        },
    )
    assert exported.status_code == 200, exported.text
    assert exported.json()["export_id"].startswith("cx_")
    assert seal.read_bytes() == sealed_bytes


def test_capability_envelope_is_schema_valid_and_reports_active_index(
    client: tuple[TestClient, dict[str, str], Path],
) -> None:
    api, headers, _seal = client
    response = api.get("/api/v1/corrections/capabilities", headers=headers)
    assert response.status_code == 200
    schema = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "docs/contracts/correction_api.schema.json"
        ).read_text(encoding="utf-8")
    )
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(response.json())
    assert response.json()["current_index_fingerprint"] == "f" * 64


def test_token_body_limit_and_optimistic_concurrency(
    client: tuple[TestClient, dict[str, str], Path],
) -> None:
    api, headers, _seal = client
    assert api.get("/api/v1/corrections").status_code == 401
    oversized = api.post(
        "/api/v1/corrections",
        headers={**headers, "content-length": "131073"},
        content=b"{}",
    )
    assert oversized.status_code == 413
    created = api.post(
        "/api/v1/corrections",
        headers=headers,
        json={
            "correction_type": "venue",
            "source_id": "wikidata",
            "target": {"match_id": "match-1"},
            "proposed": {
                "venue_name": "Cotton Bowl",
                "city": "Dallas",
                "country": "United States",
            },
        },
    ).json()
    stale = api.put(
        f"/api/v1/corrections/{created['proposal_id']}/draft",
        headers=headers,
        json={"proposed": created["proposed"], "expected_head_event_id": "ce_" + "0" * 64},
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["reason_code"] == "proposal_changed"


def test_actual_body_limit_applies_without_content_length() -> None:
    sent = False

    async def receive() -> dict[str, object]:
        nonlocal sent
        if sent:
            return {"type": "http.request", "body": b"", "more_body": False}
        sent = True
        return {"type": "http.request", "body": b" " * 131073, "more_body": False}

    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/corrections",
            "headers": [],
        },
        receive,
    )
    with pytest.raises(HTTPException) as error:
        asyncio.run(server_main._correction_body(request))
    assert error.value.status_code == 413


def test_client_entity_id_is_ignored_and_alias_requires_exact_indexed_team(
    client: tuple[TestClient, dict[str, str], Path],
) -> None:
    api, headers, _seal = client
    created = api.post(
        "/api/v1/corrections",
        headers=headers,
        json={
            "correction_type": "team_alias",
            "source_id": "wikidata",
            "target": {"match_id": "match-1", "entity_id": "client-controlled"},
            "proposed": {
                "alias": "Selecao",
                "canonical_team": "Brazil",
                "scope": {
                    "source_id": "wikidata",
                    "competition": "World Cup",
                    "country": "United States",
                },
            },
        },
    )
    assert created.status_code == 201, created.text
    proposal = created.json()
    assert proposal["target"]["entity_id"] is None
    attached = api.post(
        f"/api/v1/corrections/{proposal['proposal_id']}/evidence",
        headers=headers,
        json={
            "source_url": "https://www.wikidata.org/wiki/Q155",
            "captured_text": "Selecao Brazil",
        },
    )
    assert attached.status_code == 201, attached.text
    validated = api.post(
        f"/api/v1/corrections/{proposal['proposal_id']}/validate", headers=headers
    )
    assert validated.status_code == 200, validated.text
    assert validated.json()["state"] == "evidence_attached"
    assert "alias_requires_exact_indexed_team" in validated.json()["validation"]["reason_codes"]
