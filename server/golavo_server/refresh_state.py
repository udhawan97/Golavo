"""Durable refresh state, immutable generations and atomic activation."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from golavo_server import runtime

STATE_SCHEMA_VERSION = "0.1.0"
GENERATION_SCHEMA_VERSION = "0.1.0"
_LOCK = threading.RLock()


def _root() -> Path:
    root = runtime.refresh_dir()
    if root is None:
        raise RuntimeError("runtime refresh requires a writable GOLAVO_DATA_DIR")
    return root


def state_path() -> Path:
    return _root() / "state.json"


def pointer_path() -> Path:
    return _root() / "active.json"


def generations_dir() -> Path:
    return _root() / "generations"


def staging_dir() -> Path:
    return _root() / "staging"


def quarantine_dir() -> Path:
    return _root() / "quarantine"


def generation_dir(generation_id: str) -> Path:
    if not generation_id.startswith("g_") or len(generation_id) != 66:
        raise ValueError("invalid generation id")
    return generations_dir() / generation_id


def _fsync_dir(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


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
    root = _root()
    root.mkdir(parents=True, exist_ok=True)
    lock_path = root / name
    with _LOCK, lock_path.open("a+b") as handle:
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            if handle.tell() == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)  # type: ignore[attr-defined]
            try:
                yield
            finally:
                handle.seek(0)
                unlock = msvcrt.LK_UNLCK  # type: ignore[attr-defined]
                msvcrt.locking(  # type: ignore[attr-defined]
                    handle.fileno(), unlock, 1
                )
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def activation_lock() -> Iterator[None]:
    """Serialize active-pointer changes across local sidecar processes."""
    with _file_lock(".activation.lock"):
        yield


@contextmanager
def refresh_job_lock() -> Iterator[None]:
    """Permit only one generation builder for a user data root."""
    with _file_lock(".job.lock"):
        yield


def default_state() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sources": {},
        "job": None,
        "last_error": None,
    }


def load_state() -> dict[str, Any]:
    try:
        payload = json.loads(state_path().read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return default_state()
    if not isinstance(payload, dict) or payload.get("schema_version") != STATE_SCHEMA_VERSION:
        return default_state()
    if not isinstance(payload.get("sources"), dict):
        payload["sources"] = {}
    return payload


def save_state(payload: dict[str, Any]) -> None:
    payload = {**payload, "schema_version": STATE_SCHEMA_VERSION}
    with _LOCK:
        _atomic_json(state_path(), payload)


def load_pointer() -> dict[str, Any] | None:
    try:
        payload = json.loads(pointer_path().read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    return payload if isinstance(payload, dict) else None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_generation(path: Path) -> dict[str, Any]:
    path = Path(path)
    try:
        manifest = json.loads((path / "generation.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        raise ValueError(f"invalid generation manifest at {path}") from exc
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version") != GENERATION_SCHEMA_VERSION
    ):
        raise ValueError(f"unsupported generation schema at {path}")
    if manifest.get("generation_id") != path.name:
        raise ValueError(f"generation id/path mismatch at {path}")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ValueError(f"generation has no artifacts at {path}")
    declared: set[str] = set()
    actual_hashes: dict[str, str] = {}
    for entry in artifacts:
        if not isinstance(entry, dict):
            raise ValueError("invalid generation artifact entry")
        relative = Path(str(entry.get("path", "")))
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise ValueError("unsafe generation artifact path")
        target = path / relative
        if target.is_symlink() or not target.is_file():
            raise ValueError(f"generation artifact missing: {relative}")
        expected = str(entry.get("sha256", ""))
        actual = _sha256(target)
        if actual != expected:
            raise ValueError(f"generation artifact hash mismatch: {relative}")
        relative_name = relative.as_posix()
        declared.add(relative_name)
        actual_hashes[relative_name] = actual
    required = {"index/matches_index.parquet", "index/matches_index.meta.json"}
    if not required.issubset(declared):
        raise ValueError(
            f"generation is missing required index files: {sorted(required - declared)}"
        )
    # Cross-bind the independently written index metadata to the actual parquet
    # bytes. The parquet hash above is reused, so this adds no second large-file
    # read and never enters the per-match request path.
    try:
        index_meta = json.loads(
            (path / "index" / "matches_index.meta.json").read_text(encoding="utf-8")
        )
    except (OSError, ValueError, TypeError) as exc:
        raise ValueError("generation index metadata is invalid") from exc
    expected_parquet = (
        index_meta.get("parquet_sha256") if isinstance(index_meta, dict) else None
    )
    actual_parquet = actual_hashes["index/matches_index.parquet"]
    if (
        not isinstance(expected_parquet, str)
        or len(expected_parquet) != 64
        or any(character not in "0123456789abcdef" for character in expected_parquet)
        or expected_parquet != actual_parquet
    ):
        raise ValueError("generation parquet hash does not match index metadata")
    present = {
        file.relative_to(path).as_posix()
        for file in path.rglob("*")
        if file.is_file() and file.name != "generation.json"
    }
    if present != declared:
        raise ValueError(
            f"generation declaration mismatch (missing={sorted(declared - present)}, "
            f"undeclared={sorted(present - declared)})"
        )
    snapshots = manifest.get("source_snapshots")
    if not isinstance(snapshots, list) or len(snapshots) < 2:
        raise ValueError(
            "generation must retain at least the international and World Cup snapshots"
        )
    approved = {
        "martj42-international-results",
        "openfootball-worldcup-json",
        "openfootball-football-json",
    }
    for snapshot in snapshots:
        if not isinstance(snapshot, dict) or snapshot.get("schema_version") != "0.1.0":
            raise ValueError("invalid source snapshot receipt")
        source_id = snapshot.get("source_id")
        ref = snapshot.get("upstream_ref")
        if source_id not in approved or not isinstance(ref, str) or len(ref) != 40:
            raise ValueError("generation contains an unapproved or unpinned source snapshot")
        if snapshot.get("license") != "CC0-1.0" or not isinstance(snapshot.get("files"), list):
            raise ValueError("generation source snapshot failed its license/file contract")
        for receipt in snapshot["files"]:
            if not isinstance(receipt, dict):
                raise ValueError("invalid source file receipt")
            relative = Path(str(receipt.get("path", "")))
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("unsafe source receipt path")
            raw_relative = Path("raw") / str(source_id) / ref / relative
            if raw_relative.as_posix() not in declared:
                raise ValueError(
                    f"source receipt bytes are not generation artifacts: {raw_relative}"
                )
            if _sha256(path / raw_relative) != receipt.get("sha256"):
                raise ValueError(f"source receipt hash mismatch: {raw_relative}")
    return manifest


def active_generation() -> tuple[Path | None, bool]:
    """Return the verified active generation and whether LKG fallback was used."""
    pointer = load_pointer()
    if pointer is None:
        return None, False
    active = pointer.get("active_generation_id")
    previous = pointer.get("previous_generation_id")
    if isinstance(active, str):
        try:
            path = generation_dir(active)
            verify_generation(path)
            return path, False
        except (OSError, ValueError):
            pass
    if isinstance(previous, str):
        try:
            path = generation_dir(previous)
            verify_generation(path)
            return path, True
        except (OSError, ValueError):
            pass
    return None, False


def active_pack_dir() -> Path | None:
    active, _ = active_generation()
    if active is None:
        return None
    pack = active / "packs" / "internationals"
    return pack if (pack / "manifest.json").is_file() else None


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
    return destination


def activate_generation(generation_id: str, *, activated_at_utc: str) -> dict[str, Any]:
    with activation_lock():
        target = generation_dir(generation_id)
        verify_generation(target)
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
        return pointer


def rollback(*, activated_at_utc: str) -> dict[str, Any]:
    with activation_lock():
        pointer = load_pointer()
        if pointer is None or not isinstance(pointer.get("previous_generation_id"), str):
            raise ValueError("no previous refresh generation is available")
        previous = str(pointer["previous_generation_id"])
        current = pointer.get("active_generation_id")
        verify_generation(generation_dir(previous))
        replacement = {
            "schema_version": STATE_SCHEMA_VERSION,
            "active_generation_id": previous,
            "previous_generation_id": current if isinstance(current, str) else None,
            "activated_at_utc": activated_at_utc,
            "rollback": True,
        }
        _atomic_json(pointer_path(), replacement)
        return replacement


def clean_staging(path: Path) -> None:
    path = Path(path)
    try:
        path.relative_to(staging_dir())
    except ValueError:
        raise ValueError("refusing to clean outside refresh staging") from None
    shutil.rmtree(path, ignore_errors=True)
