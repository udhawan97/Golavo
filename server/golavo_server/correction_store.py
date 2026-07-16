"""License-separated, append-only local correction proposal store."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from golavo_server import correction_policy

SCHEMA_VERSION = "0.1.0"
DATABASE_VERSION = 1
DATABASE_NAME = "queue.sqlite3"
ACTIVE_STATES = {
    "draft",
    "evidence_attached",
    "validated_candidate",
    "conflict",
    "accepted_local",
    "exported",
    "submitted",
}


class CorrectionStoreError(Exception):
    def __init__(self, reason_code: str, detail: str, status_code: int = 409) -> None:
        super().__init__(detail)
        self.reason_code = reason_code
        self.detail = detail
        self.status_code = status_code


def now_z() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _database_path(root: Path, namespace: str) -> Path:
    if namespace not in correction_policy.KNOWN_NAMESPACES:
        raise CorrectionStoreError("invalid_license_namespace", "unknown correction namespace", 422)
    return Path(root) / namespace / DATABASE_NAME


def _connect(root: Path, namespace: str, *, create: bool) -> sqlite3.Connection | None:
    path = _database_path(root, namespace)
    if not path.exists() and not create:
        return None
    if create:
        path.parent.mkdir(parents=True, exist_ok=True)
    try:
        connection = sqlite3.connect(path, timeout=5.0)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = DELETE")
        connection.execute("PRAGMA synchronous = FULL")
        _migrate(connection)
        check = connection.execute("PRAGMA quick_check").fetchone()
        if check is None or check[0] != "ok":
            connection.close()
            raise CorrectionStoreError(
                "correction_store_unavailable",
                "correction history failed its integrity check; "
                "the original database was preserved",
                503,
            )
        return connection
    except CorrectionStoreError:
        raise
    except (OSError, sqlite3.DatabaseError) as exc:
        raise CorrectionStoreError(
            "correction_store_unavailable",
            f"correction history is unavailable; the original database was preserved: {exc}",
            503,
        ) from exc


def _migrate(connection: sqlite3.Connection) -> None:
    version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if version > DATABASE_VERSION:
        raise CorrectionStoreError(
            "correction_store_newer_version",
            "correction history was created by a newer Golavo version",
            503,
        )
    if version == DATABASE_VERSION:
        return
    if version != 0:
        raise CorrectionStoreError(
            "correction_store_unavailable", "unsupported database version", 503
        )
    with connection:
        connection.executescript(
            """
            CREATE TABLE proposals (
                proposal_id TEXT PRIMARY KEY,
                license_namespace TEXT NOT NULL,
                correction_type TEXT NOT NULL,
                state TEXT NOT NULL,
                verification_level TEXT NOT NULL,
                target_json TEXT NOT NULL,
                original_json TEXT,
                proposed_json TEXT NOT NULL,
                source_id TEXT,
                validation_json TEXT NOT NULL,
                local_visibility TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                created_at_utc TEXT NOT NULL,
                updated_at_utc TEXT NOT NULL,
                head_event_id TEXT
            );
            CREATE INDEX proposal_feed ON proposals(updated_at_utc DESC, proposal_id DESC);
            CREATE INDEX proposal_target ON proposals(correction_type, fingerprint);

            CREATE TABLE proposal_events (
                event_id TEXT PRIMARY KEY,
                proposal_id TEXT NOT NULL REFERENCES proposals(proposal_id),
                sequence INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                recorded_at_utc TEXT NOT NULL,
                previous_event_hash TEXT,
                payload_json TEXT NOT NULL,
                payload_sha256 TEXT NOT NULL,
                event_sha256 TEXT NOT NULL,
                UNIQUE(proposal_id, sequence)
            );
            CREATE TRIGGER proposal_events_no_update
                BEFORE UPDATE ON proposal_events BEGIN
                    SELECT RAISE(ABORT, 'events are append-only');
                END;
            CREATE TRIGGER proposal_events_no_delete
                BEFORE DELETE ON proposal_events BEGIN
                    SELECT RAISE(ABORT, 'events are append-only');
                END;

            CREATE TABLE evidence (
                evidence_id TEXT PRIMARY KEY,
                proposal_id TEXT NOT NULL REFERENCES proposals(proposal_id),
                source_url TEXT NOT NULL,
                hostname TEXT NOT NULL,
                source_id TEXT NOT NULL,
                license_namespace TEXT NOT NULL,
                source_revision TEXT,
                raw_sha256 TEXT NOT NULL,
                raw_bytes INTEGER NOT NULL,
                sanitized_text TEXT NOT NULL,
                sanitized_sha256 TEXT NOT NULL,
                snapshot_verified INTEGER NOT NULL DEFAULT 0,
                captured_at_utc TEXT NOT NULL,
                redacted INTEGER NOT NULL DEFAULT 0,
                UNIQUE(proposal_id, raw_sha256, source_url)
            );
            CREATE TABLE exports (
                export_id TEXT PRIMARY KEY,
                proposal_id TEXT NOT NULL REFERENCES proposals(proposal_id),
                proposal_head_event_id TEXT NOT NULL,
                relative_path TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                bytes INTEGER NOT NULL,
                created_at_utc TEXT NOT NULL,
                UNIQUE(proposal_id, proposal_head_event_id)
            );
            PRAGMA user_version = 1;
            """
        )


def _fingerprint(
    namespace: str, correction_type: str, target: dict[str, Any], proposed: dict[str, Any]
) -> str:
    material = canonical(
        {
            "schema_version": SCHEMA_VERSION,
            "license_namespace": namespace,
            "correction_type": correction_type,
            "target": target,
            "proposed": proposed,
        }
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _append_event(
    connection: sqlite3.Connection,
    proposal_id: str,
    event_type: str,
    payload: dict[str, Any],
    *,
    recorded_at: str,
) -> str:
    previous = connection.execute(
        """SELECT sequence, event_sha256 FROM proposal_events
           WHERE proposal_id=? ORDER BY sequence DESC LIMIT 1""",
        (proposal_id,),
    ).fetchone()
    sequence = int(previous["sequence"]) + 1 if previous else 1
    previous_hash = str(previous["event_sha256"]) if previous else None
    payload_json = canonical(payload)
    payload_sha = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
    event_material = canonical(
        {
            "schema_version": SCHEMA_VERSION,
            "proposal_id": proposal_id,
            "sequence": sequence,
            "event_type": event_type,
            "recorded_at_utc": recorded_at,
            "previous_event_hash": previous_hash,
            "payload_sha256": payload_sha,
        }
    )
    event_sha = hashlib.sha256(event_material.encode("utf-8")).hexdigest()
    event_id = "ce_" + event_sha
    connection.execute(
        "INSERT INTO proposal_events VALUES(?,?,?,?,?,?,?,?,?)",
        (
            event_id,
            proposal_id,
            sequence,
            event_type,
            recorded_at,
            previous_hash,
            payload_json,
            payload_sha,
            event_sha,
        ),
    )
    connection.execute(
        "UPDATE proposals SET head_event_id=?, updated_at_utc=? WHERE proposal_id=?",
        (event_id, recorded_at, proposal_id),
    )
    return event_id


def _json(value: str | None) -> Any:
    return json.loads(value) if value is not None else None


def _evidence_rows(connection: sqlite3.Connection, proposal_id: str) -> list[dict[str, Any]]:
    rows = connection.execute(
        "SELECT * FROM evidence WHERE proposal_id=? ORDER BY captured_at_utc, evidence_id",
        (proposal_id,),
    ).fetchall()
    return [
        {
            "evidence_id": row["evidence_id"],
            "source_url": row["source_url"],
            "hostname": row["hostname"],
            "source_id": row["source_id"],
            "license_namespace": row["license_namespace"],
            "source_revision": row["source_revision"],
            "raw_sha256": row["raw_sha256"],
            "raw_bytes": row["raw_bytes"],
            "sanitized_text": "[evidence redacted]" if row["redacted"] else row["sanitized_text"],
            "sanitized_sha256": row["sanitized_sha256"],
            "untrusted": True,
            "snapshot_verified": bool(row["snapshot_verified"]),
            "captured_at_utc": row["captured_at_utc"],
            "redacted": bool(row["redacted"]),
        }
        for row in rows
    ]


def _proposal(connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "proposal_id": row["proposal_id"],
        "license_namespace": row["license_namespace"],
        "correction_type": row["correction_type"],
        "state": row["state"],
        "verification_level": row["verification_level"],
        "target": _json(row["target_json"]),
        "original": _json(row["original_json"]),
        "proposed": _json(row["proposed_json"]),
        "source_id": row["source_id"],
        "evidence": _evidence_rows(connection, row["proposal_id"]),
        "validation": _json(row["validation_json"]),
        "local_visibility": row["local_visibility"],
        "head_event_id": row["head_event_id"],
        "created_at_utc": row["created_at_utc"],
        "updated_at_utc": row["updated_at_utc"],
    }


def create_proposal(
    root: Path,
    *,
    correction_type: str,
    target: dict[str, Any],
    original: dict[str, Any] | None,
    proposed: dict[str, Any],
    source_id: str | None,
) -> tuple[dict[str, Any], bool]:
    namespace = correction_policy.namespace_for(source_id)
    fingerprint = _fingerprint(namespace, correction_type, target, proposed)
    connection = _connect(root, namespace, create=True)
    assert connection is not None
    try:
        existing = connection.execute(
            """SELECT * FROM proposals
               WHERE fingerprint=? AND state NOT IN ('withdrawn','superseded')
               ORDER BY created_at_utc LIMIT 1""",
            (fingerprint,),
        ).fetchone()
        if existing:
            return _proposal(connection, existing), False
        proposal_id = "cp_" + uuid.uuid4().hex
        recorded_at = now_z()
        with connection:
            connection.execute(
                "INSERT INTO proposals VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    proposal_id,
                    namespace,
                    correction_type,
                    "draft",
                    "none",
                    canonical(target),
                    canonical(original) if original is not None else None,
                    canonical(proposed),
                    source_id,
                    canonical({"reason_codes": [], "conflicts": []}),
                    "queue_only",
                    fingerprint,
                    recorded_at,
                    recorded_at,
                    None,
                ),
            )
            _append_event(
                connection,
                proposal_id,
                "created",
                {
                    "correction_type": correction_type,
                    "target": target,
                    "original": original,
                    "proposed": proposed,
                    "source_id": source_id,
                    "license_namespace": namespace,
                },
                recorded_at=recorded_at,
            )
        row = connection.execute(
            "SELECT * FROM proposals WHERE proposal_id=?", (proposal_id,)
        ).fetchone()
        assert row is not None
        return _proposal(connection, row), True
    finally:
        connection.close()


def _locate(root: Path, proposal_id: str) -> tuple[str, sqlite3.Connection, sqlite3.Row]:
    if not proposal_id.startswith("cp_") or len(proposal_id) != 35:
        raise CorrectionStoreError("proposal_not_found", "correction proposal not found", 404)
    for namespace in correction_policy.KNOWN_NAMESPACES:
        connection = _connect(root, namespace, create=False)
        if connection is None:
            continue
        row = connection.execute(
            "SELECT * FROM proposals WHERE proposal_id=?", (proposal_id,)
        ).fetchone()
        if row is not None:
            return namespace, connection, row
        connection.close()
    raise CorrectionStoreError("proposal_not_found", "correction proposal not found", 404)


def get_proposal(root: Path, proposal_id: str, *, include_events: bool = False) -> dict[str, Any]:
    _namespace, connection, row = _locate(root, proposal_id)
    try:
        result = _proposal(connection, row)
        if include_events:
            result["events"] = events(connection, proposal_id)
        return result
    finally:
        connection.close()


def events(connection: sqlite3.Connection, proposal_id: str) -> list[dict[str, Any]]:
    rows = connection.execute(
        "SELECT * FROM proposal_events WHERE proposal_id=? ORDER BY sequence", (proposal_id,)
    ).fetchall()
    return [
        {
            "schema_version": SCHEMA_VERSION,
            "event_id": row["event_id"],
            "proposal_id": row["proposal_id"],
            "sequence": row["sequence"],
            "event_type": row["event_type"],
            "recorded_at_utc": row["recorded_at_utc"],
            "previous_event_hash": row["previous_event_hash"],
            "payload": _json(row["payload_json"]),
            "payload_sha256": row["payload_sha256"],
            "event_sha256": row["event_sha256"],
        }
        for row in rows
    ]


def list_proposals(
    root: Path,
    *,
    state: str | None = None,
    match_id: str | None = None,
    accepted_only: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for namespace in correction_policy.KNOWN_NAMESPACES:
        connection = _connect(root, namespace, create=False)
        if connection is None:
            continue
        try:
            rows = connection.execute(
                "SELECT * FROM proposals ORDER BY updated_at_utc DESC"
            ).fetchall()
            for row in rows:
                item = _proposal(connection, row)
                if state and item["state"] != state:
                    continue
                if accepted_only and item["state"] not in {
                    "accepted_local",
                    "exported",
                    "submitted",
                }:
                    continue
                if match_id and item["target"].get("match_id") != match_id:
                    continue
                items.append(item)
        finally:
            connection.close()
    items.sort(key=lambda item: (item["updated_at_utc"], item["proposal_id"]), reverse=True)
    total = len(items)
    limit = max(1, min(int(limit), 100))
    offset = max(0, int(offset))
    return {
        "schema_version": SCHEMA_VERSION,
        "items": items[offset : offset + limit],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def revise_draft(
    root: Path, proposal_id: str, proposed: dict[str, Any], expected_head_event_id: str
) -> dict[str, Any]:
    _namespace, connection, row = _locate(root, proposal_id)
    try:
        if row["state"] not in {"draft", "evidence_attached", "validated_candidate", "conflict"}:
            raise CorrectionStoreError(
                "proposal_not_editable", "this proposal can no longer be edited"
            )
        if row["head_event_id"] != expected_head_event_id:
            raise CorrectionStoreError("proposal_changed", "proposal changed in another view")
        next_state = "evidence_attached" if _evidence_rows(connection, proposal_id) else "draft"
        recorded_at = now_z()
        fingerprint = _fingerprint(
            row["license_namespace"], row["correction_type"], _json(row["target_json"]), proposed
        )
        with connection:
            connection.execute(
                """UPDATE proposals
                   SET proposed_json=?, state=?, verification_level='none',
                       validation_json=?, local_visibility='queue_only', fingerprint=?
                   WHERE proposal_id=?""",
                (
                    canonical(proposed),
                    next_state,
                    canonical({"reason_codes": [], "conflicts": []}),
                    fingerprint,
                    proposal_id,
                ),
            )
            _append_event(
                connection,
                proposal_id,
                "draft_revised",
                {"proposed": proposed, "validation_reset": True},
                recorded_at=recorded_at,
            )
        fresh = connection.execute(
            "SELECT * FROM proposals WHERE proposal_id=?", (proposal_id,)
        ).fetchone()
        assert fresh is not None
        return _proposal(connection, fresh)
    finally:
        connection.close()


def _atomic_raw(root: Path, namespace: str, digest: str, raw: bytes) -> Path:
    folder = Path(root) / namespace / "evidence"
    folder.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(folder, 0o700)
    except OSError:
        pass
    target = folder / f"{digest}.txt"
    if target.exists():
        if target.is_symlink() or not target.is_file():
            raise CorrectionStoreError(
                "evidence_path_unsafe", "stored evidence is not a safe regular file", 503
            )
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise CorrectionStoreError(
                "evidence_hash_mismatch", "stored evidence hash mismatch", 503
            )
        return target
    with tempfile.NamedTemporaryFile(dir=folder, prefix=".evidence-", delete=False) as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    try:
        os.chmod(temporary, 0o600)
    except OSError:
        pass
    os.replace(temporary, target)
    return target


def attach_evidence(
    root: Path,
    proposal_id: str,
    *,
    source_url: str,
    hostname: str,
    source_revision: str | None,
    raw: bytes,
    evidence_receipt: dict[str, Any],
    research_origin: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], bool]:
    namespace, connection, row = _locate(root, proposal_id)
    try:
        if row["state"] in {"withdrawn", "superseded", "submitted"}:
            raise CorrectionStoreError(
                "proposal_not_editable", "this proposal cannot receive evidence"
            )
        count = int(
            connection.execute(
                "SELECT COUNT(*) FROM evidence WHERE proposal_id=?", (proposal_id,)
            ).fetchone()[0]
        )
        if count >= 10:
            raise CorrectionStoreError(
                "too_many_evidence_items", "a proposal can retain at most 10 evidence items", 422
            )
        digest = str(evidence_receipt["raw_sha256"])
        existing = connection.execute(
            """SELECT evidence_id FROM evidence
               WHERE proposal_id=? AND raw_sha256=? AND source_url=?""",
            (proposal_id, digest, source_url),
        ).fetchone()
        if existing:
            return _proposal(connection, row), False
        _atomic_raw(root, namespace, digest, raw)
        evidence_id = (
            "ev_" + hashlib.sha256(f"{proposal_id}\n{source_url}\n{digest}".encode()).hexdigest()
        )
        recorded_at = now_z()
        with connection:
            connection.execute(
                """INSERT INTO evidence(
                    evidence_id, proposal_id, source_url, hostname, source_id,
                    license_namespace, source_revision, raw_sha256, raw_bytes,
                    sanitized_text, sanitized_sha256, snapshot_verified,
                    captured_at_utc, redacted
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,0)""",
                (
                    evidence_id,
                    proposal_id,
                    source_url,
                    hostname,
                    row["source_id"] or "unregistered",
                    namespace,
                    source_revision,
                    digest,
                    evidence_receipt["raw_bytes"],
                    evidence_receipt["sanitized_text"],
                    evidence_receipt["sanitized_sha256"],
                    0,
                    recorded_at,
                ),
            )
            connection.execute(
                """UPDATE proposals
                   SET state='evidence_attached', verification_level='none',
                       validation_json=?, local_visibility='queue_only'
                   WHERE proposal_id=?""",
                (canonical({"reason_codes": [], "conflicts": []}), proposal_id),
            )
            event_payload = {
                "evidence_id": evidence_id,
                "source_url": source_url,
                "raw_sha256": digest,
                "raw_bytes": evidence_receipt["raw_bytes"],
                "untrusted": True,
            }
            if research_origin is not None:
                event_payload["research_origin"] = research_origin
            _append_event(
                connection,
                proposal_id,
                "evidence_imported_from_research"
                if research_origin is not None
                else "evidence_attached",
                event_payload,
                recorded_at=recorded_at,
            )
        fresh = connection.execute(
            "SELECT * FROM proposals WHERE proposal_id=?", (proposal_id,)
        ).fetchone()
        assert fresh is not None
        return _proposal(connection, fresh), True
    finally:
        connection.close()


def raw_evidence(root: Path, proposal_id: str) -> list[tuple[dict[str, Any], bytes]]:
    namespace, connection, row = _locate(root, proposal_id)
    try:
        result = []
        for item in _evidence_rows(connection, proposal_id):
            if item["redacted"]:
                continue
            path = Path(root) / namespace / "evidence" / f"{item['raw_sha256']}.txt"
            try:
                raw = path.read_bytes()
            except OSError as exc:
                raise CorrectionStoreError(
                    "evidence_unavailable", "captured evidence is unavailable", 503
                ) from exc
            if hashlib.sha256(raw).hexdigest() != item["raw_sha256"]:
                raise CorrectionStoreError(
                    "evidence_hash_mismatch", "captured evidence hash mismatch", 503
                )
            result.append((item, raw))
        return result
    finally:
        connection.close()


def apply_validation(
    root: Path,
    proposal_id: str,
    *,
    state: str,
    verification_level: str,
    reason_codes: list[str],
    conflicts: list[dict[str, Any]],
    snapshot_evidence_ids: list[str],
    expected_head_event_id: str | None = None,
) -> dict[str, Any]:
    _namespace, connection, row = _locate(root, proposal_id)
    try:
        if expected_head_event_id is not None and row["head_event_id"] != expected_head_event_id:
            raise CorrectionStoreError("proposal_changed", "proposal changed in another view")
        if row["state"] in {"withdrawn", "superseded", "submitted"}:
            raise CorrectionStoreError(
                "proposal_not_validatable", "this proposal cannot be validated"
            )
        if state not in {"validated_candidate", "conflict", "evidence_attached"}:
            raise ValueError("invalid validation state")
        event_type = (
            "conflict_detected"
            if state == "conflict"
            else "validation_passed"
            if state == "validated_candidate"
            else "validation_failed"
        )
        recorded_at = now_z()
        validation = {"reason_codes": reason_codes, "conflicts": conflicts}
        with connection:
            connection.execute(
                "UPDATE evidence SET snapshot_verified=0 WHERE proposal_id=?", (proposal_id,)
            )
            if snapshot_evidence_ids:
                placeholders = ",".join("?" for _ in snapshot_evidence_ids)
                connection.execute(
                    f"""UPDATE evidence SET snapshot_verified=1
                        WHERE proposal_id=? AND evidence_id IN ({placeholders})""",
                    (proposal_id, *snapshot_evidence_ids),
                )
            connection.execute(
                """UPDATE proposals
                   SET state=?, verification_level=?, validation_json=?,
                       local_visibility='queue_only' WHERE proposal_id=?""",
                (state, verification_level, canonical(validation), proposal_id),
            )
            _append_event(
                connection,
                proposal_id,
                event_type,
                {"state": state, "verification_level": verification_level, **validation},
                recorded_at=recorded_at,
            )
        fresh = connection.execute(
            "SELECT * FROM proposals WHERE proposal_id=?", (proposal_id,)
        ).fetchone()
        assert fresh is not None
        return _proposal(connection, fresh)
    finally:
        connection.close()


def transition(
    root: Path,
    proposal_id: str,
    *,
    allowed: set[str],
    state: str,
    event_type: str,
    payload: dict[str, Any],
    local_visibility: str | None = None,
    expected_head_event_id: str | None = None,
) -> dict[str, Any]:
    _namespace, connection, row = _locate(root, proposal_id)
    try:
        if row["state"] not in allowed:
            raise CorrectionStoreError(
                "invalid_correction_transition", f"cannot move {row['state']} to {state}"
            )
        if expected_head_event_id is not None and row["head_event_id"] != expected_head_event_id:
            raise CorrectionStoreError("proposal_changed", "proposal changed in another view")
        recorded_at = now_z()
        visibility = local_visibility or row["local_visibility"]
        with connection:
            connection.execute(
                "UPDATE proposals SET state=?, local_visibility=? WHERE proposal_id=?",
                (state, visibility, proposal_id),
            )
            _append_event(connection, proposal_id, event_type, payload, recorded_at=recorded_at)
        fresh = connection.execute(
            "SELECT * FROM proposals WHERE proposal_id=?", (proposal_id,)
        ).fetchone()
        assert fresh is not None
        return _proposal(connection, fresh)
    finally:
        connection.close()


def competing_proposals(root: Path, proposal: dict[str, Any]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    target_json = canonical(proposal["target"])
    placeholders = ",".join("?" for _ in ACTIVE_STATES)
    for namespace in correction_policy.KNOWN_NAMESPACES:
        connection = _connect(root, namespace, create=False)
        if connection is None:
            continue
        try:
            rows = connection.execute(
                f"""SELECT proposal_id, proposed_json FROM proposals
                    WHERE correction_type=? AND target_json=? AND proposal_id<>?
                      AND state IN ({placeholders})""",
                (
                    proposal["correction_type"],
                    target_json,
                    proposal["proposal_id"],
                    *sorted(ACTIVE_STATES),
                ),
            ).fetchall()
            for row in rows:
                proposed = _json(row["proposed_json"])
                if proposed != proposal["proposed"]:
                    found.append(
                        {
                            "reason_code": "competing_local_proposal",
                            "proposal_id": row["proposal_id"],
                            "proposed": proposed,
                        }
                    )
        finally:
            connection.close()
    return sorted(found, key=lambda item: item["proposal_id"])


def record_export(
    root: Path,
    proposal_id: str,
    *,
    source_head_event_id: str,
    export_id: str,
    relative_path: str,
    sha256: str,
    byte_count: int,
) -> dict[str, Any]:
    _namespace, connection, row = _locate(root, proposal_id)
    try:
        recorded_at = now_z()
        with connection:
            connection.execute(
                "INSERT OR IGNORE INTO exports VALUES(?,?,?,?,?,?,?)",
                (
                    export_id,
                    proposal_id,
                    source_head_event_id,
                    relative_path,
                    sha256,
                    byte_count,
                    recorded_at,
                ),
            )
            if row["state"] in {"validated_candidate", "accepted_local"}:
                connection.execute(
                    "UPDATE proposals SET state='exported' WHERE proposal_id=?", (proposal_id,)
                )
                _append_event(
                    connection,
                    proposal_id,
                    "exported",
                    {"export_id": export_id, "sha256": sha256, "bytes": byte_count},
                    recorded_at=recorded_at,
                )
        return {
            "export_id": export_id,
            "proposal_id": proposal_id,
            "proposal_head_event_id": source_head_event_id,
            "relative_path": relative_path,
            "sha256": sha256,
            "bytes": byte_count,
        }
    finally:
        connection.close()


def latest_export(root: Path, proposal_id: str) -> dict[str, Any] | None:
    _namespace, connection, _row = _locate(root, proposal_id)
    try:
        record = connection.execute(
            "SELECT * FROM exports WHERE proposal_id=? ORDER BY created_at_utc DESC LIMIT 1",
            (proposal_id,),
        ).fetchone()
        if record is None:
            return None
        return {
            "export_id": record["export_id"],
            "proposal_id": record["proposal_id"],
            "proposal_head_event_id": record["proposal_head_event_id"],
            "relative_path": record["relative_path"],
            "sha256": record["sha256"],
            "bytes": record["bytes"],
        }
    finally:
        connection.close()


def redact_evidence(
    root: Path,
    proposal_id: str,
    evidence_id: str,
    *,
    expected_head_event_id: str | None = None,
) -> dict[str, Any]:
    namespace, connection, row = _locate(root, proposal_id)
    try:
        if expected_head_event_id is not None and row["head_event_id"] != expected_head_event_id:
            raise CorrectionStoreError("proposal_changed", "proposal changed in another view")
        evidence = connection.execute(
            "SELECT * FROM evidence WHERE proposal_id=? AND evidence_id=?",
            (proposal_id, evidence_id),
        ).fetchone()
        if evidence is None:
            raise CorrectionStoreError("evidence_not_found", "evidence item not found", 404)
        if not evidence["redacted"]:
            export_paths = [
                str(item[0])
                for item in connection.execute(
                    "SELECT relative_path FROM exports WHERE proposal_id=?", (proposal_id,)
                ).fetchall()
            ]
            with connection:
                connection.execute(
                    """UPDATE evidence SET snapshot_verified=0 WHERE proposal_id=?""",
                    (proposal_id,),
                )
                connection.execute(
                    """UPDATE evidence SET redacted=1, sanitized_text=''
                       WHERE evidence_id=?""",
                    (evidence_id,),
                )
                _append_event(
                    connection,
                    proposal_id,
                    "evidence_redacted",
                    {"evidence_id": evidence_id, "raw_sha256": evidence["raw_sha256"]},
                    recorded_at=now_z(),
                )
                remaining = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM evidence WHERE proposal_id=? AND redacted=0",
                        (proposal_id,),
                    ).fetchone()[0]
                )
                next_state = "evidence_attached" if remaining else "draft"
                reasons = [] if remaining else ["source_url_and_captured_evidence_required"]
                connection.execute(
                    """UPDATE proposals
                       SET state=?, verification_level='none', validation_json=?,
                           local_visibility='queue_only' WHERE proposal_id=?""",
                    (
                        next_state,
                        canonical({"reason_codes": reasons, "conflicts": []}),
                        proposal_id,
                    ),
                )
            for relative in export_paths:
                path = Path(root) / relative
                try:
                    if path.is_file() and not path.is_symlink():
                        path.unlink()
                except OSError:
                    pass
            other = connection.execute(
                "SELECT COUNT(*) FROM evidence WHERE raw_sha256=? AND redacted=0",
                (evidence["raw_sha256"],),
            ).fetchone()[0]
            if not other:
                (Path(root) / namespace / "evidence" / f"{evidence['raw_sha256']}.txt").unlink(
                    missing_ok=True
                )
        fresh = connection.execute(
            "SELECT * FROM proposals WHERE proposal_id=?", (proposal_id,)
        ).fetchone()
        assert fresh is not None
        return _proposal(connection, fresh)
    finally:
        connection.close()


def purge(root: Path) -> dict[str, Any]:
    root = Path(root)
    if root.exists():
        shutil.rmtree(root)
    return {"schema_version": SCHEMA_VERSION, "removed": True}
