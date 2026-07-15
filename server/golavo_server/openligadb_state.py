"""Durable state and immutable generations for the isolated ODbL overlay."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from golavo_server import openligadb_source, runtime

STATE_SCHEMA_VERSION = "0.1.0"
GENERATION_SCHEMA_VERSION = "0.1.0"
SETTINGS_SCHEMA_VERSION = "0.1.0"
_LOCK = threading.RLock()


def root() -> Path:
    value = runtime.openligadb_dir()
    if value is None:
        raise RuntimeError("OpenLigaDB overlay requires a writable application data path")
    return value


def settings_path() -> Path:
    return root() / "settings.json"


def state_path() -> Path:
    return root() / "state.json"


def pointer_path() -> Path:
    return root() / "active.json"


def generations_dir() -> Path:
    return root() / "generations"


def staging_dir() -> Path:
    return root() / "staging"


def quarantine_dir() -> Path:
    return root() / "quarantine"


def generation_dir(generation_id: str) -> Path:
    if not generation_id.startswith("g_") or len(generation_id) != 66:
        raise ValueError("invalid OpenLigaDB generation id")
    return generations_dir() / generation_id


def _fsync_dir(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, prefix=path.name + ".", delete=False
    ) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    os.replace(temporary, path)
    _fsync_dir(path.parent)


@contextmanager
def _file_lock(name: str) -> Iterator[None]:
    target_root = root()
    target_root.mkdir(parents=True, exist_ok=True)
    lock_path = target_root / name
    with _LOCK, lock_path.open("a+b") as handle:
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            if handle.read(1) == b"":
                handle.seek(0)
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)  # type: ignore[attr-defined]
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(  # type: ignore[attr-defined]
                    handle.fileno(),
                    msvcrt.LK_UNLCK,
                    1,  # type: ignore[attr-defined]
                )
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def job_lock() -> Iterator[None]:
    with _file_lock(".job.lock"):
        yield


@contextmanager
def lifecycle_lock() -> Iterator[None]:
    with _file_lock(".lifecycle.lock"):
        yield


def default_settings() -> dict[str, Any]:
    return {
        "schema_version": SETTINGS_SCHEMA_VERSION,
        "enabled": False,
        "refresh_policy": "manual",
        "selected_competitions": list(openligadb_source.COMPETITION_SHORTCUTS),
        "license_accepted_at_utc": None,
    }


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def load_settings() -> dict[str, Any]:
    try:
        value = _read_json(settings_path())
    except RuntimeError:
        return default_settings()
    if value is None or value.get("schema_version") != SETTINGS_SCHEMA_VERSION:
        return default_settings()
    enabled = value.get("enabled") is True
    policy = value.get("refresh_policy")
    selected = value.get("selected_competitions")
    accepted = value.get("license_accepted_at_utc")
    if policy not in ("manual", "while_open"):
        return default_settings()
    if (
        not isinstance(selected, list)
        or not selected
        or not all(isinstance(item, str) for item in selected)
        or len(selected) != len(set(selected))
        or set(selected) - set(openligadb_source.COMPETITION_SHORTCUTS)
    ):
        return default_settings()
    if accepted is not None and not isinstance(accepted, str):
        return default_settings()
    # A corrupt or hand-edited state can never bypass license consent.
    if enabled and not accepted:
        enabled = False
    return {
        "schema_version": SETTINGS_SCHEMA_VERSION,
        "enabled": enabled,
        "refresh_policy": policy,
        "selected_competitions": selected,
        "license_accepted_at_utc": accepted,
    }


def save_settings(value: dict[str, Any]) -> dict[str, Any]:
    selected = value.get("selected_competitions")
    if (
        not isinstance(selected, list)
        or not selected
        or not all(isinstance(item, str) for item in selected)
        or len(selected) != len(set(selected))
        or set(selected) - set(openligadb_source.COMPETITION_SHORTCUTS)
    ):
        raise ValueError("selected_competitions must be a non-empty allowlisted set")
    policy = value.get("refresh_policy")
    if policy not in ("manual", "while_open"):
        raise ValueError("refresh_policy must be manual or while_open")
    accepted = value.get("license_accepted_at_utc")
    if value.get("enabled") is True and not isinstance(accepted, str):
        raise ValueError("ODbL disclosure must be accepted before enabling the overlay")
    payload = {
        "schema_version": SETTINGS_SCHEMA_VERSION,
        "enabled": value.get("enabled") is True,
        "refresh_policy": policy,
        "selected_competitions": selected,
        "license_accepted_at_utc": accepted if isinstance(accepted, str) else None,
    }
    with _LOCK:
        _atomic_json(settings_path(), payload)
    return payload


def default_state() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "health": "disabled",
        "last_checked_at_utc": None,
        "last_activated_at_utc": None,
        "next_check_after_utc": None,
        "failure_count": 0,
        "capabilities": [],
        "job": None,
        "last_error": None,
    }


def load_state() -> dict[str, Any]:
    try:
        value = _read_json(state_path())
    except RuntimeError:
        return default_state()
    if value is None or value.get("schema_version") != STATE_SCHEMA_VERSION:
        return default_state()
    return {**default_state(), **value, "schema_version": STATE_SCHEMA_VERSION}


def save_state(value: dict[str, Any]) -> None:
    with _LOCK:
        _atomic_json(state_path(), {**value, "schema_version": STATE_SCHEMA_VERSION})


def load_pointer() -> dict[str, Any] | None:
    try:
        value = _read_json(pointer_path())
    except RuntimeError:
        return None
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


_WRITE_ACTIONS = frozenset(
    value
    for value in (
        getattr(sqlite3, "SQLITE_INSERT", None),
        getattr(sqlite3, "SQLITE_UPDATE", None),
        getattr(sqlite3, "SQLITE_DELETE", None),
        getattr(sqlite3, "SQLITE_CREATE_TABLE", None),
        getattr(sqlite3, "SQLITE_DROP_TABLE", None),
        getattr(sqlite3, "SQLITE_ALTER_TABLE", None),
        getattr(sqlite3, "SQLITE_ATTACH", None),
        getattr(sqlite3, "SQLITE_DETACH", None),
        getattr(sqlite3, "SQLITE_PRAGMA", None),
    )
    if isinstance(value, int)
)


def open_readonly_database(path: Path) -> sqlite3.Connection:
    """Open only the isolated database and deny writes, ATTACH and PRAGMA."""
    resolved = Path(path).resolve(strict=True)
    connection = sqlite3.connect(f"file:{resolved.as_posix()}?mode=ro&immutable=1", uri=True)
    connection.row_factory = sqlite3.Row

    def authorizer(
        action: int, _arg1: str | None, _arg2: str | None, _db: str | None, _src: str | None
    ) -> int:
        return sqlite3.SQLITE_DENY if action in _WRITE_ACTIONS else sqlite3.SQLITE_OK

    connection.set_authorizer(authorizer)
    return connection


def _verify_database(path: Path) -> None:
    # Integrity validation happens before the restrictive read authorizer is set.
    connection = sqlite3.connect(f"file:{path.resolve(strict=True).as_posix()}?mode=ro", uri=True)
    try:
        if connection.execute("PRAGMA quick_check").fetchone() != ("ok",):
            raise ValueError("OpenLigaDB SQLite integrity check failed")
        tables = {
            str(row[0])
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        required = {"metadata", "raw_responses", "competitions", "groups", "teams", "matches"}
        if not required.issubset(tables):
            raise ValueError(f"OpenLigaDB database is missing tables: {sorted(required - tables)}")
        metadata = dict(connection.execute("SELECT key, value FROM metadata"))
        if (
            metadata.get("source_id") != openligadb_source.SOURCE_ID
            or metadata.get("license") != openligadb_source.LICENSE_ID
            or metadata.get("display_only") != "true"
        ):
            raise ValueError("OpenLigaDB database boundary metadata is invalid")
        for table in required:
            columns = {
                str(row[1]).casefold() for row in connection.execute(f"PRAGMA table_info({table})")
            }
            if {"core_match_id", "artifact_id", "forecast_id"} & columns:
                raise ValueError("OpenLigaDB database contains a forbidden cross-boundary id")
    finally:
        connection.close()


def verify_generation(path: Path) -> dict[str, Any]:
    target = Path(path)
    manifest = _read_json(target / "generation.json")
    if (
        manifest is None
        or manifest.get("schema_version") != GENERATION_SCHEMA_VERSION
        or manifest.get("generation_id") != target.name
        or manifest.get("source_id") != openligadb_source.SOURCE_ID
        or manifest.get("license") != openligadb_source.LICENSE_ID
        or manifest.get("display_only") is not True
    ):
        raise ValueError(f"invalid OpenLigaDB generation manifest at {target}")
    revision = manifest.get("content_revision")
    if not isinstance(revision, str) or len(revision) != 64:
        raise ValueError("OpenLigaDB generation has an invalid content revision")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ValueError("OpenLigaDB generation has no artifacts")
    declared: set[str] = set()
    for item in artifacts:
        if not isinstance(item, dict):
            raise ValueError("invalid OpenLigaDB generation artifact")
        relative = Path(str(item.get("path") or ""))
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise ValueError("unsafe OpenLigaDB generation artifact path")
        artifact = target / relative
        if artifact.is_symlink() or not artifact.is_file():
            raise ValueError(f"missing OpenLigaDB generation artifact: {relative}")
        if _sha256(artifact) != item.get("sha256"):
            raise ValueError(f"OpenLigaDB generation artifact hash mismatch: {relative}")
        declared.add(relative.as_posix())
    if not {"overlay.sqlite3", "LICENSE.json"}.issubset(declared):
        raise ValueError("OpenLigaDB generation lacks its database or license notice")
    if not any(path.startswith("raw/") for path in declared):
        raise ValueError("OpenLigaDB generation does not retain raw responses")
    receipts = manifest.get("raw_receipts")
    if not isinstance(receipts, list) or not receipts:
        raise ValueError("OpenLigaDB generation has no raw response receipts")
    season = str(manifest.get("season") or "")
    seen_endpoints: set[str] = set()
    for receipt in receipts:
        if not isinstance(receipt, dict):
            raise ValueError("OpenLigaDB generation has an invalid raw receipt")
        endpoint = str(receipt.get("endpoint") or "")
        relative = Path(str(receipt.get("path") or ""))
        artifact_relative = Path("raw") / relative
        if (
            endpoint in seen_endpoints
            or not openligadb_source.approved_path(endpoint, season=season)
            or relative.is_absolute()
            or ".." in relative.parts
            or artifact_relative.as_posix() not in declared
            or _sha256(target / artifact_relative) != receipt.get("sha256")
        ):
            raise ValueError("OpenLigaDB raw receipt does not match retained approved bytes")
        seen_endpoints.add(endpoint)
    present = {
        item.relative_to(target).as_posix()
        for item in target.rglob("*")
        if item.is_file() and item.name != "generation.json"
    }
    if present != declared:
        raise ValueError("OpenLigaDB generation contains undeclared or missing bytes")
    _verify_database(target / "overlay.sqlite3")
    return manifest


def active_generation() -> tuple[Path | None, bool]:
    pointer = load_pointer()
    if pointer is None:
        return None, False
    for field, fallback in (("active_generation_id", False), ("previous_generation_id", True)):
        generation_id = pointer.get(field)
        if isinstance(generation_id, str):
            try:
                path = generation_dir(generation_id)
                verify_generation(path)
                return path, fallback
            except (OSError, ValueError):
                continue
    return None, False


def active_database() -> Path | None:
    active, _ = active_generation()
    return active / "overlay.sqlite3" if active is not None else None


def install_generation(staging: Path, generation_id: str) -> Path:
    destination = generation_dir(generation_id)
    generations_dir().mkdir(parents=True, exist_ok=True)
    if destination.exists():
        verify_generation(destination)
        shutil.rmtree(staging, ignore_errors=True)
        return destination
    os.replace(staging, destination)
    _fsync_dir(generations_dir())
    verify_generation(destination)
    if os.name != "nt":
        for item in destination.rglob("*"):
            if item.is_file():
                try:
                    item.chmod(0o444)
                except OSError:
                    pass
    return destination


def _prune_generations(pointer: dict[str, Any]) -> None:
    keep = {
        str(value)
        for value in (pointer.get("active_generation_id"), pointer.get("previous_generation_id"))
        if isinstance(value, str)
    }
    if not generations_dir().is_dir():
        return
    for candidate in generations_dir().iterdir():
        if candidate.is_dir() and candidate.name not in keep:
            shutil.rmtree(candidate, ignore_errors=True)


def activate_generation(generation_id: str, *, activated_at_utc: str) -> dict[str, Any]:
    with lifecycle_lock():
        verify_generation(generation_dir(generation_id))
        current = load_pointer() or {}
        old_active = current.get("active_generation_id")
        previous = (
            old_active
            if isinstance(old_active, str) and old_active != generation_id
            else current.get("previous_generation_id")
        )
        pointer = {
            "schema_version": STATE_SCHEMA_VERSION,
            "active_generation_id": generation_id,
            "previous_generation_id": previous,
            "activated_at_utc": activated_at_utc,
        }
        _atomic_json(pointer_path(), pointer)
        _prune_generations(pointer)
        return pointer


def rollback(*, activated_at_utc: str) -> dict[str, Any]:
    with lifecycle_lock():
        pointer = load_pointer()
        if pointer is None or not isinstance(pointer.get("previous_generation_id"), str):
            raise ValueError("no previous OpenLigaDB generation is available")
        previous = str(pointer["previous_generation_id"])
        current = pointer.get("active_generation_id")
        verify_generation(generation_dir(previous))
        updated = {
            "schema_version": STATE_SCHEMA_VERSION,
            "active_generation_id": previous,
            "previous_generation_id": current if isinstance(current, str) else None,
            "activated_at_utc": activated_at_utc,
            "rollback": True,
        }
        _atomic_json(pointer_path(), updated)
        return updated


def clean_staging(path: Path) -> None:
    try:
        path.resolve().relative_to(staging_dir().resolve())
    except ValueError as exc:
        raise ValueError("refusing to clean outside OpenLigaDB staging") from exc
    shutil.rmtree(path, ignore_errors=True)


def storage_bytes() -> int:
    try:
        target = root()
    except RuntimeError:
        return 0
    total = 0
    if target.is_dir():
        for item in target.rglob("*"):
            try:
                if item.is_file() and not item.name.startswith("."):
                    total += item.stat().st_size
            except OSError:
                continue
    return total


def delete_overlay_data() -> None:
    """Remove settings, raw bytes and databases without touching sibling data."""
    with lifecycle_lock():
        target = root().resolve()
        expected = runtime.openligadb_dir()
        if expected is None or target != expected.resolve() or target.name != "openligadb":
            raise RuntimeError("refusing to delete outside the OpenLigaDB overlay root")
        for name in (
            "settings.json",
            "state.json",
            "active.json",
            "generations",
            "staging",
            "quarantine",
        ):
            candidate = target / name
            if candidate.is_dir():
                shutil.rmtree(candidate, ignore_errors=False)
            else:
                candidate.unlink(missing_ok=True)
