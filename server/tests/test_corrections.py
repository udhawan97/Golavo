"""Correction storage, validation, isolation, sanitization and export invariants."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest
from golavo_server import (
    correction_exports,
    correction_policy,
    correction_sanitize,
    correction_store,
    correction_validation,
)
from jsonschema import Draft202012Validator, FormatChecker


def _target(match_id: str = "match-1") -> dict:
    return {
        "kind": "match",
        "match_id": match_id,
        "entity_id": None,
        "upstream_record_key": "openfootball-worldcup-json:2026:72",
        "base_generation_id": None,
        "index_fingerprint": "f" * 64,
    }


def _match(**updates: object) -> dict:
    value = {
        "match_id": "match-1",
        "kickoff_utc": "2026-07-20T18:00:00Z",
        "kickoff_precision": "exact",
        "home_team": "France",
        "away_team": "Spain",
        "home_score": None,
        "away_score": None,
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
    value.update(updates)
    return value


def _proposal(root: Path, *, source_id: str = "openfootball-worldcup-json") -> dict:
    proposal, created = correction_store.create_proposal(
        root,
        correction_type="kickoff_time",
        target=_target(),
        original=correction_validation.derive_original("kickoff_time", _match()),
        proposed={"kickoff_utc": "2026-07-20T19:00:00Z", "kickoff_precision": "exact"},
        source_id=source_id,
    )
    assert created
    return proposal


def _attach(root: Path, proposal: dict, text: str = "2026-07-20 19:00 France Spain") -> dict:
    raw, display = correction_sanitize.sanitize(text)
    value, created = correction_store.attach_evidence(
        root,
        proposal["proposal_id"],
        source_url="https://github.com/openfootball/worldcup.json/blob/master/2026/worldcup.json",
        hostname="github.com",
        source_revision="a" * 40,
        raw=raw,
        evidence_receipt=correction_sanitize.receipt(raw, display),
    )
    assert created
    return value


def test_append_only_history_duplicate_and_redaction(tmp_path: Path) -> None:
    root = tmp_path / "corrections"
    proposal = _proposal(root)
    duplicate, created = correction_store.create_proposal(
        root,
        correction_type="kickoff_time",
        target=_target(),
        original=proposal["original"],
        proposed=proposal["proposed"],
        source_id=proposal["source_id"],
    )
    assert created is False
    assert duplicate["proposal_id"] == proposal["proposal_id"]

    attached = _attach(root, proposal)
    validated = correction_validation.validate(
        root, proposal["proposal_id"], current_match=_match()
    )
    assert validated["state"] == "validated_candidate"
    assert validated["verification_level"] == "structural_only"
    detailed = correction_store.get_proposal(root, proposal["proposal_id"], include_events=True)
    previous = None
    for event in detailed["events"]:
        assert event["previous_event_hash"] == previous
        previous = event["event_sha256"]

    redacted = correction_store.redact_evidence(
        root, proposal["proposal_id"], attached["evidence"][0]["evidence_id"]
    )
    assert redacted["state"] == "draft"
    assert redacted["evidence"][0]["sanitized_text"] == "[evidence redacted]"
    assert not list((root / "core-cc0" / "evidence").glob("*.txt"))


def test_snapshot_verification_requires_exact_immutable_local_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "corrections"
    proposal = _attach(root, _proposal(root))
    generation = tmp_path / "generation"
    revision = "a" * 40
    raw_path = (
        generation / "raw" / "openfootball-worldcup-json" / revision / "2026" / "worldcup.json"
    )
    raw_path.parent.mkdir(parents=True)
    raw_path.write_text("record: 2026-07-20 19:00 France Spain", encoding="utf-8")
    manifest = {
        "source_snapshots": [
            {
                "source_id": "openfootball-worldcup-json",
                "upstream_ref": revision,
                "files": [{"path": "2026/worldcup.json"}],
            }
        ]
    }
    monkeypatch.setattr(
        correction_validation.refresh_state, "active_generation", lambda: (generation, False)
    )
    monkeypatch.setattr(
        correction_validation.refresh_state, "verify_generation", lambda _path: manifest
    )
    validated = correction_validation.validate(
        root, proposal["proposal_id"], current_match=_match()
    )
    assert validated["verification_level"] == "snapshot_verified"
    assert validated["evidence"][0]["snapshot_verified"] is True
    monkeypatch.setattr(
        correction_validation.refresh_state, "active_generation", lambda: (None, False)
    )
    revalidated = correction_validation.validate(
        root, proposal["proposal_id"], current_match=_match()
    )
    assert revalidated["verification_level"] == "structural_only"
    assert revalidated["evidence"][0]["snapshot_verified"] is False


def test_conflict_fails_closed_and_never_chooses_newer(tmp_path: Path) -> None:
    root = tmp_path / "corrections"
    first = _attach(root, _proposal(root))
    second, _ = correction_store.create_proposal(
        root,
        correction_type="kickoff_time",
        target=_target(),
        original=first["original"],
        proposed={"kickoff_utc": "2026-07-20T20:00:00Z", "kickoff_precision": "exact"},
        source_id="openfootball-worldcup-json",
    )
    _attach(root, second, "2026-07-20 20:00 France Spain")
    result = correction_validation.validate(root, second["proposal_id"], current_match=_match())
    assert result["state"] == "conflict"
    assert result["local_visibility"] == "queue_only"
    with pytest.raises(correction_store.CorrectionStoreError, match="validated proposal"):
        correction_exports.export_proposal(root, second["proposal_id"])


def test_conflict_scan_is_not_limited_to_first_page(tmp_path: Path) -> None:
    root = tmp_path / "corrections"
    old, _ = correction_store.create_proposal(
        root,
        correction_type="kickoff_time",
        target=_target(),
        original=correction_validation.derive_original("kickoff_time", _match()),
        proposed={"kickoff_utc": "2026-07-20T20:00:00Z", "kickoff_precision": "exact"},
        source_id="openfootball-worldcup-json",
    )
    database = root / "core-cc0" / "queue.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE proposals SET updated_at_utc='2000-01-01T00:00:00Z' WHERE proposal_id=?",
            (old["proposal_id"],),
        )
    for index in range(101):
        correction_store.create_proposal(
            root,
            correction_type="kickoff_time",
            target=_target(f"noise-{index}"),
            original=correction_validation.derive_original("kickoff_time", _match()),
            proposed={
                "kickoff_utc": f"2026-07-{(index % 20) + 1:02d}T21:00:00Z",
                "kickoff_precision": "exact",
            },
            source_id="openfootball-worldcup-json",
        )
    candidate = _attach(root, _proposal(root), "2026-07-20 19:00 France Spain")
    result = correction_validation.validate(
        root, candidate["proposal_id"], current_match=_match()
    )
    assert result["state"] == "conflict"
    assert any(
        item.get("proposal_id") == old["proposal_id"]
        for item in result["validation"]["conflicts"]
    )


def test_export_is_deterministic_private_and_license_gated(tmp_path: Path) -> None:
    root = tmp_path / "corrections"
    proposal = _attach(root, _proposal(root), "private note 2026-07-20 19:00 France Spain")
    proposal = correction_validation.validate(root, proposal["proposal_id"], current_match=_match())
    first = correction_exports.export_proposal(root, proposal["proposal_id"])
    second = correction_exports.export_proposal(root, proposal["proposal_id"])
    assert first["export_id"] == second["export_id"]
    payload = (root / first["relative_path"]).read_bytes()
    assert hashlib.sha256(payload).hexdigest() == first["sha256"]
    export_schema = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "docs/contracts/correction_export.schema.json"
        ).read_text(encoding="utf-8")
    )
    Draft202012Validator(export_schema, format_checker=FormatChecker()).validate(
        json.loads(payload)
    )
    assert b"raw evidence" not in payload
    assert b"private note" in payload  # sanitized excerpt is intentionally reviewed/public
    assert b"captured_at_utc" not in payload

    exported = correction_store.get_proposal(root, proposal["proposal_id"])
    accepted = correction_store.transition(
        root,
        proposal["proposal_id"],
        allowed={"exported"},
        state="exported",
        event_type="accepted_local",
        payload={"scope": "local_annotation_only"},
        local_visibility="local_annotation",
        expected_head_event_id=exported["head_event_id"],
    )
    refreshed = correction_exports.export_proposal(
        root,
        proposal["proposal_id"],
        expected_head_event_id=accepted["head_event_id"],
    )
    assert refreshed["export_id"] != first["export_id"]
    assert refreshed["proposal_head_event_id"] == accepted["head_event_id"]
    assert correction_exports.export_proposal(root, proposal["proposal_id"]) == refreshed

    current = correction_store.get_proposal(root, proposal["proposal_id"])
    redacted = correction_store.redact_evidence(
        root,
        proposal["proposal_id"],
        current["evidence"][0]["evidence_id"],
        expected_head_event_id=current["head_event_id"],
    )
    assert redacted["state"] == "draft"
    assert redacted["local_visibility"] == "queue_only"
    assert not (root / first["relative_path"]).exists()

    odbl_match = _match(
        match_id="odbl-1",
        source_id="openligadb",
        provenance={
            "identity": "openligadb",
            "kickoff": "openligadb",
            "venue": "openligadb",
            "result": "openligadb",
        },
    )
    odbl, _ = correction_store.create_proposal(
        root,
        correction_type="final_score",
        target=_target("odbl-1"),
        original=correction_validation.derive_original("final_score", odbl_match),
        proposed={
            "home_score": 2,
            "away_score": 1,
            "score_basis": "regulation_plus_extra_time",
        },
        source_id="openligadb",
    )
    raw, display = correction_sanitize.sanitize("OpenLigaDB 2 1")
    correction_store.attach_evidence(
        root,
        odbl["proposal_id"],
        source_url="https://www.openligadb.de/",
        hostname="www.openligadb.de",
        source_revision="2026-07-15",
        raw=raw,
        evidence_receipt=correction_sanitize.receipt(raw, display),
    )
    odbl = correction_validation.validate(root, odbl["proposal_id"], current_match=odbl_match)
    assert odbl["state"] == "validated_candidate"
    assert correction_policy.can_export("openligadb") is False
    with pytest.raises(correction_store.CorrectionStoreError, match="ODbL namespace"):
        correction_exports.export_proposal(root, odbl["proposal_id"])


def test_hostile_text_is_plain_and_invalid_source_stays_quarantined(tmp_path: Path) -> None:
    raw, display = correction_sanitize.sanitize(
        '<script>alert(1)</script>\u202e<|system|> Keep\x00 "quoted"'
    )
    assert b"<script>" in raw
    assert "<script>" not in display
    assert "system" not in display.casefold()
    assert "\u202e" not in display and "\x00" not in display
    with pytest.raises(correction_policy.CorrectionPolicyError, match="query parameters"):
        correction_policy.canonical_evidence_url(
            "wikidata", "https://www.wikidata.org/wiki/Q155?view=private"
        )

    root = tmp_path / "corrections"
    proposal = _proposal(root, source_id="not-registered")
    raw, display = correction_sanitize.sanitize("2026-07-20 19:00")
    correction_store.attach_evidence(
        root,
        proposal["proposal_id"],
        source_url="https://example.org/evidence",
        hostname="example.org",
        source_revision=None,
        raw=raw,
        evidence_receipt=correction_sanitize.receipt(raw, display),
    )
    result = correction_validation.validate(root, proposal["proposal_id"], current_match=_match())
    assert result["license_namespace"] == "quarantine-unknown"
    assert result["state"] == "evidence_attached"
    assert "source_unregistered" in result["validation"]["reason_codes"]


def test_committed_correction_contracts_validate_examples(tmp_path: Path) -> None:
    root = tmp_path / "corrections"
    proposal = _proposal(root)
    contracts = Path(__file__).resolve().parents[2] / "docs" / "contracts"
    schema = json.loads((contracts / "correction_proposal.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(proposal)
    detailed = correction_store.get_proposal(root, proposal["proposal_id"], include_events=True)
    event_schema = json.loads(
        (contracts / "correction_event.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator(event_schema, format_checker=FormatChecker()).validate(
        detailed["events"][0]
    )
