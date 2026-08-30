"""Portable, checksummed backup of explicitly allowlisted forecast-ledger state."""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any

from golavo_core.artifacts import verify_artifact_integrity
from golavo_core.picks import validate_user_pick, verify_pick_integrity

from golavo_server import follows, ledger_checkpoints, refresh_sources, runtime

SCHEMA_VERSION = "0.2.0"
LEGACY_SCHEMA_VERSION = "0.1.0"
SUPPORTED_SCHEMA_VERSIONS = frozenset({LEGACY_SCHEMA_VERSION, SCHEMA_VERSION})
MAX_FILES = 5000
MAX_UNCOMPRESSED = 64 * 1024 * 1024
MAX_JSON_DEPTH = 64
_SNAPSHOT_FIELDS = {
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
}
_ALLOWED = (
    re.compile(r"^ledger/fa_[0-9a-f]{20}\.json$"),
    re.compile(r"^ledger/checkpoints/head\.json$"),
    re.compile(r"^ledger/checkpoints/lc_[0-9a-f]{64}\.json$"),
    re.compile(
        r"^ledger/picks/(?:drafts/[A-Za-z0-9_.-]+\.json|pk_[0-9a-f]{20}\.json|audit\.jsonl)$"
    ),
    re.compile(r"^ledger/follows/follows\.sqlite3$"),
)


def _allowed(name: str) -> bool:
    return "\\" not in name and any(pattern.fullmatch(name) for pattern in _ALLOWED)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _check_depth(value: Any, *, maximum: int = MAX_JSON_DEPTH) -> None:
    stack = [(value, 1)]
    while stack:
        current, depth = stack.pop()
        if depth > maximum:
            raise ValueError(f"JSON nesting exceeds {maximum} levels")
        if isinstance(current, dict):
            stack.extend((item, depth + 1) for item in current.values())
        elif isinstance(current, list):
            stack.extend((item, depth + 1) for item in current)


def _json(data: bytes | str) -> Any:
    try:
        value = json.loads(data)
    except RecursionError as exc:
        raise ValueError("JSON nesting is too deep") from exc
    _check_depth(value)
    return value


def _normalized_schema(connection: sqlite3.Connection) -> tuple[tuple[str, str, str, str], ...]:
    rows = connection.execute(
        """SELECT type, name, tbl_name, sql FROM sqlite_master
        WHERE type IN ('table','index','trigger','view') AND name NOT LIKE 'sqlite_%'
        ORDER BY type, name"""
    ).fetchall()
    return tuple(
        (
            str(row[0]),
            str(row[1]),
            str(row[2]),
            " ".join(str(row[3]).split()).casefold(),
        )
        for row in rows
    )


@lru_cache(maxsize=1)
def _canonical_follow_schema() -> tuple[tuple[str, str, str, str], ...]:
    connection = sqlite3.connect(":memory:")
    try:
        follows._migrate(connection)
        return _normalized_schema(connection)
    finally:
        connection.close()


def _outside(values: set[str]) -> str:
    return ",".join("?" for _ in values)


def _validate_snapshot(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != _SNAPSHOT_FIELDS:
        raise ValueError("follow history contains an invalid match snapshot")
    approved = set(refresh_sources.APPROVED_SOURCE_IDS)
    if (
        not isinstance(value["match_id"], str)
        or not value["match_id"]
        or value["source_id"] not in approved
        or not isinstance(value["is_complete"], bool)
    ):
        raise ValueError("follow history contains an invalid match snapshot")
    for field in (
        "kickoff_precision",
        "home_team",
        "away_team",
        "competition",
        "country",
        "city",
        "source_kind",
        "upstream_fixture_key",
    ):
        if value[field] is not None and not isinstance(value[field], str):
            raise ValueError("follow history contains an invalid match snapshot")
    kickoff = value["kickoff_utc"]
    if kickoff is not None:
        if not isinstance(kickoff, str):
            raise ValueError("follow history contains an invalid match snapshot")
        try:
            parsed = datetime.fromisoformat(kickoff.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("follow history contains an invalid match snapshot") from exc
        if parsed.tzinfo is None:
            raise ValueError("follow history contains an invalid match snapshot")
    for field in ("home_score", "away_score"):
        score = value[field]
        if score is not None and (
            isinstance(score, bool) or not isinstance(score, int) or score < 0
        ):
            raise ValueError("follow history contains an invalid match snapshot")
    if value["neutral"] is not None and not isinstance(value["neutral"], bool):
        raise ValueError("follow history contains an invalid match snapshot")
    provenance = value["provenance"]
    if not isinstance(provenance, dict) or any(
        item is not None and (not isinstance(item, str) or item not in approved)
        for item in provenance.values()
    ):
        raise ValueError("follow history contains an invalid match snapshot")
    return value


def _require_shape(value: Any, fields: set[str], message: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(message)
    return value


def _snapshot_matches_follow_identity(
    snapshot: dict[str, Any],
    identities: dict[str, dict[str, set[str]]],
) -> None:
    source_id = str(snapshot["source_id"])
    match_sources = identities.get("match_id", {}).get(str(snapshot["match_id"]), set())
    if source_id not in match_sources:
        raise ValueError("follow history snapshot does not match its recorded identity")
    upstream = snapshot.get("upstream_fixture_key")
    if source_id in follows.STABLE_UPSTREAM_KEY_SOURCES and upstream is not None:
        upstream_sources = identities.get("upstream_fixture_key", {}).get(str(upstream), set())
        if source_id not in upstream_sources:
            raise ValueError("follow history snapshot does not match its recorded identity")


def _validate_event_evidence(
    event_type: str,
    before: Any,
    after: Any,
    conflict: Any,
    identities: dict[str, dict[str, set[str]]],
) -> None:
    message = "follow history contains invalid event evidence"
    if event_type in {"followed", "refollowed"}:
        if before is not None or conflict is not None:
            raise ValueError(message)
        _snapshot_matches_follow_identity(_validate_snapshot(after), identities)
        return
    if event_type == "unfollowed":
        if after is not None or conflict is not None:
            raise ValueError(message)
        _snapshot_matches_follow_identity(_validate_snapshot(before), identities)
        return
    if event_type == "source_conflict" and conflict is not None:
        if after is not None or not isinstance(conflict, dict):
            raise ValueError(message)
        _snapshot_matches_follow_identity(_validate_snapshot(before), identities)
        return
    if event_type == "identity_unresolved":
        value = _require_shape(before, {"match_id"}, message)
        reason = _require_shape(conflict, {"reason"}, message)
        if (
            after is not None
            or not isinstance(value["match_id"], str)
            or reason["reason"] != "no exact stable source identity"
        ):
            raise ValueError(message)
        if value["match_id"] not in identities.get("match_id", {}):
            raise ValueError("follow event evidence does not match its recorded identity")
        return
    if conflict is not None:
        raise ValueError(message)
    if event_type == "match_repointed":
        previous = _require_shape(before, {"match_id"}, message)
        current = _require_shape(after, {"match_id"}, message)
        known = identities.get("match_id", {})
        if any(
            not isinstance(value["match_id"], str) or value["match_id"] not in known
            for value in (previous, current)
        ):
            raise ValueError("follow event evidence does not match its recorded identity")
        return
    comparison_fields = {
        "kickoff_changed": {"kickoff_utc", "kickoff_precision"},
        "venue_changed": {"city", "country"},
        "score_published": {"home_score", "away_score", "is_complete"},
    }
    if event_type in comparison_fields:
        previous = _require_shape(before, comparison_fields[event_type], message)
        current = _require_shape(after, comparison_fields[event_type], message)
        if event_type == "score_published":
            for value in (previous, current):
                for field in ("home_score", "away_score"):
                    score = value[field]
                    if score is not None and (
                        isinstance(score, bool) or not isinstance(score, int) or score < 0
                    ):
                        raise ValueError(message)
                if not isinstance(value["is_complete"], bool):
                    raise ValueError(message)
        elif any(
            item is not None and not isinstance(item, str)
            for value in (previous, current)
            for item in value.values()
        ):
            raise ValueError(message)
        return
    if event_type in {"source_conflict", "source_unavailable", "source_recovered"}:
        previous = _require_shape(before, {"data_state"}, message)
        current = _require_shape(after, {"data_state"}, message)
        allowed_states = {
            "current",
            "stale",
            "source_conflict",
            "source_unavailable",
            "completed",
        }
        if (
            previous["data_state"] not in allowed_states
            or current["data_state"] not in allowed_states
        ):
            raise ValueError(message)
        return
    if event_type == "source_revision_available":
        previous = _require_shape(before, {"active_ref"}, message)
        current = _require_shape(after, {"observed_ref"}, message)
        if any(
            item is not None and not isinstance(item, str)
            for item in (previous["active_ref"], current["observed_ref"])
        ):
            raise ValueError(message)
        return
    if event_type == "settlement_available":
        if before is not None:
            raise ValueError(message)
        current = _require_shape(
            after, {"sealed_artifact_ids", "home_score", "away_score"}, message
        )
        if (
            not isinstance(current["sealed_artifact_ids"], list)
            or not all(isinstance(item, str) for item in current["sealed_artifact_ids"])
            or any(
                isinstance(current[field], bool)
                or not isinstance(current[field], int)
                or current[field] < 0
                for field in ("home_score", "away_score")
            )
        ):
            raise ValueError(message)
        return
    if event_type == "settlement_recorded":
        if before is not None:
            raise ValueError(message)
        current = _require_shape(after, {"sealed_artifact_id", "scored_artifact_id"}, message)
        if not all(isinstance(item, str) and item for item in current.values()):
            raise ValueError(message)
        return
    raise ValueError(message)


def _validate_follow_database(data: bytes) -> None:
    with tempfile.NamedTemporaryFile(suffix=".sqlite3") as handle:
        handle.write(data)
        handle.flush()
        connection = sqlite3.connect(f"file:{handle.name}?mode=ro", uri=True)
        try:
            check = connection.execute("PRAGMA quick_check").fetchone()
            foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            if check is None or check[0] != "ok" or foreign_keys or version != 1:
                raise ValueError("follow history failed its database integrity/version check")
            if _normalized_schema(connection) != _canonical_follow_schema():
                raise ValueError("follow history has an unexpected database schema")
            invalid = connection.execute(
                """SELECT COUNT(*) FROM followed_matches
                WHERE namespace != 'core-cc0'
                   OR subscription_state NOT IN ('active','unfollowed')
                   OR resolution_state NOT IN ('resolved','identity_unresolved')
                   OR data_state NOT IN (
                       'current','stale','source_conflict','source_unavailable','completed'
                   )"""
            ).fetchone()[0]
            if invalid:
                raise ValueError("follow history contains values outside its domain")
            approved_sources = set(refresh_sources.APPROVED_SOURCE_IDS)
            invalid_sources = connection.execute(
                f"""SELECT
                (SELECT COUNT(*) FROM followed_matches
                    WHERE identity_source_id NOT IN ({_outside(approved_sources)})) +
                (SELECT COUNT(*) FROM follow_identities
                    WHERE source_id NOT IN ({_outside(approved_sources)})) +
                (SELECT COUNT(*) FROM follow_events
                    WHERE source_id NOT IN ({_outside(approved_sources)}))""",
                (*approved_sources, *approved_sources, *approved_sources),
            ).fetchone()[0]
            invalid_events = connection.execute(
                f"""SELECT COUNT(*) FROM follow_events
                WHERE event_type NOT IN ({_outside(follows.EVENT_TYPES)})
                   OR notification_status NOT IN ({_outside(follows.NOTIFICATION_STATUSES)})""",
                (*follows.EVENT_TYPES, *follows.NOTIFICATION_STATUSES),
            ).fetchone()[0]
            if invalid_sources or invalid_events:
                raise ValueError("follow history contains values outside its domain")
            identity_index: dict[str, dict[str, dict[str, set[str]]]] = {}
            for follow_id, kind, value, source_id in connection.execute(
                """SELECT follow_id, identity_kind, identity_value, source_id
                FROM follow_identities"""
            ):
                identity_index.setdefault(str(follow_id), {}).setdefault(str(kind), {}).setdefault(
                    str(value), set()
                ).add(str(source_id))
            for row in connection.execute(
                """SELECT follow_id, canonical_match_id, identity_source_id, upstream_fixture_key,
                initial_snapshot_json, current_snapshot_json FROM followed_matches"""
            ):
                identities = identity_index.get(str(row[0]), {})
                initial = _validate_snapshot(_json(row[4]))
                current = _validate_snapshot(_json(row[5]))
                _snapshot_matches_follow_identity(initial, identities)
                _snapshot_matches_follow_identity(current, identities)
                if (
                    current["match_id"] != row[1]
                    or current["source_id"] != row[2]
                    or current["upstream_fixture_key"] != row[3]
                    or initial["source_id"] not in approved_sources
                ):
                    raise ValueError("follow history snapshot identity does not match its row")
            for row in connection.execute(
                """SELECT follow_id, event_type, before_json, after_json, conflict_json
                FROM follow_events"""
            ):
                before = _json(row[2]) if row[2] is not None else None
                after = _json(row[3]) if row[3] is not None else None
                conflict = _json(row[4]) if row[4] is not None else None
                _validate_event_evidence(
                    str(row[1]),
                    before,
                    after,
                    conflict,
                    identity_index.get(str(row[0]), {}),
                )
        except sqlite3.DatabaseError as exc:
            raise ValueError("follow history is not a valid Golavo database") from exc
        finally:
            connection.close()


def _validate_content(name: str, data: bytes) -> None:
    if name.startswith("ledger/fa_"):
        verify_artifact_integrity(_json(data), expected_id=Path(name).stem)
        return
    if "/picks/pk_" in name:
        verify_pick_integrity(_json(data), expected_id=Path(name).stem)
        return
    if "/picks/drafts/" in name:
        value = _json(data)
        validate_user_pick(value)
        if value["match"]["match_id"] != PurePosixPath(name).stem:
            raise ValueError("pick draft path does not match its recorded match identity")
        return
    if name.endswith("/picks/audit.jsonl"):
        for line in data.splitlines():
            if not isinstance(_json(line), dict):
                raise ValueError("pick audit contains a non-object row")
        return
    if name.endswith("/follows/follows.sqlite3"):
        _validate_follow_database(data)
        return
    if name.startswith("ledger/checkpoints/") and not isinstance(_json(data), dict):
        raise ValueError("checkpoint archive entry is not an object")


def _safe_destination(ledger: Path, name: str) -> Path:
    ledger = Path(ledger)
    if ledger.is_symlink():
        raise ValueError("ledger root must not be a symlink")
    portable = PurePosixPath(name)
    if "\\" in name or portable.as_posix() != name:
        raise ValueError(f"restore destination is not a canonical portable path: {name}")
    relative = Path(*portable.relative_to("ledger").parts)
    destination = ledger / relative
    cursor = ledger
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError(f"restore destination contains a symlink: {name}")
    root = ledger.resolve(strict=False)
    resolved = destination.resolve(strict=False)
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"restore destination escapes the ledger: {name}")
    return destination


def _snapshot_follow_database(path: Path) -> bytes:
    with tempfile.NamedTemporaryFile(suffix=".sqlite3") as handle:
        source = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5.0)
        target = sqlite3.connect(handle.name)
        try:
            source.backup(target)
            target.commit()
        finally:
            target.close()
            source.close()
        return Path(handle.name).read_bytes()


def _files(ledger: Path, *, validate_checkpoints: bool = True) -> list[tuple[str, Path]]:
    candidates = [*Path(ledger).glob("fa_*.json"), *Path(ledger).glob("picks/**/*.json")]
    audit = Path(ledger) / "picks" / "audit.jsonl"
    follows = Path(ledger) / "follows" / "follows.sqlite3"
    candidates.extend(path for path in (audit, follows) if path.is_file())
    if validate_checkpoints:
        candidates.extend(ledger_checkpoints.recovery_files(ledger))
    else:
        checkpoint_root = Path(ledger) / "checkpoints"
        candidates.extend(
            path
            for path in [checkpoint_root / "head.json", *checkpoint_root.glob("lc_*.json")]
            if path.is_file()
        )
    result = []
    for path in candidates:
        if path.is_symlink():
            raise ValueError("archive-owned files must not be symlinks")
        if not path.is_file():
            continue
        name = "ledger/" + path.relative_to(ledger).as_posix()
        if _allowed(name) and _safe_destination(ledger, name) == path:
            result.append((name, path))
    return sorted(result)


def _checkpoint_recovery_summary(status: dict[str, Any]) -> dict[str, Any]:
    return {
        "available": status["head"] is not None,
        "recovery_drill_verified": True,
        "checkpoint_count": status["checkpoint_count"],
        "head": status["head"],
        "head_schema_version": status["head_schema_version"],
        "checkpoint_schema_versions": status["checkpoint_schema_versions"],
        "legacy_checkpoint_count": status["legacy_checkpoint_count"],
        "missing_artifacts": status["missing_artifacts"],
        "uncheckpointed_artifacts": status["uncheckpointed_artifacts"],
    }


def _raw_checkpoint_recovery(ledger: Path) -> dict[str, Any]:
    checkpoint_root = Path(ledger) / "checkpoints"
    return {
        "available": (checkpoint_root / "head.json").is_file(),
        "recovery_drill_verified": False,
        "checkpoint_count": len(list(checkpoint_root.glob("lc_*.json"))),
        "head": None,
        "head_schema_version": None,
        "checkpoint_schema_versions": [],
        "legacy_checkpoint_count": 0,
        "missing_artifacts": [],
        "uncheckpointed_artifacts": [],
    }


def _export_archive_unlocked(
    ledger: Path, *, validate_content: bool = True
) -> tuple[bytes, dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    content: dict[str, bytes] = {}
    total = 0
    files = _files(ledger, validate_checkpoints=validate_content)
    if len(files) > MAX_FILES:
        raise ValueError("ledger contains too many archive-owned files")
    for name, path in files:
        data = (
            _snapshot_follow_database(path)
            if validate_content and name.endswith("/follows/follows.sqlite3")
            else path.read_bytes()
        )
        total += len(data)
        if total > MAX_UNCOMPRESSED:
            raise ValueError("forecast-ledger archive exceeds 64 MiB")
        if validate_content:
            _validate_content(name, data)
        content[name] = data
        entries.append({"path": name, "bytes": len(data), "sha256": _sha(data)})
    created = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    checkpoint_recovery = (
        _checkpoint_recovery_summary(_checkpoint_overlay_status(content))
        if validate_content
        else _raw_checkpoint_recovery(ledger)
    )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "created_at_utc": created,
        "files": entries,
        "included": [
            "forecast artifacts",
            "picks",
            "followed-match state",
            "verified linked ledger checkpoints when available",
        ],
        "excluded": [
            "team favorites stored in browser preferences",
            "credentials and provider settings",
            "licensed overlays and provider responses",
            "weather captures and research data",
            "refresh generations and derived caches",
        ],
        "checkpoint_recovery": checkpoint_recovery,
        "integrity": "verified" if validate_content else "unverified-preservation",
    }
    content["manifest.json"] = json.dumps(manifest, indent=2, sort_keys=True).encode() + b"\n"
    target = io.BytesIO()
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(content.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            archive.writestr(info, data)
    return target.getvalue(), manifest


def _sibling_root(ledger: Path, name: str) -> Path:
    ledger = Path(ledger)
    parent = ledger.parent
    root = parent / name
    if parent.is_symlink() or root.is_symlink():
        raise ValueError("archive transaction paths must not be symlinks")
    parent_resolved = parent.resolve(strict=False)
    root_resolved = root.resolve(strict=False)
    if root_resolved.parent != parent_resolved:
        raise ValueError("archive transaction path escapes the application data root")
    return root


def _recovery_root(ledger: Path) -> Path:
    return _sibling_root(ledger, f".{Path(ledger).name}-restore-transaction")


def _backup_root(ledger: Path) -> Path:
    return _sibling_root(ledger, f"{Path(ledger).name}-archive-backups")


def _fsync_dir(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_bytes(path: Path, data: bytes) -> None:
    parent_existed = path.parent.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not parent_existed and path.parent.parent.exists():
        _fsync_dir(path.parent.parent)
    descriptor, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _fsync_dir(path.parent)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _write_journal(root: Path, value: dict[str, Any]) -> None:
    _atomic_bytes(root / "restore.json", json.dumps(value, sort_keys=True).encode() + b"\n")


def _remove_recovery(root: Path) -> None:
    parent = root.parent
    shutil.rmtree(root)
    _fsync_dir(parent)


def _recover_unlocked(ledger: Path) -> bool:
    root = _recovery_root(ledger)
    if not root.exists():
        return False
    journal_path = root / "restore.json"
    if not journal_path.is_file():
        _remove_recovery(root)
        return True
    journal = _json(journal_path.read_bytes())
    if not isinstance(journal, dict) or journal.get("phase") not in {
        "prepared",
        "applying",
        "committed",
        "rolled_back",
    }:
        raise ValueError("restore recovery journal is invalid")
    phase = journal["phase"]
    entries = journal.get("files")
    if not isinstance(entries, list):
        raise ValueError("restore recovery file list is invalid")
    if phase == "applying":
        for entry in entries:
            if not isinstance(entry, dict) or not _allowed(str(entry.get("path", ""))):
                raise ValueError("restore recovery entry is invalid")
            name = str(entry["path"])
            destination = _safe_destination(ledger, name)
            relative = Path(*PurePosixPath(name).relative_to("ledger").parts)
            backup = root / "backup" / relative
            if bool(entry.get("existed")):
                if not backup.is_file() or backup.is_symlink():
                    raise ValueError("restore recovery backup is missing")
                _atomic_bytes(destination, backup.read_bytes())
            else:
                destination.unlink(missing_ok=True)
                if destination.parent.exists():
                    _fsync_dir(destination.parent)
        journal["phase"] = "rolled_back"
        _write_journal(root, journal)
    _remove_recovery(root)
    return True


def recover_pending(ledger: Path) -> bool:
    """Idempotently roll back an interrupted restore before serving ledger state."""
    with runtime.USER_STATE_LOCK:
        return _recover_unlocked(Path(ledger))


def export_archive(ledger: Path) -> tuple[bytes, dict[str, Any]]:
    with runtime.USER_STATE_LOCK:
        _recover_unlocked(Path(ledger))
        return _export_archive_unlocked(Path(ledger))


def _checkpoint_overlay_status(
    content: dict[str, bytes], *, ledger: Path | None = None
) -> dict[str, Any]:
    """Run the recovered checkpoint state in a disposable ledger directory."""

    with tempfile.TemporaryDirectory(prefix="golavo-checkpoint-drill-") as directory:
        staging = Path(directory)
        if ledger is not None:
            # Validate path ownership before copying local bytes. Content may be
            # corrupt specifically because this archive is intended to repair it;
            # only the fully overlaid staging ledger must pass chain verification.
            ledger_checkpoints.validate_paths(ledger)
            local_files = [*Path(ledger).glob("fa_*.json")]
            checkpoint_root = Path(ledger) / "checkpoints"
            local_files.extend(
                path
                for path in [checkpoint_root / "head.json", *checkpoint_root.glob("lc_*.json")]
                if path.exists()
            )
            for path in local_files:
                if not path.is_file() or path.is_symlink():
                    raise ValueError("local checkpoint state contains an unsafe path")
                relative = path.relative_to(ledger)
                destination = staging / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(path.read_bytes())
        for name, value in content.items():
            if not (name.startswith("ledger/fa_") or name.startswith("ledger/checkpoints/")):
                continue
            relative = Path(*PurePosixPath(name).relative_to("ledger").parts)
            destination = staging / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(value)
        return ledger_checkpoints.status(staging)


def _restore_preview_token(content: dict[str, bytes], *, ledger: Path) -> str:
    """Bind replace approval to both archive bytes and the previewed local state."""

    state: list[dict[str, str | None]] = []
    for name, archived in sorted(content.items()):
        destination = _safe_destination(ledger, name)
        local_sha = _sha(destination.read_bytes()) if destination.exists() else None
        state.append(
            {
                "path": name,
                "archive_sha256": _sha(archived),
                "local_sha256": local_sha,
            }
        )
    encoded = json.dumps(state, sort_keys=True, separators=(",", ":")).encode()
    return _sha(encoded)


def _inspect_archive_unlocked(
    data: bytes, *, ledger: Path
) -> tuple[dict[str, Any], dict[str, bytes]]:
    if len(data) > MAX_UNCOMPRESSED:
        raise ValueError("archive exceeds 64 MiB")
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ValueError("archive is not a valid ZIP file") from exc
    with archive:
        infos = archive.infolist()
        if len(infos) > MAX_FILES + 1:
            raise ValueError("archive contains too many files")
        if sum(item.file_size for item in infos) > MAX_UNCOMPRESSED:
            raise ValueError("archive expands beyond 64 MiB")
        names = [item.filename for item in infos]
        if len(names) != len(set(names)) or "manifest.json" not in names:
            raise ValueError("archive has duplicate paths or no manifest")
        for item in infos:
            path = PurePosixPath(item.filename)
            is_symlink = (item.external_attr >> 16) & 0o170000 == 0o120000
            if path.is_absolute() or ".." in path.parts or item.is_dir() or is_symlink:
                raise ValueError("archive contains an unsafe path")
            if item.filename != "manifest.json" and not _allowed(item.filename):
                raise ValueError(
                    f"archive path is outside the forecast-ledger allowlist: {item.filename}"
                )
        manifest = _json(archive.read("manifest.json"))
        if (
            not isinstance(manifest, dict)
            or manifest.get("schema_version") not in SUPPORTED_SCHEMA_VERSIONS
        ):
            raise ValueError("unsupported archive manifest")
        manifest_version = str(manifest["schema_version"])
        checkpoint_names = {
            name for name in names if name.startswith("ledger/checkpoints/")
        }
        if manifest_version == LEGACY_SCHEMA_VERSION and checkpoint_names:
            raise ValueError("legacy archives cannot declare checkpoint files")
        declared = manifest.get("files")
        if not isinstance(declared, list):
            raise ValueError("archive file manifest is invalid")
        content: dict[str, bytes] = {}
        conflicts: list[str] = []
        declared_names: set[str] = set()
        for entry in declared:
            if not isinstance(entry, dict) or not _allowed(str(entry.get("path", ""))):
                raise ValueError("archive declaration is outside the allowlist")
            name = str(entry["path"])
            if name in declared_names:
                raise ValueError("archive declaration contains duplicate paths")
            declared_names.add(name)
            value = archive.read(name)
            if len(value) != entry.get("bytes") or _sha(value) != entry.get("sha256"):
                raise ValueError(f"archive checksum mismatch: {name}")
            _validate_content(name, value)
            content[name] = value
            destination = _safe_destination(ledger, name)
            if destination.exists() and destination.read_bytes() != value:
                conflicts.append(name)
        if declared_names != set(names) - {"manifest.json"}:
            raise ValueError("archive contents do not match its manifest")
        archive_checkpoint_status = _checkpoint_overlay_status(content)
        checkpoint_record_count = sum(
            name.startswith("ledger/checkpoints/lc_") for name in content
        )
        if checkpoint_record_count != archive_checkpoint_status["checkpoint_count"]:
            raise ValueError("archive contains checkpoint records outside the linked chain")
        checkpoint_recovery = _checkpoint_recovery_summary(archive_checkpoint_status)
        if manifest_version == SCHEMA_VERSION:
            if manifest.get("checkpoint_recovery") != checkpoint_recovery:
                raise ValueError("archive checkpoint recovery declaration is invalid")
        restore_blocked_reason = None
        try:
            _checkpoint_overlay_status(content, ledger=ledger)
        except (OSError, ValueError, KeyError) as exc:
            restore_blocked_reason = (
                "restore would leave the local checkpoint chain invalid: " + str(exc)
            )
        preview = {
            "schema_version": manifest_version,
            "verified": True,
            "file_count": len(content),
            "total_bytes": sum(len(value) for value in content.values()),
            "conflicts": sorted(conflicts),
            "requires_replace_confirmation": bool(conflicts),
            "restore_preview_token": _restore_preview_token(content, ledger=ledger),
            "excluded_categories": manifest.get("excluded", []),
            "checkpoint_recovery": checkpoint_recovery,
            "restore_blocked_reason": restore_blocked_reason,
        }
        return preview, content


def inspect_archive(data: bytes, *, ledger: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    with runtime.USER_STATE_LOCK:
        _recover_unlocked(Path(ledger))
        return _inspect_archive_unlocked(data, ledger=Path(ledger))


def restore_archive(
    data: bytes,
    *,
    ledger: Path,
    replace: bool = False,
    preview_token: str | None = None,
) -> dict[str, Any]:
    ledger = Path(ledger)
    with runtime.USER_STATE_LOCK:
        _recover_unlocked(ledger)
        preview, content = _inspect_archive_unlocked(data, ledger=ledger)
        if preview["restore_blocked_reason"] is not None:
            raise ValueError(preview["restore_blocked_reason"])
        if preview["conflicts"] and not replace:
            raise FileExistsError(
                "restore has conflicts; preview and explicitly confirm replacement"
            )
        if (
            preview["conflicts"]
            and replace
            and preview_token != preview["restore_preview_token"]
        ):
            raise ValueError("restore preview changed; preview again before replacing files")
        ledger.mkdir(parents=True, exist_ok=True)

        # Keep valid state as a verified escape hatch. If the current ledger is
        # exactly what this restore is repairing, preserve its raw allowlisted
        # bytes without mislabeling that quarantine copy as restorable.
        backup_verified = True
        try:
            before_data, _ = _export_archive_unlocked(ledger)
        except (KeyError, TypeError, ValueError, sqlite3.DatabaseError):
            before_data, _ = _export_archive_unlocked(ledger, validate_content=False)
            backup_verified = False
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        backup_kind = "pre-restore" if backup_verified else "pre-restore-unverified"
        backup_name = f"{backup_kind}-{stamp}-{_sha(before_data)[:12]}.zip"
        backup_path = _backup_root(ledger) / backup_name
        _atomic_bytes(backup_path, before_data)
        if backup_verified:
            _inspect_archive_unlocked(backup_path.read_bytes(), ledger=ledger)

        root = _recovery_root(ledger)
        root.mkdir(parents=True, exist_ok=False)
        _fsync_dir(root.parent)
        staging = root / "staging"
        backup = root / "backup"
        entries: list[dict[str, Any]] = []
        for name, value in sorted(content.items()):
            destination = _safe_destination(ledger, name)
            relative = Path(*PurePosixPath(name).relative_to("ledger").parts)
            _atomic_bytes(staging / relative, value)
            existed = destination.exists()
            if existed:
                _atomic_bytes(backup / relative, destination.read_bytes())
            entries.append({"path": name, "existed": existed})
        journal: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "phase": "prepared",
            "files": entries,
            "applied_count": 0,
            "pre_restore_backup": backup_name,
        }
        _write_journal(root, journal)
        journal["phase"] = "applying"
        _write_journal(root, journal)
        try:
            for index, name in enumerate(sorted(content), start=1):
                destination = _safe_destination(ledger, name)
                relative = Path(*PurePosixPath(name).relative_to("ledger").parts)
                staged = staging / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                os.replace(staged, destination)
                _fsync_dir(destination.parent)
                journal["applied_count"] = index
                _write_journal(root, journal)
            final_checkpoint_status = ledger_checkpoints.status(ledger)
            journal["phase"] = "committed"
            _write_journal(root, journal)
        except BaseException:
            _recover_unlocked(ledger)
            raise
        _remove_recovery(root)
        return {
            **preview,
            "restored": True,
            "replaced_conflicts": bool(preview["conflicts"]),
            "pre_restore_backup": backup_name,
            "pre_restore_backup_verified": backup_verified,
            "checkpoint_recovery": _checkpoint_recovery_summary(final_checkpoint_status),
        }
