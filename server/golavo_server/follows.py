"""Durable, local-only followed-match subscriptions and event history.

The store lives under the mutable forecast ledger so the desktop updater backs
it up with the user's seals and picks. Only approved CC0 match-index identities
may enter this database; OpenLigaDB remains in its physically isolated overlay.
Following and reconciliation never write a forecast artifact.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from golavo_server import refresh_sources

SCHEMA_VERSION = "0.1.0"
DATABASE_VERSION = 1
NAMESPACE = "core-cc0"
DATABASE_NAME = "follows.sqlite3"

EVENT_TYPES = {
    "followed",
    "unfollowed",
    "refollowed",
    "match_repointed",
    "identity_unresolved",
    "kickoff_changed",
    "venue_changed",
    "score_published",
    "settlement_available",
    "settlement_recorded",
    "source_revision_available",
    "source_conflict",
    "source_unavailable",
    "source_recovered",
}
NOTIFICATION_STATUSES = {
    "not_eligible",
    "pending",
    "claimed",
    "submitted",
    "suppressed_visible",
    "permission_denied",
    "failed",
}
NOTIFIABLE_EVENTS = EVENT_TYPES - {"followed", "unfollowed", "refollowed"}

# Only this adapter currently emits a source-owned identifier whose contract is
# stable across a schedule edit (the World Cup match number). Date/team-derived
# keys are deliberately excluded.
STABLE_UPSTREAM_KEY_SOURCES = {refresh_sources.WORLDCUP}


class FollowError(Exception):
    def __init__(self, reason_code: str, detail: str, status_code: int = 409) -> None:
        super().__init__(detail)
        self.reason_code = reason_code
        self.detail = detail
        self.status_code = status_code


def _now_z(now: datetime | None = None) -> str:
    value = now or datetime.now(UTC)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _database_path(ledger: Path) -> Path:
    return Path(ledger) / "follows" / DATABASE_NAME


def _connect(ledger: Path, *, create: bool) -> sqlite3.Connection | None:
    path = _database_path(ledger)
    if not path.exists() and not create:
        return None
    if create:
        path.parent.mkdir(parents=True, exist_ok=True)
    try:
        connection = sqlite3.connect(path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = DELETE")
        connection.execute("PRAGMA synchronous = FULL")
        _migrate(connection)
        check = connection.execute("PRAGMA quick_check").fetchone()
        if check is None or check[0] != "ok":
            connection.close()
            raise FollowError(
                "follow_store_unavailable",
                "follow history failed its integrity check; the original database was preserved",
                503,
            )
        return connection
    except FollowError:
        raise
    except (OSError, sqlite3.DatabaseError) as exc:
        raise FollowError(
            "follow_store_unavailable",
            f"follow history is unavailable; the original database was preserved: {exc}",
            503,
        ) from exc


def _migrate(connection: sqlite3.Connection) -> None:
    version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if version > DATABASE_VERSION:
        raise FollowError(
            "follow_store_newer_version",
            "follow history was created by a newer Golavo version",
            503,
        )
    if version == DATABASE_VERSION:
        return
    if version != 0:
        raise FollowError("follow_store_unavailable", "unsupported follow database version", 503)
    with connection:
        connection.executescript(
            """
            CREATE TABLE followed_matches (
                follow_id TEXT PRIMARY KEY,
                namespace TEXT NOT NULL CHECK(namespace = 'core-cc0'),
                subscription_state TEXT NOT NULL
                    CHECK(subscription_state IN ('active','unfollowed')),
                resolution_state TEXT NOT NULL
                    CHECK(resolution_state IN ('resolved','identity_unresolved')),
                data_state TEXT NOT NULL
                    CHECK(data_state IN (
                        'current','stale','source_conflict','source_unavailable','completed'
                    )),
                canonical_match_id TEXT NOT NULL,
                identity_source_id TEXT NOT NULL,
                upstream_fixture_key TEXT,
                initial_snapshot_json TEXT NOT NULL,
                current_snapshot_json TEXT NOT NULL,
                last_generation_id TEXT,
                last_index_fingerprint TEXT,
                created_at_utc TEXT NOT NULL,
                updated_at_utc TEXT NOT NULL,
                unfollowed_at_utc TEXT,
                last_observed_at_utc TEXT
            );
            CREATE UNIQUE INDEX one_active_follow_per_match
                ON followed_matches(namespace, canonical_match_id)
                WHERE subscription_state = 'active';
            CREATE INDEX followed_matches_state
                ON followed_matches(subscription_state, updated_at_utc DESC);

            CREATE TABLE follow_identities (
                follow_id TEXT NOT NULL REFERENCES followed_matches(follow_id) ON DELETE CASCADE,
                identity_kind TEXT NOT NULL
                    CHECK(identity_kind IN ('match_id','upstream_fixture_key')),
                identity_value TEXT NOT NULL,
                source_id TEXT NOT NULL,
                first_seen_at_utc TEXT NOT NULL,
                last_seen_at_utc TEXT NOT NULL,
                PRIMARY KEY(follow_id, identity_kind, identity_value)
            );

            CREATE TABLE follow_events (
                event_id TEXT PRIMARY KEY,
                follow_id TEXT NOT NULL REFERENCES followed_matches(follow_id) ON DELETE CASCADE,
                event_type TEXT NOT NULL,
                detected_at_utc TEXT NOT NULL,
                effective_at_utc TEXT,
                source_id TEXT NOT NULL,
                source_ref TEXT,
                source_checked_at_utc TEXT,
                generation_id TEXT,
                before_json TEXT,
                after_json TEXT,
                conflict_json TEXT,
                read_at_utc TEXT,
                notification_status TEXT NOT NULL,
                notification_batch_id TEXT,
                notification_updated_at_utc TEXT,
                notification_error TEXT
            );
            CREATE INDEX follow_events_feed
                ON follow_events(follow_id, detected_at_utc DESC, event_id DESC);
            CREATE INDEX follow_events_unread
                ON follow_events(read_at_utc, detected_at_utc DESC);
            CREATE INDEX follow_events_notification
                ON follow_events(notification_status, detected_at_utc);

            CREATE TABLE follow_settings (
                settings_id INTEGER PRIMARY KEY CHECK(settings_id = 1),
                notifications_opt_in INTEGER NOT NULL CHECK(notifications_opt_in IN (0,1)),
                created_at_utc TEXT NOT NULL,
                updated_at_utc TEXT NOT NULL
            );
            PRAGMA user_version = 1;
            """
        )


def _snapshot(match: dict[str, Any]) -> dict[str, Any]:
    source_id = match.get("source_id")
    if source_id not in refresh_sources.APPROVED_SOURCE_IDS:
        raise FollowError(
            "unsupported_follow_source",
            "only approved core CC0 fixtures can be followed in this release",
            422,
        )
    fields = (
        "match_id",
        "kickoff_utc",
        "kickoff_precision",
        "home_team",
        "away_team",
        "home_score",
        "away_score",
        "competition",
        "country",
        "city",
        "neutral",
        "is_complete",
        "source_kind",
        "source_id",
        "upstream_fixture_key",
        "provenance",
    )
    return {field: match.get(field) for field in fields}


def _source_details(
    snapshot: dict[str, Any],
    field: str,
    source_status: dict[str, dict[str, Any]] | None,
) -> tuple[str, str | None, str | None]:
    provenance = snapshot.get("provenance")
    source_id = (
        provenance.get(field)
        if isinstance(provenance, dict) and isinstance(provenance.get(field), str)
        else snapshot["source_id"]
    )
    status = (source_status or {}).get(source_id, {})
    source_ref = status.get("active_ref") or status.get("observed_ref")
    checked_at = status.get("last_checked_at_utc")
    return source_id, source_ref, checked_at


def _event_id(
    follow_id: str,
    event_type: str,
    source_id: str,
    source_ref: str | None,
    generation_id: str | None,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    conflict: dict[str, Any] | None,
) -> str:
    material = "\n".join(
        (
            SCHEMA_VERSION,
            follow_id,
            event_type,
            source_id,
            source_ref or generation_id or "local",
            _canonical(before),
            _canonical(after),
            _canonical(conflict),
        )
    )
    return "fe_" + hashlib.sha256(material.encode("utf-8")).hexdigest()


def _insert_event(
    connection: sqlite3.Connection,
    *,
    follow_id: str,
    event_type: str,
    source_id: str,
    source_ref: str | None,
    source_checked_at_utc: str | None,
    generation_id: str | None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    conflict: dict[str, Any] | None = None,
    effective_at_utc: str | None = None,
    detected_at_utc: str,
) -> str | None:
    if event_type not in EVENT_TYPES:
        raise ValueError(f"unknown follow event type: {event_type}")
    event_id = _event_id(
        follow_id,
        event_type,
        source_id,
        source_ref,
        generation_id,
        before,
        after,
        conflict,
    )
    opted = connection.execute(
        "SELECT notifications_opt_in FROM follow_settings WHERE settings_id=1"
    ).fetchone()
    notification = (
        "pending"
        if event_type in NOTIFIABLE_EVENTS and opted is not None and bool(opted[0])
        else "not_eligible"
    )
    cursor = connection.execute(
        """
        INSERT OR IGNORE INTO follow_events(
            event_id, follow_id, event_type, detected_at_utc, effective_at_utc,
            source_id, source_ref, source_checked_at_utc, generation_id,
            before_json, after_json, conflict_json, notification_status
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            event_id,
            follow_id,
            event_type,
            detected_at_utc,
            effective_at_utc,
            source_id,
            source_ref,
            source_checked_at_utc,
            generation_id,
            _canonical(before) if before is not None else None,
            _canonical(after) if after is not None else None,
            _canonical(conflict) if conflict is not None else None,
            notification,
        ),
    )
    return event_id if cursor.rowcount else None


def _identity(
    connection: sqlite3.Connection,
    follow_id: str,
    kind: str,
    value: str | None,
    source_id: str,
    now: str,
) -> None:
    if not value:
        return
    connection.execute(
        """
        INSERT INTO follow_identities(
            follow_id, identity_kind, identity_value, source_id,
            first_seen_at_utc, last_seen_at_utc
        ) VALUES(?,?,?,?,?,?)
        ON CONFLICT(follow_id, identity_kind, identity_value)
        DO UPDATE SET last_seen_at_utc=excluded.last_seen_at_utc
        """,
        (follow_id, kind, value, source_id, now, now),
    )


def _json(value: str | None) -> Any:
    return json.loads(value) if value is not None else None


def _resolved_artifact_ids(ledger: Path) -> set[str]:
    resolved: set[str] = set()
    for path in sorted(Path(ledger).glob("fa_*.json")):
        try:
            artifact = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            continue
        supersedes = artifact.get("supersedes") if isinstance(artifact, dict) else None
        if isinstance(supersedes, str) and supersedes:
            resolved.add(supersedes)
    return resolved


def _event_view(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "event_id": row["event_id"],
        "follow_id": row["follow_id"],
        "event_type": row["event_type"],
        "detected_at_utc": row["detected_at_utc"],
        "effective_at_utc": row["effective_at_utc"],
        "source": {
            "source_id": row["source_id"],
            "source_ref": row["source_ref"],
            "checked_at_utc": row["source_checked_at_utc"],
        },
        "generation_id": row["generation_id"],
        "before": _json(row["before_json"]),
        "after": _json(row["after_json"]),
        "conflict": _json(row["conflict_json"]),
        "read_at_utc": row["read_at_utc"],
        "notification_status": row["notification_status"],
    }


def _follow_view(
    connection: sqlite3.Connection, row: sqlite3.Row, *, event_limit: int
) -> dict[str, Any]:
    events = connection.execute(
        """
        SELECT * FROM follow_events WHERE follow_id=?
        ORDER BY detected_at_utc DESC, rowid DESC LIMIT ?
        """,
        (row["follow_id"], event_limit),
    ).fetchall()
    unread = connection.execute(
        "SELECT COUNT(*) FROM follow_events WHERE follow_id=? AND read_at_utc IS NULL",
        (row["follow_id"],),
    ).fetchone()[0]
    return {
        "schema_version": SCHEMA_VERSION,
        "follow_id": row["follow_id"],
        "namespace": row["namespace"],
        "subscription_state": row["subscription_state"],
        "resolution_state": row["resolution_state"],
        "data_state": row["data_state"],
        "canonical_match_id": row["canonical_match_id"],
        "identity_source_id": row["identity_source_id"],
        "upstream_fixture_key": row["upstream_fixture_key"],
        "created_at_utc": row["created_at_utc"],
        "updated_at_utc": row["updated_at_utc"],
        "unfollowed_at_utc": row["unfollowed_at_utc"],
        "last_observed_at_utc": row["last_observed_at_utc"],
        "current": _json(row["current_snapshot_json"]),
        "unread_event_count": int(unread),
        "events": [_event_view(event) for event in events],
    }


def follow_match(
    match: dict[str, Any],
    *,
    ledger: Path,
    source_ref: str | None = None,
    source_checked_at_utc: str | None = None,
    generation_id: str | None = None,
    index_fingerprint: str | None = None,
    now: datetime | None = None,
) -> tuple[dict[str, Any], bool]:
    snapshot = _snapshot(match)
    timestamp = _now_z(now)
    connection = _connect(ledger, create=True)
    assert connection is not None
    try:
        with connection:
            existing = connection.execute(
                """
                SELECT * FROM followed_matches
                WHERE namespace=? AND canonical_match_id=?
                ORDER BY created_at_utc DESC LIMIT 1
                """,
                (NAMESPACE, snapshot["match_id"]),
            ).fetchone()
            if existing is not None and existing["subscription_state"] == "active":
                return _follow_view(connection, existing, event_limit=20), False
            if existing is not None:
                follow_id = existing["follow_id"]
                connection.execute(
                    """
                    UPDATE followed_matches SET subscription_state='active',
                        resolution_state='resolved', data_state=?, current_snapshot_json=?,
                        identity_source_id=?, upstream_fixture_key=?, last_generation_id=?,
                        last_index_fingerprint=?, updated_at_utc=?, unfollowed_at_utc=NULL,
                        last_observed_at_utc=? WHERE follow_id=?
                    """,
                    (
                        "completed" if snapshot["is_complete"] else "current",
                        _canonical(snapshot),
                        snapshot["source_id"],
                        snapshot["upstream_fixture_key"],
                        generation_id,
                        index_fingerprint,
                        timestamp,
                        timestamp,
                        follow_id,
                    ),
                )
                event_type = "refollowed"
            else:
                follow_id = "fm_" + uuid.uuid4().hex
                connection.execute(
                    """
                    INSERT INTO followed_matches(
                        follow_id, namespace, subscription_state, resolution_state,
                        data_state, canonical_match_id, identity_source_id,
                        upstream_fixture_key, initial_snapshot_json, current_snapshot_json,
                        last_generation_id, last_index_fingerprint, created_at_utc,
                        updated_at_utc, unfollowed_at_utc, last_observed_at_utc
                    ) VALUES(?,?,'active','resolved',?,?,?,?,?,?,?,?,?,?,NULL,?)
                    """,
                    (
                        follow_id,
                        NAMESPACE,
                        "completed" if snapshot["is_complete"] else "current",
                        snapshot["match_id"],
                        snapshot["source_id"],
                        snapshot["upstream_fixture_key"],
                        _canonical(snapshot),
                        _canonical(snapshot),
                        generation_id,
                        index_fingerprint,
                        timestamp,
                        timestamp,
                        timestamp,
                    ),
                )
                event_type = "followed"
            _identity(
                connection,
                follow_id,
                "match_id",
                snapshot["match_id"],
                snapshot["source_id"],
                timestamp,
            )
            if snapshot["source_id"] in STABLE_UPSTREAM_KEY_SOURCES:
                _identity(
                    connection,
                    follow_id,
                    "upstream_fixture_key",
                    snapshot["upstream_fixture_key"],
                    snapshot["source_id"],
                    timestamp,
                )
            _insert_event(
                connection,
                follow_id=follow_id,
                event_type=event_type,
                source_id=snapshot["source_id"],
                source_ref=source_ref,
                source_checked_at_utc=source_checked_at_utc,
                generation_id=generation_id,
                after=snapshot,
                detected_at_utc=timestamp,
            )
            row = connection.execute(
                "SELECT * FROM followed_matches WHERE follow_id=?", (follow_id,)
            ).fetchone()
            return _follow_view(connection, row, event_limit=20), True
    finally:
        connection.close()


def list_follows(
    *,
    ledger: Path,
    state: str = "active",
    limit: int = 100,
    offset: int = 0,
    event_limit: int = 20,
) -> dict[str, Any]:
    if state not in ("active", "unfollowed", "all"):
        raise FollowError("invalid_follow_state", "state must be active, unfollowed, or all", 422)
    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))
    event_limit = max(0, min(int(event_limit), 100))
    connection = _connect(ledger, create=False)
    if connection is None:
        return {"schema_version": SCHEMA_VERSION, "items": [], "total": 0, "unread_event_count": 0}
    try:
        where = "" if state == "all" else "WHERE subscription_state=?"
        params: tuple[Any, ...] = () if state == "all" else (state,)
        total = connection.execute(
            f"SELECT COUNT(*) FROM followed_matches {where}", params  # noqa: S608
        ).fetchone()[0]
        rows = connection.execute(
            f"""SELECT * FROM followed_matches {where}
            ORDER BY updated_at_utc DESC, follow_id LIMIT ? OFFSET ?""",  # noqa: S608
            (*params, limit, offset),
        ).fetchall()
        unread = connection.execute(
            """SELECT COUNT(*) FROM follow_events e
            JOIN followed_matches f ON f.follow_id=e.follow_id
            WHERE e.read_at_utc IS NULL AND f.subscription_state='active'"""
        ).fetchone()[0]
        return {
            "schema_version": SCHEMA_VERSION,
            "items": [_follow_view(connection, row, event_limit=event_limit) for row in rows],
            "total": int(total),
            "unread_event_count": int(unread),
        }
    finally:
        connection.close()


def get_follow_for_match(match_id: str, *, ledger: Path) -> dict[str, Any] | None:
    connection = _connect(ledger, create=False)
    if connection is None:
        return None
    try:
        row = connection.execute(
            """SELECT * FROM followed_matches
            WHERE namespace=? AND canonical_match_id=? AND subscription_state='active'""",
            (NAMESPACE, match_id),
        ).fetchone()
        return _follow_view(connection, row, event_limit=20) if row is not None else None
    finally:
        connection.close()


def unfollow(follow_id: str, *, ledger: Path, now: datetime | None = None) -> dict[str, Any]:
    timestamp = _now_z(now)
    connection = _connect(ledger, create=False)
    if connection is None:
        raise FollowError("follow_not_found", "followed match not found", 404)
    try:
        with connection:
            row = connection.execute(
                "SELECT * FROM followed_matches WHERE follow_id=?", (follow_id,)
            ).fetchone()
            if row is None:
                raise FollowError("follow_not_found", "followed match not found", 404)
            if row["subscription_state"] == "active":
                snapshot = _json(row["current_snapshot_json"])
                connection.execute(
                    """UPDATE followed_matches SET subscription_state='unfollowed',
                    updated_at_utc=?, unfollowed_at_utc=? WHERE follow_id=?""",
                    (timestamp, timestamp, follow_id),
                )
                _insert_event(
                    connection,
                    follow_id=follow_id,
                    event_type="unfollowed",
                    source_id=row["identity_source_id"],
                    source_ref=None,
                    source_checked_at_utc=None,
                    generation_id=row["last_generation_id"],
                    before=snapshot,
                    detected_at_utc=timestamp,
                )
            updated = connection.execute(
                "SELECT * FROM followed_matches WHERE follow_id=?", (follow_id,)
            ).fetchone()
            return _follow_view(connection, updated, event_limit=20)
    finally:
        connection.close()


def remove_history(*, ledger: Path) -> dict[str, Any]:
    root = _database_path(ledger).parent
    path = root / DATABASE_NAME
    removed = path.exists()
    try:
        companions = (
            path,
            Path(str(path) + "-journal"),
            Path(str(path) + "-wal"),
            Path(str(path) + "-shm"),
        )
        for candidate in companions:
            if candidate.exists():
                candidate.unlink()
        if root.exists() and not any(root.iterdir()):
            root.rmdir()
    except OSError as exc:
        raise FollowError(
            "follow_store_unavailable", f"could not remove follow history: {exc}", 503
        ) from exc
    return {"schema_version": SCHEMA_VERSION, "removed": removed}


def settings(*, ledger: Path, notifications_supported: bool) -> dict[str, Any]:
    connection = _connect(ledger, create=False)
    opt_in = False
    if connection is not None:
        try:
            row = connection.execute(
                "SELECT notifications_opt_in FROM follow_settings WHERE settings_id=1"
            ).fetchone()
            opt_in = bool(row[0]) if row is not None else False
        finally:
            connection.close()
    return {
        "schema_version": SCHEMA_VERSION,
        "notifications_opt_in": opt_in,
        "notifications_supported": notifications_supported,
    }


def update_settings(
    notifications_opt_in: bool,
    *,
    ledger: Path,
    notifications_supported: bool,
    now: datetime | None = None,
) -> dict[str, Any]:
    timestamp = _now_z(now)
    connection = _connect(ledger, create=True)
    assert connection is not None
    try:
        with connection:
            connection.execute(
                """INSERT INTO follow_settings(
                settings_id, notifications_opt_in, created_at_utc, updated_at_utc
                ) VALUES(1,?,?,?) ON CONFLICT(settings_id) DO UPDATE SET
                notifications_opt_in=excluded.notifications_opt_in,
                updated_at_utc=excluded.updated_at_utc""",
                (int(notifications_opt_in), timestamp, timestamp),
            )
    finally:
        connection.close()
    return settings(ledger=ledger, notifications_supported=notifications_supported)


def mark_read(
    event_ids: Iterable[str] | None,
    *,
    ledger: Path,
    all_events: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    timestamp = _now_z(now)
    ids = sorted(set(event_ids or []))
    if not all_events and not ids:
        raise FollowError("invalid_event_selection", "event_ids or all=true is required", 422)
    connection = _connect(ledger, create=False)
    if connection is None:
        return {"schema_version": SCHEMA_VERSION, "updated": 0}
    try:
        with connection:
            if all_events:
                cursor = connection.execute(
                    "UPDATE follow_events SET read_at_utc=? WHERE read_at_utc IS NULL", (timestamp,)
                )
            else:
                placeholders = ",".join("?" for _ in ids)
                cursor = connection.execute(
                    f"UPDATE follow_events SET read_at_utc=? WHERE event_id IN ({placeholders})",  # noqa: S608
                    (timestamp, *ids),
                )
        return {"schema_version": SCHEMA_VERSION, "updated": cursor.rowcount}
    finally:
        connection.close()


def claim_notifications(
    *, ledger: Path, limit: int = 20, now: datetime | None = None
) -> dict[str, Any]:
    timestamp = _now_z(now)
    limit = max(1, min(int(limit), 100))
    connection = _connect(ledger, create=False)
    if connection is None:
        return {"schema_version": SCHEMA_VERSION, "batch_id": None, "events": []}
    try:
        with connection:
            opted = connection.execute(
                "SELECT notifications_opt_in FROM follow_settings WHERE settings_id=1"
            ).fetchone()
            if opted is None or not bool(opted[0]):
                return {"schema_version": SCHEMA_VERSION, "batch_id": None, "events": []}
            rows = connection.execute(
                """SELECT * FROM follow_events WHERE notification_status='pending'
                ORDER BY detected_at_utc, event_id LIMIT ?""",
                (limit,),
            ).fetchall()
            if not rows:
                return {"schema_version": SCHEMA_VERSION, "batch_id": None, "events": []}
            batch_id = "fn_" + uuid.uuid4().hex
            ids = [row["event_id"] for row in rows]
            placeholders = ",".join("?" for _ in ids)
            connection.execute(
                f"""UPDATE follow_events SET notification_status='claimed',
                notification_batch_id=?, notification_updated_at_utc=?
                WHERE notification_status='pending' AND event_id IN ({placeholders})""",  # noqa: S608
                (batch_id, timestamp, *ids),
            )
            claimed = connection.execute(
                f"""SELECT * FROM follow_events WHERE notification_batch_id=?
                AND event_id IN ({placeholders})""",  # noqa: S608
                (batch_id, *ids),
            ).fetchall()
            return {
                "schema_version": SCHEMA_VERSION,
                "batch_id": batch_id,
                "events": [_event_view(row) for row in claimed],
            }
    finally:
        connection.close()


def update_notification(
    event_id: str,
    status: str,
    *,
    ledger: Path,
    error: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    if status not in NOTIFICATION_STATUSES - {"pending", "claimed", "not_eligible"}:
        raise FollowError("invalid_notification_status", "invalid notification outcome", 422)
    connection = _connect(ledger, create=False)
    if connection is None:
        raise FollowError("follow_event_not_found", "follow event not found", 404)
    try:
        with connection:
            cursor = connection.execute(
                """UPDATE follow_events SET notification_status=?,
                notification_updated_at_utc=?, notification_error=? WHERE event_id=?""",
                (status, _now_z(now), error, event_id),
            )
            if cursor.rowcount == 0:
                raise FollowError("follow_event_not_found", "follow event not found", 404)
            row = connection.execute(
                "SELECT * FROM follow_events WHERE event_id=?", (event_id,)
            ).fetchone()
            return _event_view(row)
    finally:
        connection.close()


def _match_lookup(
    frame: Any,
    match_id: str,
    by_match_id: dict[str, list[dict[str, Any]]],
    by_fixture: dict[tuple[str, str, str], list[dict[str, Any]]],
) -> dict[str, Any] | None:
    from golavo_server import matches

    selected = frame.loc[frame["match_id"].astype("string") == match_id]
    if selected.empty:
        return None
    return matches._row_to_dict(selected.iloc[0], by_match_id, by_fixture)


def _upstream_lookup(
    frame: Any,
    source_id: str,
    key: str,
    by_match_id: dict[str, list[dict[str, Any]]],
    by_fixture: dict[tuple[str, str, str], list[dict[str, Any]]],
) -> dict[str, Any] | None:
    from golavo_server import matches

    if "upstream_fixture_key" not in frame.columns:
        return None
    mask = frame["source_id"].astype("string").eq(source_id)
    mask = mask & frame["upstream_fixture_key"].astype("string").eq(key)
    selected = frame.loc[mask]
    if len(selected) != 1:
        return None
    return matches._row_to_dict(selected.iloc[0], by_match_id, by_fixture)


def reconcile(
    *,
    ledger: Path,
    frame: Any,
    index_fingerprint: str,
    generation_id: str | None,
    source_status: dict[str, dict[str, Any]],
    now: datetime | None = None,
) -> dict[str, Any]:
    """Compare active follows with one already-activated immutable index."""
    timestamp = _now_z(now)
    connection = _connect(ledger, create=False)
    if connection is None:
        return {"schema_version": SCHEMA_VERSION, "reconciled": 0, "event_ids": []}
    event_ids: list[str] = []
    try:
        with connection:
            from golavo_server import matches

            by_match_id, by_fixture = matches.artifact_links(ledger)
            resolved_artifacts = _resolved_artifact_ids(ledger)
            rows = connection.execute(
                "SELECT * FROM followed_matches WHERE subscription_state='active'"
            ).fetchall()
            for row in rows:
                previous = _json(row["current_snapshot_json"])
                current_match = _match_lookup(
                    frame, row["canonical_match_id"], by_match_id, by_fixture
                )
                repointed = False
                if current_match is None:
                    source_id = row["identity_source_id"]
                    key = row["upstream_fixture_key"]
                    if source_id in STABLE_UPSTREAM_KEY_SOURCES and key:
                        current_match = _upstream_lookup(
                            frame, source_id, key, by_match_id, by_fixture
                        )
                        repointed = current_match is not None
                if current_match is None:
                    source_id, source_ref, checked_at = _source_details(
                        previous, "identity", source_status
                    )
                    event_id = _insert_event(
                        connection,
                        follow_id=row["follow_id"],
                        event_type="identity_unresolved",
                        source_id=source_id,
                        source_ref=source_ref,
                        source_checked_at_utc=checked_at,
                        generation_id=generation_id,
                        before={"match_id": row["canonical_match_id"]},
                        conflict={"reason": "no exact stable source identity"},
                        detected_at_utc=timestamp,
                    )
                    if event_id:
                        event_ids.append(event_id)
                    connection.execute(
                        """UPDATE followed_matches SET resolution_state='identity_unresolved',
                        data_state='stale', last_generation_id=?, last_index_fingerprint=?,
                        last_observed_at_utc=?, updated_at_utc=? WHERE follow_id=?""",
                        (generation_id, index_fingerprint, timestamp, timestamp, row["follow_id"]),
                    )
                    continue
                current = _snapshot(current_match)
                if repointed and current["match_id"] != row["canonical_match_id"]:
                    source_id, source_ref, checked_at = _source_details(
                        current, "identity", source_status
                    )
                    event_id = _insert_event(
                        connection,
                        follow_id=row["follow_id"],
                        event_type="match_repointed",
                        source_id=source_id,
                        source_ref=source_ref,
                        source_checked_at_utc=checked_at,
                        generation_id=generation_id,
                        before={"match_id": row["canonical_match_id"]},
                        after={"match_id": current["match_id"]},
                        detected_at_utc=timestamp,
                    )
                    if event_id:
                        event_ids.append(event_id)
                    _identity(
                        connection,
                        row["follow_id"],
                        "match_id",
                        current["match_id"],
                        current["source_id"],
                        timestamp,
                    )

                comparisons = (
                    ("kickoff_changed", "kickoff", ("kickoff_utc", "kickoff_precision")),
                    ("venue_changed", "venue", ("city", "country")),
                    ("score_published", "result", ("home_score", "away_score", "is_complete")),
                )
                for event_type, field, keys in comparisons:
                    before = {key: previous.get(key) for key in keys}
                    after = {key: current.get(key) for key in keys}
                    if before == after:
                        continue
                    if event_type == "score_published" and not (
                        current["is_complete"]
                        and current["home_score"] is not None
                        and current["away_score"] is not None
                    ):
                        continue
                    source_id, source_ref, checked_at = _source_details(
                        current, field, source_status
                    )
                    event_id = _insert_event(
                        connection,
                        follow_id=row["follow_id"],
                        event_type=event_type,
                        source_id=source_id,
                        source_ref=source_ref,
                        source_checked_at_utc=checked_at,
                        generation_id=generation_id,
                        before=before,
                        after=after,
                        effective_at_utc=(
                            current["kickoff_utc"] if event_type == "kickoff_changed" else None
                        ),
                        detected_at_utc=timestamp,
                    )
                    if event_id:
                        event_ids.append(event_id)

                identity_health = source_status.get(current["source_id"], {}).get("health")
                if identity_health == "conflict":
                    data_state = "source_conflict"
                    health_event = "source_conflict"
                elif identity_health in ("offline", "backoff", "invalid", "unavailable"):
                    data_state = "source_unavailable"
                    health_event = "source_unavailable"
                else:
                    data_state = "completed" if current["is_complete"] else "current"
                    health_event = (
                        "source_recovered"
                        if row["data_state"] in ("source_conflict", "source_unavailable")
                        else None
                    )
                if health_event:
                    source_id, source_ref, checked_at = _source_details(
                        current, "identity", source_status
                    )
                    event_id = _insert_event(
                        connection,
                        follow_id=row["follow_id"],
                        event_type=health_event,
                        source_id=source_id,
                        source_ref=source_ref,
                        source_checked_at_utc=checked_at,
                        generation_id=generation_id,
                        before={"data_state": row["data_state"]},
                        after={"data_state": data_state},
                        detected_at_utc=timestamp,
                    )
                    if event_id:
                        event_ids.append(event_id)

                pending_seals = sorted(
                    str(forecast["artifact_id"])
                    for forecast in current_match.get("forecasts", [])
                    if isinstance(forecast, dict)
                    and forecast.get("status") in ("sealed", "abstained")
                    and forecast.get("artifact_id")
                    and forecast.get("artifact_id") not in resolved_artifacts
                )
                if data_state == "completed" and pending_seals:
                    availability = {
                        "sealed_artifact_ids": pending_seals,
                        "home_score": current["home_score"],
                        "away_score": current["away_score"],
                    }
                    already_available = connection.execute(
                        """SELECT 1 FROM follow_events WHERE follow_id=?
                        AND event_type='settlement_available' AND after_json=? LIMIT 1""",
                        (row["follow_id"], _canonical(availability)),
                    ).fetchone()
                    if already_available is None:
                        source_id, source_ref, checked_at = _source_details(
                            current, "result", source_status
                        )
                        event_id = _insert_event(
                            connection,
                            follow_id=row["follow_id"],
                            event_type="settlement_available",
                            source_id=source_id,
                            source_ref=source_ref,
                            source_checked_at_utc=checked_at,
                            generation_id=generation_id,
                            after=availability,
                            detected_at_utc=timestamp,
                        )
                        if event_id:
                            event_ids.append(event_id)

                connection.execute(
                    """UPDATE followed_matches SET canonical_match_id=?,
                    resolution_state='resolved', data_state=?, identity_source_id=?,
                    upstream_fixture_key=?, current_snapshot_json=?, last_generation_id=?,
                    last_index_fingerprint=?, last_observed_at_utc=?, updated_at_utc=?
                    WHERE follow_id=?""",
                    (
                        current["match_id"],
                        data_state,
                        current["source_id"],
                        current["upstream_fixture_key"],
                        _canonical(current),
                        generation_id,
                        index_fingerprint,
                        timestamp,
                        timestamp,
                        row["follow_id"],
                    ),
                )
        return {
            "schema_version": SCHEMA_VERSION,
            "reconciled": len(rows),
            "event_ids": event_ids,
        }
    finally:
        connection.close()


def source_ids(*, ledger: Path) -> list[str]:
    connection = _connect(ledger, create=False)
    if connection is None:
        return []
    try:
        rows = connection.execute(
            """SELECT DISTINCT identity_source_id FROM followed_matches
            WHERE subscription_state='active' ORDER BY identity_source_id"""
        ).fetchall()
        return [row[0] for row in rows if row[0] in refresh_sources.APPROVED_SOURCE_IDS]
    finally:
        connection.close()


def record_source_revisions(
    source_ids: Iterable[str],
    *,
    ledger: Path,
    source_status: dict[str, dict[str, Any]],
    now: datetime | None = None,
) -> list[str]:
    timestamp = _now_z(now)
    selected = set(source_ids)
    connection = _connect(ledger, create=False)
    if connection is None:
        return []
    event_ids: list[str] = []
    try:
        with connection:
            rows = connection.execute(
                """SELECT * FROM followed_matches WHERE subscription_state='active'"""
            ).fetchall()
            for row in rows:
                source_id = row["identity_source_id"]
                if source_id not in selected:
                    continue
                status = source_status.get(source_id, {})
                observed = status.get("observed_ref")
                active = status.get("active_ref")
                if not observed or observed == active:
                    continue
                event_id = _insert_event(
                    connection,
                    follow_id=row["follow_id"],
                    event_type="source_revision_available",
                    source_id=source_id,
                    source_ref=observed,
                    source_checked_at_utc=status.get("last_checked_at_utc"),
                    generation_id=None,
                    before={"active_ref": active},
                    after={"observed_ref": observed},
                    detected_at_utc=timestamp,
                )
                if event_id:
                    event_ids.append(event_id)
        return event_ids
    finally:
        connection.close()


def record_conflicts(
    details: Iterable[dict[str, Any]],
    *,
    ledger: Path,
    source_status: dict[str, dict[str, Any]],
    now: datetime | None = None,
) -> list[str]:
    """Attach structured quarantined candidate evidence to matching follows."""
    timestamp = _now_z(now)
    items = [item for item in details if isinstance(item, dict)]
    if not items:
        return []
    connection = _connect(ledger, create=False)
    if connection is None:
        return []
    event_ids: list[str] = []
    try:
        with connection:
            for detail in items:
                match_id = detail.get("match_id")
                if not isinstance(match_id, str):
                    continue
                row = connection.execute(
                    """SELECT * FROM followed_matches WHERE canonical_match_id=?
                    AND subscription_state='active'""",
                    (match_id,),
                ).fetchone()
                if row is None:
                    continue
                source_id = row["identity_source_id"]
                status = source_status.get(source_id, {})
                event_id = _insert_event(
                    connection,
                    follow_id=row["follow_id"],
                    event_type="source_conflict",
                    source_id=source_id,
                    source_ref=status.get("observed_ref") or status.get("active_ref"),
                    source_checked_at_utc=status.get("last_checked_at_utc"),
                    generation_id=None,
                    before=_json(row["current_snapshot_json"]),
                    conflict=detail,
                    detected_at_utc=timestamp,
                )
                connection.execute(
                    """UPDATE followed_matches SET data_state='source_conflict',
                    updated_at_utc=?, last_observed_at_utc=? WHERE follow_id=?""",
                    (timestamp, timestamp, row["follow_id"]),
                )
                if event_id:
                    event_ids.append(event_id)
        return event_ids
    finally:
        connection.close()


def record_settlement_report(
    report: dict[str, Any], *, ledger: Path, now: datetime | None = None
) -> list[str]:
    """Append events only for settlement successors the existing service created."""
    timestamp = _now_z(now)
    scored = report.get("scored")
    if not isinstance(scored, list) or not scored:
        return []
    connection = _connect(ledger, create=False)
    if connection is None:
        return []
    event_ids: list[str] = []
    try:
        with connection:
            rows = connection.execute(
                "SELECT * FROM followed_matches WHERE subscription_state='active'"
            ).fetchall()
            for row in rows:
                snapshot = _json(row["current_snapshot_json"])
                for item in scored:
                    if not isinstance(item, dict):
                        continue
                    if (
                        item.get("home_team") != snapshot.get("home_team")
                        or item.get("away_team") != snapshot.get("away_team")
                    ):
                        continue
                    source_id = str(item.get("source_id") or snapshot["source_id"])
                    event_id = _insert_event(
                        connection,
                        follow_id=row["follow_id"],
                        event_type="settlement_recorded",
                        source_id=source_id,
                        source_ref=str(item.get("scored_artifact_id") or "") or None,
                        source_checked_at_utc=report.get("checked_at_utc"),
                        generation_id=row["last_generation_id"],
                        after={
                            "sealed_artifact_id": item.get("sealed_artifact_id"),
                            "scored_artifact_id": item.get("scored_artifact_id"),
                        },
                        detected_at_utc=timestamp,
                    )
                    if event_id:
                        event_ids.append(event_id)
        return event_ids
    finally:
        connection.close()
