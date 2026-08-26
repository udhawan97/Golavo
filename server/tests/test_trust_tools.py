from __future__ import annotations

import hashlib
import json
import sqlite3
import zipfile
from io import BytesIO
from pathlib import Path

import pytest
from golavo_server import (
    calendar_export,
    follows,
    ledger_checkpoints,
    personal_archive,
    refresh_jobs,
    refresh_receipts,
    refresh_state,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_ARTIFACT = sorted((REPO_ROOT / "data/fixtures/sample_artifacts").glob("fa_*.json"))[0]


def _draft(match_id: str, home_goals: int) -> dict[str, object]:
    return {
        "schema_version": "0.1.0",
        "pick_id": None,
        "status": "draft",
        "match": {
            "match_id": match_id,
            "kickoff_utc": "2026-09-01T18:30:00Z",
            "kickoff_time_known": True,
            "home_team": "A",
            "away_team": "B",
            "home_norm": "a",
            "away_norm": "b",
            "competition": "League",
        },
        "user_pick": {"home_goals": home_goals, "away_goals": 0, "outcome": "home"},
        "rivals": [],
        "analysis_fingerprint": {
            "index_fingerprint": "index",
            "analysis_schema_version": "0.5.0",
            "information_cutoff_utc": "2026-09-01T18:29:59Z",
        },
        "created_at_utc": "2026-08-25T12:00:00Z",
        "updated_at_utc": "2026-08-25T12:00:00Z",
        "lock_at_utc": "2026-09-01T18:30:00Z",
        "locked_at_utc": None,
        "payload_sha256": None,
    }


def test_calendar_exports_only_exact_kickoffs_with_stable_uid() -> None:
    items = [
        {
            "follow_id": "fm_stable",
            "current": {
                "match_id": "m1",
                "kickoff_utc": "2026-09-01T18:30:00Z",
                "kickoff_precision": "exact",
                "home_team": "A, United",
                "away_team": "B; City",
                "competition": "League " * 20,
            },
        },
        {
            "follow_id": "fm_day",
            "current": {
                "match_id": "m2",
                "kickoff_utc": "2026-09-02T00:00:00Z",
                "kickoff_precision": "day",
            },
        },
    ]
    first = calendar_export.build_calendar(items, generated_at_utc="2026-08-25T12:00:00Z")
    second = calendar_export.build_calendar(items, generated_at_utc="2026-08-25T12:00:00Z")
    assert first == second
    assert first.count("BEGIN:VEVENT") == 1
    assert "DTSTART:20260901T183000Z" in first
    assert "SUMMARY:A\\, United vs B\\; City" in first
    assert "20260902" not in first
    assert all(len(line.encode("utf-8")) <= 75 for line in first.split("\r\n"))


def test_archive_round_trip_is_allowlisted_and_conflicts_require_confirmation(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / SAMPLE_ARTIFACT.name).write_bytes(SAMPLE_ARTIFACT.read_bytes())
    (source / "picks" / "drafts").mkdir(parents=True)
    draft = {
        "schema_version": "0.1.0",
        "pick_id": None,
        "status": "draft",
        "match": {
            "match_id": "m1",
            "kickoff_utc": "2026-09-01T18:30:00Z",
            "kickoff_time_known": True,
            "home_team": "A",
            "away_team": "B",
            "home_norm": "a",
            "away_norm": "b",
            "competition": "League",
        },
        "user_pick": {"home_goals": 1, "away_goals": 0, "outcome": "home"},
        "rivals": [],
        "analysis_fingerprint": {
            "index_fingerprint": "index",
            "analysis_schema_version": "0.5.0",
            "information_cutoff_utc": "2026-09-01T18:29:59Z",
        },
        "created_at_utc": "2026-08-25T12:00:00Z",
        "updated_at_utc": "2026-08-25T12:00:00Z",
        "lock_at_utc": "2026-09-01T18:30:00Z",
        "locked_at_utc": None,
        "payload_sha256": None,
    }
    draft_bytes = json.dumps(draft, sort_keys=True) + "\n"
    (source / "picks" / "drafts" / "match.json").write_text(draft_bytes)
    (source / "weather").mkdir()
    (source / "weather" / "capture.json").write_text("private-context")
    data, manifest = personal_archive.export_archive(source)
    assert [item["path"] for item in manifest["files"]] == [
        f"ledger/{SAMPLE_ARTIFACT.name}",
        "ledger/picks/drafts/match.json",
    ]
    assert "weather" not in str(manifest["files"])

    target = tmp_path / "target"
    target.mkdir()
    preview, _ = personal_archive.inspect_archive(data, ledger=target)
    assert preview["verified"] is True
    restored = personal_archive.restore_archive(data, ledger=target)
    assert restored["restored"] is True
    assert (target / "picks" / "drafts" / "match.json").read_text() == draft_bytes

    (target / "picks" / "drafts" / "match.json").write_text("different")
    different = {**draft, "user_pick": {"home_goals": 2, "away_goals": 0, "outcome": "home"}}
    (target / "picks" / "drafts" / "match.json").write_text(
        json.dumps(different, sort_keys=True) + "\n"
    )
    with pytest.raises(FileExistsError):
        personal_archive.restore_archive(data, ledger=target)
    replaced = personal_archive.restore_archive(data, ledger=target, replace=True)
    assert (target.parent / "target-archive-backups" / replaced["pre_restore_backup"]).is_file()


def test_archive_rejects_paths_outside_allowlist(tmp_path: Path) -> None:
    manifest = {
        "schema_version": "0.1.0",
        "files": [{"path": "ledger/providers/key.txt", "bytes": 1, "sha256": "0" * 64}],
    }
    stream = BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr("ledger/providers/key.txt", "x")
    with pytest.raises(ValueError, match="allowlist"):
        personal_archive.inspect_archive(stream.getvalue(), ledger=tmp_path)


def test_archive_rejects_checksum_bombs_symlink_ancestors_and_fake_follow_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact_name = f"ledger/{SAMPLE_ARTIFACT.name}"
    artifact = SAMPLE_ARTIFACT.read_bytes()
    manifest = {
        "schema_version": "0.1.0",
        "files": [{"path": artifact_name, "bytes": len(artifact), "sha256": "0" * 64}],
    }
    stream = BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr(artifact_name, artifact)
    with pytest.raises(ValueError, match="checksum"):
        personal_archive.inspect_archive(stream.getvalue(), ledger=tmp_path / "ledger")

    monkeypatch.setattr(personal_archive, "MAX_UNCOMPRESSED", 512)
    bomb = BytesIO()
    with zipfile.ZipFile(bomb, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", "{}")
        archive.writestr(artifact_name, b"0" * 2048)
    with pytest.raises(ValueError, match="expands"):
        personal_archive.inspect_archive(bomb.getvalue(), ledger=tmp_path / "ledger")
    monkeypatch.setattr(personal_archive, "MAX_UNCOMPRESSED", 64 * 1024 * 1024)

    source = tmp_path / "outside"
    source.mkdir()
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    (ledger / "picks").symlink_to(source, target_is_directory=True)
    clean = tmp_path / "clean"
    (clean / "picks" / "drafts").mkdir(parents=True)
    # A generated archive with a draft is enough to exercise destination confinement.
    draft_source = tmp_path / "draft-source"
    draft_source.mkdir()
    (draft_source / SAMPLE_ARTIFACT.name).write_bytes(artifact)
    archive_data, _ = personal_archive.export_archive(draft_source)
    # The artifact itself is safe; target an allowlisted draft explicitly through the link.
    with pytest.raises(ValueError, match="symlink"):
        personal_archive._safe_destination(ledger, "ledger/picks/drafts/example.json")
    assert personal_archive.inspect_archive(archive_data, ledger=ledger)[0]["verified"] is True

    fake = tmp_path / "fake.sqlite3"
    connection = sqlite3.connect(fake)
    connection.execute("CREATE TABLE unrelated(value TEXT)")
    connection.execute("PRAGMA user_version = 1")
    connection.commit()
    connection.close()
    fake_bytes = fake.read_bytes()
    fake_name = "ledger/follows/follows.sqlite3"
    fake_manifest = {
        "schema_version": "0.1.0",
        "files": [
            {
                "path": fake_name,
                "bytes": len(fake_bytes),
                "sha256": hashlib.sha256(fake_bytes).hexdigest(),
            }
        ],
    }
    fake_archive = BytesIO()
    with zipfile.ZipFile(fake_archive, "w") as archive:
        archive.writestr("manifest.json", json.dumps(fake_manifest))
        archive.writestr(fake_name, fake_bytes)
    with pytest.raises(ValueError, match="schema"):
        personal_archive.inspect_archive(fake_archive.getvalue(), ledger=tmp_path / "other")

    shaped = tmp_path / "shaped.sqlite3"
    connection = sqlite3.connect(shaped)
    connection.executescript(
        """
        CREATE TABLE followed_matches (
            follow_id TEXT, namespace TEXT, subscription_state TEXT, resolution_state TEXT,
            data_state TEXT, canonical_match_id TEXT, identity_source_id TEXT,
            upstream_fixture_key TEXT, initial_snapshot_json TEXT, current_snapshot_json TEXT,
            last_generation_id TEXT, last_index_fingerprint TEXT, created_at_utc TEXT,
            updated_at_utc TEXT, unfollowed_at_utc TEXT, last_observed_at_utc TEXT
        );
        CREATE UNIQUE INDEX one_active_follow_per_match
            ON followed_matches(namespace, canonical_match_id);
        CREATE INDEX followed_matches_state
            ON followed_matches(subscription_state, updated_at_utc);
        CREATE TABLE follow_identities (
            follow_id TEXT, identity_kind TEXT, identity_value TEXT, source_id TEXT,
            first_seen_at_utc TEXT, last_seen_at_utc TEXT
        );
        CREATE TABLE follow_events (
            event_id TEXT, follow_id TEXT, event_type TEXT, detected_at_utc TEXT,
            effective_at_utc TEXT, source_id TEXT, source_ref TEXT,
            source_checked_at_utc TEXT, generation_id TEXT, before_json TEXT, after_json TEXT,
            conflict_json TEXT, read_at_utc TEXT, notification_status TEXT,
            notification_batch_id TEXT, notification_updated_at_utc TEXT,
            notification_error TEXT
        );
        CREATE INDEX follow_events_feed ON follow_events(follow_id, detected_at_utc, event_id);
        CREATE INDEX follow_events_unread ON follow_events(read_at_utc, detected_at_utc);
        CREATE INDEX follow_events_notification
            ON follow_events(notification_status, detected_at_utc);
        CREATE TABLE follow_settings (
            settings_id TEXT, notifications_opt_in TEXT, created_at_utc TEXT, updated_at_utc TEXT
        );
        PRAGMA user_version = 1;
        """
    )
    connection.close()
    with pytest.raises(ValueError, match="schema"):
        personal_archive._validate_follow_database(shaped.read_bytes())


def test_archive_rejects_a_symlinked_pre_restore_backup_root(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / SAMPLE_ARTIFACT.name).write_bytes(SAMPLE_ARTIFACT.read_bytes())
    archive, _ = personal_archive.export_archive(source)
    target = tmp_path / "target"
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "target-archive-backups").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="symlink"):
        personal_archive.restore_archive(archive, ledger=target)
    assert list(outside.iterdir()) == []


def test_archive_restore_repairs_corrupt_state_and_labels_its_quarantine_copy(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / SAMPLE_ARTIFACT.name).write_bytes(SAMPLE_ARTIFACT.read_bytes())
    archive, _ = personal_archive.export_archive(source)
    target = tmp_path / "target"
    target.mkdir()
    (target / SAMPLE_ARTIFACT.name).write_text("{corrupt")

    restored = personal_archive.restore_archive(archive, ledger=target, replace=True)

    assert restored["restored"] is True
    assert restored["pre_restore_backup_verified"] is False
    assert restored["pre_restore_backup"].startswith("pre-restore-unverified-")
    assert (target / SAMPLE_ARTIFACT.name).read_bytes() == SAMPLE_ARTIFACT.read_bytes()
    quarantine = target.parent / "target-archive-backups" / restored["pre_restore_backup"]
    assert quarantine.is_file()
    with pytest.raises(ValueError):
        personal_archive.inspect_archive(quarantine.read_bytes(), ledger=target)


def test_archive_rejects_out_of_contract_snapshots_inside_canonical_follow_schema(
    tmp_path: Path,
) -> None:
    database = tmp_path / "follows.sqlite3"
    connection = sqlite3.connect(database)
    follows._migrate(connection)
    valid = {
        "match_id": "match-1",
        "kickoff_utc": "2026-09-01T18:30:00Z",
        "kickoff_precision": "exact",
        "home_team": "A",
        "away_team": "B",
        "home_score": None,
        "away_score": None,
        "competition": "League",
        "country": "Country",
        "city": "City",
        "neutral": False,
        "is_complete": False,
        "source_kind": "international",
        "source_id": "openfootball-worldcup-json",
        "upstream_fixture_key": "fixture-1",
        "provenance": {"identity": "openfootball-worldcup-json"},
    }
    forged = {**valid, "source_id": "proprietary-feed", "home_score": -99}
    connection.execute(
        "INSERT INTO followed_matches VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            "fm_" + "1" * 32,
            "core-cc0",
            "active",
            "resolved",
            "current",
            "match-1",
            "openfootball-worldcup-json",
            "fixture-1",
            json.dumps(valid),
            json.dumps(forged),
            None,
            None,
            "2026-08-25T12:00:00Z",
            "2026-08-25T12:00:00Z",
            None,
            "2026-08-25T12:00:00Z",
        ),
    )
    connection.commit()
    connection.close()

    with pytest.raises(ValueError, match="invalid match snapshot"):
        personal_archive._validate_follow_database(database.read_bytes())

    connection = sqlite3.connect(database)
    connection.execute(
        "UPDATE followed_matches SET current_snapshot_json=?",
        (json.dumps(valid),),
    )
    connection.executemany(
        """INSERT INTO follow_identities(
        follow_id, identity_kind, identity_value, source_id,
        first_seen_at_utc, last_seen_at_utc
        ) VALUES(?,?,?,?,?,?)""",
        [
            (
                "fm_" + "1" * 32,
                "match_id",
                "match-1",
                "openfootball-worldcup-json",
                "2026-08-25T12:00:00Z",
                "2026-08-25T12:00:00Z",
            ),
            (
                "fm_" + "1" * 32,
                "upstream_fixture_key",
                "fixture-1",
                "openfootball-worldcup-json",
                "2026-08-25T12:00:00Z",
                "2026-08-25T12:00:00Z",
            ),
        ],
    )
    other_match = {
        **valid,
        "match_id": "other-match",
        "upstream_fixture_key": "other-fixture",
    }
    connection.execute(
        """INSERT INTO follow_events(
        event_id, follow_id, event_type, detected_at_utc, source_id,
        after_json, notification_status
        ) VALUES(?,?,?,?,?,?,?)""",
        (
            "fe_" + "2" * 64,
            "fm_" + "1" * 32,
            "followed",
            "2026-08-25T12:00:00Z",
            "openfootball-worldcup-json",
            json.dumps(other_match),
            "not_eligible",
        ),
    )
    connection.execute(
        """INSERT INTO follow_events(
        event_id, follow_id, event_type, detected_at_utc, source_id,
        before_json, conflict_json, notification_status
        ) VALUES(?,?,?,?,?,?,?,?)""",
        (
            "fe_" + "4" * 64,
            "fm_" + "1" * 32,
            "identity_unresolved",
            "2026-08-25T14:00:00Z",
            "openfootball-worldcup-json",
            json.dumps({"match_id": "match-1"}),
            json.dumps({"reason": "no exact stable source identity"}),
            "pending",
        ),
    )
    connection.commit()
    connection.close()

    with pytest.raises(ValueError, match="recorded identity"):
        personal_archive._validate_follow_database(database.read_bytes())

    connection = sqlite3.connect(database)
    connection.execute(
        "UPDATE follow_events SET after_json=? WHERE event_type='followed'",
        (json.dumps(valid),),
    )
    connection.execute(
        """INSERT INTO follow_events(
        event_id, follow_id, event_type, detected_at_utc, source_id,
        before_json, after_json, notification_status
        ) VALUES(?,?,?,?,?,?,?,?)""",
        (
            "fe_" + "3" * 64,
            "fm_" + "1" * 32,
            "kickoff_changed",
            "2026-08-25T13:00:00Z",
            "openfootball-worldcup-json",
            json.dumps(
                {
                    "kickoff_utc": "2026-09-01T18:30:00Z",
                    "kickoff_precision": "exact",
                }
            ),
            json.dumps(
                {
                    "kickoff_utc": "2026-09-01T19:00:00Z",
                    "kickoff_precision": "exact",
                }
            ),
            "pending",
        ),
    )
    connection.commit()
    connection.close()

    personal_archive._validate_follow_database(database.read_bytes())


def test_archive_recovers_an_interruption_after_a_live_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source" / "picks" / "drafts"
    source.mkdir(parents=True)
    for name in ("a", "b"):
        (source / f"{name}.json").write_text(json.dumps(_draft(name, 1)) + "\n")
    archive, _ = personal_archive.export_archive(tmp_path / "source")

    target = tmp_path / "target"
    destination = target / "picks" / "drafts"
    destination.mkdir(parents=True)
    originals: dict[Path, bytes] = {}
    for name in ("a", "b"):
        path = destination / f"{name}.json"
        path.write_text(json.dumps(_draft(name, 2)) + "\n")
        originals[path] = path.read_bytes()

    real_replace = personal_archive.os.replace
    failed = False

    def fail_second_live_replace(source_path, destination_path):
        nonlocal failed
        destination_value = Path(destination_path)
        if destination_value == destination / "b.json" and not failed:
            failed = True
            raise OSError("injected interruption")
        return real_replace(source_path, destination_path)

    monkeypatch.setattr(personal_archive.os, "replace", fail_second_live_replace)
    with pytest.raises(OSError, match="injected"):
        personal_archive.restore_archive(archive, ledger=target, replace=True)
    assert failed is True
    assert {path: path.read_bytes() for path in originals} == originals
    assert not personal_archive._recovery_root(target).exists()


def test_refresh_receipts_detect_tampering(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOLAVO_DATA_DIR", str(tmp_path / "ledger"))
    receipt = refresh_receipts.append(
        operation="refresh_activation",
        previous_generation_id=None,
        active_generation_id="g_" + "a" * 64,
        manifest={
            "artifacts": [{"path": "index/matches_index.parquet", "sha256": "b" * 64}],
            "source_snapshots": [
                {
                    "source_id": "source",
                    "upstream_ref": "c" * 40,
                    "license": "CC0-1.0",
                    "files": [{"path": "data"}],
                }
            ],
            "capabilities": [
                {
                    "source_id": "source",
                    "competition": "League",
                    "season": "2026-27",
                    "capability": "complete",
                    "certificate": {"complete_fixture_list": True},
                }
            ],
        },
        occurred_at_utc="2026-08-25T12:00:00Z",
    )
    assert receipt["active_index_sha256"] == "b" * 64
    assert receipt["source_summaries"][0]["license"] == "CC0-1.0"
    assert receipt["change_summary"]["stable_identity_counts"] is None
    assert refresh_receipts.list_receipts()["items"] == [receipt]
    path = tmp_path / "refresh" / "receipts.jsonl"
    path.write_text(path.read_text().replace("baseline_unavailable", "comparison_unavailable"))
    with pytest.raises(ValueError, match="hash mismatch"):
        refresh_receipts.list_receipts()


def test_refresh_receipt_comparison_reports_rekeys_without_false_add_remove(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def stable(generation_id: str):
        match_id = "old-id" if generation_id == "g_old" else "new-id"
        complete = generation_id == "g_new"
        return {
            ("openfootball-worldcup-json", "fixture-7"): {
                "match_id": match_id,
                "is_complete": complete,
            }
        }, 12

    monkeypatch.setattr(refresh_receipts, "_stable_index", stable)
    summary = refresh_receipts._safe_change_summary("g_old", "g_new")
    assert summary["stable_identity_counts"] == {
        "added": 0,
        "removed": 0,
        "new_results": 1,
        "rekeyed": 1,
    }
    assert summary["unresolved_previous_rows"] == 12
    assert summary["unresolved_active_rows"] == 12


def test_refresh_receipt_gap_survives_an_interrupted_activation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GOLAVO_DATA_DIR", str(tmp_path / "ledger"))
    active = "g_" + "a" * 64
    marker = refresh_jobs._mark_receipt_pending(
        operation="refresh_activation",
        previous_generation_id=None,
        active_generation_id=active,
        occurred_at_utc="2026-08-25T12:00:00Z",
        job_id="rj_interrupted",
    )
    pointer = refresh_state.pointer_path()
    pointer.parent.mkdir(parents=True, exist_ok=True)
    pointer.write_text(
        json.dumps(
            {
                "schema_version": "0.1.0",
                "active_generation_id": active,
                "previous_generation_id": None,
                "activated_at_utc": marker["occurred_at_utc"],
            }
        )
    )

    gap = refresh_jobs.application_receipt_gap([])
    assert gap == {
        "job_id": "rj_interrupted",
        "message": (
            "the process stopped after the active pointer changed and before receipt append "
            "was confirmed"
        ),
    }
    assert (
        refresh_jobs.application_receipt_gap(
            [
                {
                    "operation": marker["operation"],
                    "active_generation_id": active,
                    "occurred_at_utc": marker["occurred_at_utc"],
                }
            ]
        )
        is None
    )


def test_refresh_receipt_append_is_atomic_and_truncated_legacy_tail_is_bounded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GOLAVO_DATA_DIR", str(tmp_path / "ledger"))
    manifest = {
        "artifacts": [{"path": "index/matches_index.parquet", "sha256": "b" * 64}],
        "source_snapshots": [],
        "capabilities": [],
    }
    first = refresh_receipts.append(
        operation="refresh_activation",
        previous_generation_id=None,
        active_generation_id="g_" + "a" * 64,
        manifest=manifest,
        occurred_at_utc="2026-08-25T12:00:00Z",
    )
    path = tmp_path / "refresh" / "receipts.jsonl"
    original = path.read_bytes()
    real_replace = refresh_receipts.os.replace

    def fail_replace(*_args: object) -> None:
        raise OSError("injected atomic replace failure")

    monkeypatch.setattr(refresh_receipts.os, "replace", fail_replace)
    with pytest.raises(OSError, match="injected atomic replace failure"):
        refresh_receipts.append(
            operation="rollback",
            previous_generation_id="g_" + "a" * 64,
            active_generation_id="g_" + "c" * 64,
            manifest=manifest,
            occurred_at_utc="2026-08-25T13:00:00Z",
        )
    assert path.read_bytes() == original
    monkeypatch.setattr(refresh_receipts.os, "replace", real_replace)

    with path.open("ab") as handle:
        handle.write(b'{"partial"')
    listed = refresh_receipts.list_receipts()
    assert listed["items"] == [first]
    assert listed["truncated_tail"] is True
    assert refresh_jobs.application_receipt_gap([], truncated_tail=True) == {
        "job_id": None,
        "message": "refresh receipt history ended with an incomplete final record",
    }


def test_checkpoint_chain_is_created_and_verified(tmp_path: Path) -> None:
    status = ledger_checkpoints.status(tmp_path)
    assert status["verified"] is True
    assert status["checkpoint_count"] == 0
    (tmp_path / SAMPLE_ARTIFACT.name).write_bytes(SAMPLE_ARTIFACT.read_bytes())
    created = ledger_checkpoints.create(tmp_path)
    assert created["artifacts"][0]["artifact_id"] == SAMPLE_ARTIFACT.stem
    status = ledger_checkpoints.status(tmp_path)
    assert status["checkpoint_count"] == 1
    assert status["missing_artifacts"] == []
    assert status["uncheckpointed_artifacts"] == []
    (tmp_path / SAMPLE_ARTIFACT.name).unlink()
    assert ledger_checkpoints.status(tmp_path)["missing_artifacts"] == [SAMPLE_ARTIFACT.stem]


def test_checkpoint_refuses_to_extend_a_corrupt_chain_without_writing(tmp_path: Path) -> None:
    (tmp_path / SAMPLE_ARTIFACT.name).write_bytes(SAMPLE_ARTIFACT.read_bytes())
    ledger_checkpoints.create(tmp_path)
    head = tmp_path / "checkpoints" / "head.json"
    value = json.loads(head.read_text())
    value["checkpoint_sha256"] = "0" * 64
    head.write_text(json.dumps(value))
    before = {path: path.read_bytes() for path in (tmp_path / "checkpoints").iterdir()}
    with pytest.raises(ValueError, match="unreadable"):
        ledger_checkpoints.create(tmp_path)
    assert {path: path.read_bytes() for path in (tmp_path / "checkpoints").iterdir()} == before


def test_checkpoint_refuses_an_orphaned_chain_when_head_was_removed(tmp_path: Path) -> None:
    (tmp_path / SAMPLE_ARTIFACT.name).write_bytes(SAMPLE_ARTIFACT.read_bytes())
    ledger_checkpoints.create(tmp_path)
    (tmp_path / "checkpoints" / "head.json").unlink()
    before = {path: path.read_bytes() for path in (tmp_path / "checkpoints").iterdir()}

    with pytest.raises(ValueError, match="head is missing"):
        ledger_checkpoints.status(tmp_path)
    with pytest.raises(ValueError, match="head is missing"):
        ledger_checkpoints.create(tmp_path)
    assert {path: path.read_bytes() for path in (tmp_path / "checkpoints").iterdir()} == before
