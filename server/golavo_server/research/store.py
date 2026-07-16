"""License-separated, append-only local storage for research runs and evidence."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

SCHEMA_VERSION = "0.1.0"
KNOWN_NAMESPACES = (
    "core-cc0",
    "enrichment-cc0",
    "enrichment-public-domain",
    "enrichment-cc-by-4.0",
    "research-cc-by-sa-4.0",
)
RUN_STATES = {
    "planned",
    "fetching",
    "captured",
    "extracting",
    "candidates_ready",
    "partial",
    "cancelled",
    "offline",
    "failed",
}
TERMINAL_RUN_STATES = {"candidates_ready", "partial", "cancelled", "offline", "failed"}


class ResearchStoreError(ValueError):
    def __init__(self, reason_code: str, detail: str, status: int = 422) -> None:
        super().__init__(detail)
        self.reason_code = reason_code
        self.detail = detail
        self.status = status


def now_z() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def capture_id_for(
    *,
    run_id: str,
    source_id: str,
    canonical_url: str,
    document_url: str,
    entity_id: str | None,
    raw_sha256: str,
) -> str:
    """Content-address a capture together with its parsed document identity."""
    material = canonical(
        {
            "run_id": run_id,
            "source_id": source_id,
            "canonical_url": canonical_url,
            "document_url": document_url,
            "entity_id": entity_id,
            "raw_sha256": raw_sha256,
        }
    )
    return "rc_" + hashlib.sha256(material.encode("utf-8")).hexdigest()


def _capture_identity_matches(payload: dict[str, Any], raw: bytes) -> bool:
    """Re-bind source-specific raw identity when a receipt is loaded for review."""
    if payload.get("source_id") != "wikidata":
        return True
    try:
        raw_payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return False
    canonical_url = payload.get("canonical_url")
    if not isinstance(canonical_url, str) or not isinstance(raw_payload, dict):
        return False
    qid = urlsplit(canonical_url).path.rstrip("/").rsplit("/", 1)[-1]
    return (
        raw_payload.get("id") == qid
        and payload.get("entity_id") == qid
        and payload.get("document_url") == f"https://www.wikidata.org/wiki/{qid}"
    )


def _secure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, 0o700)
    except OSError:
        pass


def _connect(path: Path) -> sqlite3.Connection:
    _secure_dir(path.parent)
    if path.exists() and (path.is_symlink() or not path.is_file()):
        raise ResearchStoreError("unsafe_store_path", "research store is not a safe file", 503)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA journal_mode=WAL")
    return connection


def _control(root: Path) -> sqlite3.Connection:
    connection = _connect(Path(root) / "control.sqlite3")
    connection.execute(
        """CREATE TABLE IF NOT EXISTS runs(
            run_id TEXT PRIMARY KEY,
            match_id TEXT NOT NULL,
            index_fingerprint TEXT NOT NULL,
            state TEXT NOT NULL,
            selected_urls_json TEXT NOT NULL,
            allow_local_ai INTEGER NOT NULL,
            counts_json TEXT NOT NULL,
            reasons_json TEXT NOT NULL,
            created_at_utc TEXT NOT NULL,
            updated_at_utc TEXT NOT NULL
        )"""
    )
    connection.commit()
    return connection


def _namespace(root: Path, namespace: str) -> sqlite3.Connection:
    if namespace not in KNOWN_NAMESPACES:
        raise ResearchStoreError("unknown_license_namespace", "unknown research namespace")
    folder = Path(root) / namespace
    connection = _connect(folder / "research.sqlite3")
    connection.execute(
        """CREATE TABLE IF NOT EXISTS captures(
            capture_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            raw_sha256 TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at_utc TEXT NOT NULL
        )"""
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS candidates(
            candidate_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            capture_id TEXT NOT NULL,
            state TEXT NOT NULL,
            queued_proposal_id TEXT,
            payload_json TEXT NOT NULL,
            created_at_utc TEXT NOT NULL
        )"""
    )
    connection.execute("CREATE INDEX IF NOT EXISTS candidates_run ON candidates(run_id)")
    connection.commit()
    return connection


def create_run(
    root: Path,
    *,
    match_id: str,
    index_fingerprint: str,
    selected_urls: list[str],
    allow_local_ai: bool,
    generation_commit: Callable[[Callable[[], None]], bool] | None = None,
) -> dict[str, Any]:
    if not 1 <= len(selected_urls) <= 4 or len(set(selected_urls)) != len(selected_urls):
        raise ResearchStoreError("invalid_selected_urls", "select one to four unique URLs")
    run_id = "rr_" + uuid.uuid4().hex
    recorded = now_z()
    counts = {"selected": len(selected_urls), "captured": 0, "candidates": 0, "failed": 0}
    connection = _control(root)
    try:
        # One match owns at most one non-terminal research run. The UI carries
        # its own immediate click lock, but the local API is still a trust
        # boundary: two concurrent POSTs must not create two workers and two
        # sets of immutable captures. BEGIN IMMEDIATE serializes the active-run
        # check and insert without preventing a later explicit rerun once the
        # first reaches a terminal state.
        connection.execute("BEGIN IMMEDIATE")
        terminals = sorted(TERMINAL_RUN_STATES)
        placeholders = ",".join("?" for _ in terminals)
        active = connection.execute(
            f"SELECT run_id FROM runs WHERE match_id=? AND state NOT IN ({placeholders}) "
            "ORDER BY created_at_utc, run_id LIMIT 1",
            (match_id, *terminals),
        ).fetchone()
        if active is not None:
            if generation_commit is not None and not generation_commit(connection.commit):
                raise ResearchStoreError(
                    "index_generation_changed",
                    "verified match index changed before the active run was returned; retry",
                    409,
                )
            if generation_commit is None:
                connection.commit()
            raise ResearchStoreError(
                "research_run_active",
                f"a research run is already active for this match ({active['run_id']})",
                409,
            )
        connection.execute(
            "INSERT INTO runs VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                run_id,
                match_id,
                index_fingerprint,
                "planned",
                canonical(selected_urls),
                int(allow_local_ai),
                canonical(counts),
                "[]",
                recorded,
                recorded,
            ),
        )
        if generation_commit is not None and not generation_commit(connection.commit):
            raise ResearchStoreError(
                "index_generation_changed",
                "verified match index changed before the research run was committed; retry",
                409,
            )
        if generation_commit is None:
            connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return get_run(root, run_id)


def _run(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": row["run_id"],
        "match_id": row["match_id"],
        "index_fingerprint": row["index_fingerprint"],
        "state": row["state"],
        "selected_urls": json.loads(row["selected_urls_json"]),
        "allow_local_ai": bool(row["allow_local_ai"]),
        "counts": json.loads(row["counts_json"]),
        "reason_codes": json.loads(row["reasons_json"]),
        "created_at_utc": row["created_at_utc"],
        "updated_at_utc": row["updated_at_utc"],
    }


def get_run(root: Path, run_id: str) -> dict[str, Any]:
    connection = _control(root)
    try:
        row = connection.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
        if row is None:
            raise ResearchStoreError("run_not_found", "research run not found", 404)
        return _run(row)
    finally:
        connection.close()


def list_runs(root: Path, *, match_id: str, limit: int = 10) -> list[dict[str, Any]]:
    connection = _control(root)
    try:
        rows = connection.execute(
            """SELECT * FROM runs WHERE match_id=?
               ORDER BY created_at_utc DESC, run_id DESC LIMIT ?""",
            (match_id, max(1, min(limit, 50))),
        ).fetchall()
        return [_run(row) for row in rows]
    finally:
        connection.close()


def update_run(
    root: Path,
    run_id: str,
    *,
    state: str,
    counts: dict[str, int] | None = None,
    reason_codes: list[str] | None = None,
) -> dict[str, Any]:
    if state not in RUN_STATES:
        raise ResearchStoreError("invalid_run_state", "invalid research run state")
    connection = _control(root)
    try:
        row = connection.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
        if row is None:
            raise ResearchStoreError("run_not_found", "research run not found", 404)
        if row["state"] in TERMINAL_RUN_STATES and state != row["state"]:
            return _run(row)
        next_counts = counts if counts is not None else json.loads(row["counts_json"])
        reasons = sorted(set(reason_codes or json.loads(row["reasons_json"])))
        with connection:
            connection.execute(
                """UPDATE runs
                   SET state=?, counts_json=?, reasons_json=?, updated_at_utc=?
                   WHERE run_id=?""",
                (state, canonical(next_counts), canonical(reasons), now_z(), run_id),
            )
        fresh = connection.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
        assert fresh is not None
        return _run(fresh)
    finally:
        connection.close()


def _atomic_capture(root: Path, namespace: str, digest: str, raw: bytes) -> None:
    folder = Path(root) / namespace / "captures"
    _secure_dir(folder)
    target = folder / f"{digest}.bin"
    if target.exists():
        if target.is_symlink() or hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise ResearchStoreError(
                "capture_hash_mismatch", "stored research capture is unsafe", 503
            )
        return
    with tempfile.NamedTemporaryFile(dir=folder, prefix=".capture-", delete=False) as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    try:
        os.chmod(temporary, 0o600)
    except OSError:
        pass
    os.replace(temporary, target)


def add_capture(root: Path, payload: dict[str, Any], raw: bytes) -> tuple[dict[str, Any], bool]:
    namespace = str(payload["license_namespace"])
    digest = hashlib.sha256(raw).hexdigest()
    if payload.get("raw_sha256") != digest or payload.get("raw_bytes") != len(raw):
        raise ResearchStoreError("capture_receipt_mismatch", "capture bytes do not match receipt")
    _atomic_capture(root, namespace, digest, raw)
    connection = _namespace(root, namespace)
    try:
        existing = connection.execute(
            "SELECT payload_json FROM captures WHERE capture_id=?", (payload["capture_id"],)
        ).fetchone()
        if existing:
            return json.loads(existing["payload_json"]), False
        with connection:
            connection.execute(
                "INSERT INTO captures VALUES(?,?,?,?,?)",
                (payload["capture_id"], payload["run_id"], digest, canonical(payload), now_z()),
            )
        return payload, True
    finally:
        connection.close()


def add_candidate(
    root: Path, namespace: str, payload: dict[str, Any]
) -> tuple[dict[str, Any], bool]:
    connection = _namespace(root, namespace)
    try:
        existing = connection.execute(
            "SELECT payload_json FROM candidates WHERE candidate_id=?", (payload["candidate_id"],)
        ).fetchone()
        if existing:
            return json.loads(existing["payload_json"]), False
        with connection:
            connection.execute(
                "INSERT INTO candidates VALUES(?,?,?,?,?,?,?)",
                (
                    payload["candidate_id"],
                    payload["run_id"],
                    payload["evidence"]["capture_id"],
                    payload["state"],
                    None,
                    canonical(payload),
                    payload["created_at_utc"],
                ),
            )
        return payload, True
    finally:
        connection.close()


def _candidate_row(root: Path, candidate_id: str) -> tuple[str, sqlite3.Connection, sqlite3.Row]:
    for namespace in KNOWN_NAMESPACES:
        path = Path(root) / namespace / "research.sqlite3"
        if not path.is_file():
            continue
        connection = _namespace(root, namespace)
        row = connection.execute(
            "SELECT * FROM candidates WHERE candidate_id=?", (candidate_id,)
        ).fetchone()
        if row is not None:
            return namespace, connection, row
        connection.close()
    raise ResearchStoreError("candidate_not_found", "research candidate not found", 404)


def get_candidate(root: Path, candidate_id: str) -> dict[str, Any]:
    _namespace_name, connection, row = _candidate_row(root, candidate_id)
    try:
        return json.loads(row["payload_json"])
    finally:
        connection.close()


def get_candidate_record(root: Path, candidate_id: str) -> tuple[str, dict[str, Any]]:
    namespace, connection, row = _candidate_row(root, candidate_id)
    try:
        return namespace, json.loads(row["payload_json"])
    finally:
        connection.close()


def load_capture(root: Path, namespace: str, capture_id: str) -> tuple[dict[str, Any], bytes]:
    connection = _namespace(root, namespace)
    try:
        row = connection.execute(
            "SELECT * FROM captures WHERE capture_id=?", (capture_id,)
        ).fetchone()
        if row is None:
            raise ResearchStoreError("capture_not_found", "research capture not found", 404)
        payload = json.loads(row["payload_json"])
    finally:
        connection.close()
    raw_path = Path(root) / namespace / "captures" / f"{row['raw_sha256']}.bin"
    if raw_path.is_symlink() or not raw_path.is_file():
        raise ResearchStoreError("capture_unavailable", "research capture is unavailable", 503)
    raw = raw_path.read_bytes()
    raw_sha = hashlib.sha256(raw).hexdigest()
    text = payload.get("canonical_text")
    document_url = payload.get("document_url")
    entity_id = payload.get("entity_id")
    if (
        raw_sha != row["raw_sha256"]
        or payload.get("raw_sha256") != raw_sha
        or payload.get("raw_bytes") != len(raw)
        or not isinstance(text, str)
        or not isinstance(document_url, str)
        or not document_url
        or (entity_id is not None and not isinstance(entity_id, str))
        or payload.get("canonical_text_sha256") != hashlib.sha256(text.encode("utf-8")).hexdigest()
        or not _capture_identity_matches(payload, raw)
    ):
        raise ResearchStoreError(
            "capture_hash_mismatch", "research capture failed verification", 503
        )
    expected_id = capture_id_for(
        run_id=str(payload.get("run_id") or ""),
        source_id=str(payload.get("source_id") or ""),
        canonical_url=str(payload.get("canonical_url") or ""),
        document_url=document_url,
        entity_id=entity_id,
        raw_sha256=raw_sha,
    )
    if payload.get("capture_id") != expected_id or capture_id != expected_id:
        raise ResearchStoreError("capture_id_mismatch", "research capture identity mismatch", 503)
    return payload, raw


def list_candidates(root: Path, run_id: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for namespace in KNOWN_NAMESPACES:
        path = Path(root) / namespace / "research.sqlite3"
        if not path.is_file():
            continue
        connection = _namespace(root, namespace)
        try:
            rows = connection.execute(
                """SELECT payload_json FROM candidates
                   WHERE run_id=? ORDER BY created_at_utc, candidate_id""",
                (run_id,),
            ).fetchall()
            result.extend(json.loads(row["payload_json"]) for row in rows)
        finally:
            connection.close()
    return sorted(result, key=lambda value: (value["created_at_utc"], value["candidate_id"]))


def mark_queued(
    root: Path,
    candidate_id: str,
    proposal_id: str,
    *,
    generation_commit: Callable[[Callable[[], None]], bool] | None = None,
) -> dict[str, Any]:
    _namespace_name, connection, row = _candidate_row(root, candidate_id)
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT * FROM candidates WHERE candidate_id=?", (candidate_id,)
        ).fetchone()
        assert row is not None
        payload = json.loads(row["payload_json"])
        existing = payload.get("queued_proposal_id")
        if existing and existing != proposal_id:
            raise ResearchStoreError(
                "candidate_already_queued", "candidate was already queued", 409
            )
        payload["state"] = "queued_as_draft"
        payload["queued_proposal_id"] = proposal_id
        connection.execute(
            """UPDATE candidates
               SET state='queued_as_draft', queued_proposal_id=?, payload_json=?
               WHERE candidate_id=?""",
            (proposal_id, canonical(payload), candidate_id),
        )
        if generation_commit is not None and not generation_commit(connection.commit):
            raise ResearchStoreError(
                "index_generation_changed",
                "verified match index changed before the candidate was queued; retry",
                409,
            )
        if generation_commit is None:
            connection.commit()
        return payload
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def prune(root: Path, retention_days: int, *, now: datetime | None = None) -> dict[str, int]:
    """Remove expired unqueued runs while retaining every queued research receipt."""
    if not 1 <= retention_days <= 90:
        raise ResearchStoreError("invalid_retention", "retention must be between 1 and 90 days")
    path = Path(root)
    if not (path / "control.sqlite3").is_file():
        return {"runs": 0, "candidates": 0, "captures": 0, "raw_blobs": 0}
    protected: set[str] = set()
    for namespace in KNOWN_NAMESPACES:
        database = path / namespace / "research.sqlite3"
        if not database.is_file():
            continue
        connection = _namespace(path, namespace)
        try:
            rows = connection.execute(
                "SELECT DISTINCT run_id FROM candidates WHERE queued_proposal_id IS NOT NULL"
            ).fetchall()
            protected.update(str(row["run_id"]) for row in rows)
        finally:
            connection.close()
    cutoff = (now or datetime.now(UTC)) - timedelta(days=retention_days)
    cutoff_z = cutoff.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    control = _control(path)
    try:
        rows = control.execute(
            "SELECT run_id FROM runs WHERE updated_at_utc < ?", (cutoff_z,)
        ).fetchall()
        expired = {str(row["run_id"]) for row in rows} - protected
        if not expired:
            return {"runs": 0, "candidates": 0, "captures": 0, "raw_blobs": 0}
        placeholders = ",".join("?" for _ in expired)
        counts = {"runs": len(expired), "candidates": 0, "captures": 0, "raw_blobs": 0}
        ordered = sorted(expired)
        for namespace in KNOWN_NAMESPACES:
            database = path / namespace / "research.sqlite3"
            if not database.is_file():
                continue
            connection = _namespace(path, namespace)
            try:
                capture_rows = connection.execute(
                    f"SELECT raw_sha256 FROM captures WHERE run_id IN ({placeholders})",
                    ordered,
                ).fetchall()
                with connection:
                    cursor = connection.execute(
                        f"DELETE FROM candidates WHERE run_id IN ({placeholders})", ordered
                    )
                    counts["candidates"] += cursor.rowcount
                    cursor = connection.execute(
                        f"DELETE FROM captures WHERE run_id IN ({placeholders})", ordered
                    )
                    counts["captures"] += cursor.rowcount
                for row in capture_rows:
                    digest = str(row["raw_sha256"])
                    remaining = connection.execute(
                        "SELECT COUNT(*) FROM captures WHERE raw_sha256=?", (digest,)
                    ).fetchone()[0]
                    if not remaining:
                        raw_path = path / namespace / "captures" / f"{digest}.bin"
                        if raw_path.is_file() and not raw_path.is_symlink():
                            raw_path.unlink()
                            counts["raw_blobs"] += 1
            finally:
                connection.close()
        with control:
            control.execute(f"DELETE FROM runs WHERE run_id IN ({placeholders})", ordered)
        return counts
    finally:
        control.close()


def purge(root: Path) -> dict[str, Any]:
    path = Path(root)
    if not path.exists():
        return {"removed": False}
    if path.is_symlink() or not path.is_dir():
        raise ResearchStoreError("unsafe_store_path", "research root is not a safe directory", 503)
    settings_path = path / "settings.json"
    settings_bytes: bytes | None = None
    if settings_path.is_file() and not settings_path.is_symlink():
        settings_bytes = settings_path.read_bytes()
    shutil.rmtree(path)
    if settings_bytes is not None:
        _secure_dir(path)
        temporary = path / ".settings-restore"
        temporary.write_bytes(settings_bytes)
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            pass
        os.replace(temporary, settings_path)
    return {"removed": True, "settings_preserved": settings_bytes is not None}
