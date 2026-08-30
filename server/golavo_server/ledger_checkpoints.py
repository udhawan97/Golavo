"""Hash-chained local checkpoints over immutable forecast artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from golavo_core.artifacts import load_verified_artifact

from golavo_server import runtime

SCHEMA_VERSION = "0.2.0"
LEGACY_SCHEMA_VERSION = "0.1.0"
SUPPORTED_SCHEMA_VERSIONS = frozenset({LEGACY_SCHEMA_VERSION, SCHEMA_VERSION})
LIMITS = [
    "The chain detects changes relative to earlier local checkpoints; it does not prove "
    "external authenticity.",
    "It cannot prove that an artifact was created before a particular real-world event.",
    "A checkpoint records the artifacts present at creation time and does not prevent "
    "explicit later removal.",
    "A verified forecast-ledger archive can preserve and recover the linked chain, but it "
    "cannot recover artifact bytes that were already absent when the archive was made.",
    "Optional external anchoring remains a separate release gate.",
]
_LOCK = threading.RLock()
_ARTIFACT_ID = re.compile(r"^fa_[0-9a-f]{20}$")


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _digest(value: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _root(ledger: Path) -> Path:
    ledger = Path(ledger)
    if ledger.is_symlink():
        raise ValueError("ledger root must not be a symlink")
    root = ledger / "checkpoints"
    if root.is_symlink() or root.resolve(strict=False).parent != ledger.resolve(strict=False):
        raise ValueError("checkpoint directory is unsafe")
    return root


def _owned_checkpoint_path(ledger: Path, name: str) -> Path:
    root = _root(ledger)
    path = root / name
    if path.parent != root or path.is_symlink():
        raise ValueError("checkpoint path is unsafe")
    return path


def validate_paths(ledger: Path) -> None:
    """Validate checkpoint path ownership without requiring current bytes to verify."""

    with runtime.USER_STATE_LOCK:
        with _LOCK:
            root = _root(Path(ledger))
            _owned_checkpoint_path(ledger, "head.json")
            if root.exists():
                for path in root.glob("lc_*.json"):
                    _owned_checkpoint_path(ledger, path.name)


def _artifact_path(ledger: Path, artifact_id: Any) -> Path:
    """Resolve only canonical artifact IDs to direct, non-symlink ledger children."""

    if not isinstance(artifact_id, str) or not _ARTIFACT_ID.fullmatch(artifact_id):
        raise ValueError("checkpoint artifact ID is invalid")
    ledger = Path(ledger)
    path = ledger / f"{artifact_id}.json"
    if path.parent != ledger or path.is_symlink():
        raise ValueError("checkpointed artifact path is unsafe")
    return path


def _fsync_dir(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic(path: Path, value: dict[str, Any]) -> None:
    if path.is_symlink():
        raise ValueError("checkpoint path is unsafe")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(json.dumps(value, indent=2, sort_keys=True).encode() + b"\n")
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    try:
        os.replace(temporary, path)
        _fsync_dir(path.parent)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _checkpoint(path: Path, expected: str) -> dict[str, Any]:
    if path.is_symlink():
        raise ValueError("checkpoint path is unsafe")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"checkpoint is unreadable: {expected}") from exc
    if (
        not isinstance(value, dict)
        or value.get("schema_version") not in SUPPORTED_SCHEMA_VERSIONS
    ):
        raise ValueError("checkpoint schema is invalid")
    body = {key: item for key, item in value.items() if key != "checkpoint_sha256"}
    if value.get("checkpoint_sha256") != expected or _digest(body) != expected:
        raise ValueError("checkpoint hash mismatch")
    previous = value.get("previous_checkpoint_sha256")
    if previous is not None and not _is_sha256(previous):
        raise ValueError("checkpoint predecessor is invalid")
    entries = value.get("artifacts")
    if not isinstance(entries, list):
        raise ValueError("checkpoint artifact list is invalid")
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("checkpoint artifact entry is invalid")
        artifact_id = entry.get("artifact_id")
        digest = entry.get("sha256")
        if artifact_id in seen or not _is_sha256(digest):
            raise ValueError("checkpoint artifact entry is invalid")
        _artifact_path(path.parent.parent, artifact_id)
        seen.add(artifact_id)
    limits = value.get("limits")
    if not isinstance(limits, list) or not all(isinstance(item, str) for item in limits):
        raise ValueError("checkpoint limits are invalid")
    if value["schema_version"] == SCHEMA_VERSION:
        count = value.get("artifact_count")
        previous_schema = value.get("previous_schema_version")
        if isinstance(count, bool) or not isinstance(count, int) or count != len(entries):
            raise ValueError("checkpoint artifact count is invalid")
        if previous is None:
            if previous_schema is not None:
                raise ValueError("checkpoint predecessor schema is invalid")
        elif previous_schema not in SUPPORTED_SCHEMA_VERSIONS:
            raise ValueError("checkpoint predecessor schema is invalid")
    return value


def _status_unlocked(ledger: Path) -> dict[str, Any]:
    ledger = Path(ledger)
    root = _root(ledger)
    head_path = _owned_checkpoint_path(ledger, "head.json")
    if not head_path.exists():
        if root.exists() and any(root.glob("lc_*.json")):
            raise ValueError("checkpoint head is missing while checkpoint records remain")
        return {
            "schema_version": SCHEMA_VERSION,
            "verified": True,
            "checkpoint_count": 0,
            "head": None,
            "head_schema_version": None,
            "checkpoint_schema_versions": [],
            "legacy_checkpoint_count": 0,
            "migration_required": False,
            "missing_artifacts": [],
            "uncheckpointed_artifacts": sorted(path.stem for path in ledger.glob("fa_*.json")),
            "limits": LIMITS,
        }
    try:
        head_value = json.loads(head_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("checkpoint head is unreadable") from exc
    head = head_value.get("checkpoint_sha256") if isinstance(head_value, dict) else None
    if (
        not isinstance(head_value, dict)
        or head_value.get("schema_version") not in SUPPORTED_SCHEMA_VERSIONS
        or not _is_sha256(head)
    ):
        raise ValueError("checkpoint head is invalid")
    head_schema_version = str(head_value["schema_version"])
    current: str | None = head
    expected_schema_version: str | None = head_schema_version
    seen: set[str] = set()
    schema_versions: list[str] = []
    missing: set[str] = set()
    head_artifacts: set[str] = set()
    while current:
        if current in seen:
            raise ValueError("checkpoint chain contains a cycle")
        seen.add(current)
        value = _checkpoint(_owned_checkpoint_path(ledger, f"lc_{current}.json"), current)
        schema_version = str(value["schema_version"])
        if expected_schema_version is not None and schema_version != expected_schema_version:
            raise ValueError("checkpoint predecessor schema does not match its link")
        schema_versions.append(schema_version)
        entries = value["artifacts"]
        if len(seen) == 1:
            head_artifacts = {str(entry["artifact_id"]) for entry in entries}
        for entry in entries:
            artifact_id = str(entry["artifact_id"])
            artifact_path = _artifact_path(ledger, artifact_id)
            if not artifact_path.exists():
                missing.add(artifact_id)
            elif hashlib.sha256(artifact_path.read_bytes()).hexdigest() != entry["sha256"]:
                raise ValueError(f"checkpointed artifact changed: {artifact_id}")
        current = value.get("previous_checkpoint_sha256")
        expected_schema_version = (
            value.get("previous_schema_version")
            if schema_version == SCHEMA_VERSION and current is not None
            else None
        )
    current_artifacts = {path.stem for path in ledger.glob("fa_*.json")}
    return {
        "schema_version": SCHEMA_VERSION,
        "verified": True,
        "checkpoint_count": len(seen),
        "head": head,
        "head_schema_version": head_schema_version,
        "checkpoint_schema_versions": sorted(set(schema_versions)),
        "legacy_checkpoint_count": sum(
            version != SCHEMA_VERSION for version in schema_versions
        ),
        "migration_required": head_schema_version != SCHEMA_VERSION,
        "missing_artifacts": sorted(missing),
        "uncheckpointed_artifacts": sorted(current_artifacts - head_artifacts),
        "limits": LIMITS,
    }


def create(ledger: Path) -> dict[str, Any]:
    with runtime.USER_STATE_LOCK:
        with _LOCK:
            ledger = Path(ledger)
            # Verify every predecessor before creating any bytes. A corrupt chain is
            # immutable evidence of a problem, never a base for a new head.
            verified = _status_unlocked(ledger)
            artifacts: list[dict[str, str]] = []
            for path in sorted(ledger.glob("fa_*.json")):
                if path.is_symlink():
                    raise ValueError("checkpointed artifact path is unsafe")
                artifact = load_verified_artifact(path)
                artifacts.append(
                    {
                        "artifact_id": str(artifact["artifact_id"]),
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    }
                )
            body: dict[str, Any] = {
                "schema_version": SCHEMA_VERSION,
                "created_at_utc": datetime.now(UTC)
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z"),
                "previous_checkpoint_sha256": verified["head"],
                "previous_schema_version": verified["head_schema_version"],
                "artifact_count": len(artifacts),
                "artifacts": artifacts,
                "limits": LIMITS,
            }
            digest = _digest(body)
            checkpoint = {**body, "checkpoint_sha256": digest}
            checkpoint_path = _owned_checkpoint_path(ledger, f"lc_{digest}.json")
            created_checkpoint = not checkpoint_path.exists()
            _atomic(checkpoint_path, checkpoint)
            try:
                _atomic(
                    _owned_checkpoint_path(ledger, "head.json"),
                    {"schema_version": SCHEMA_VERSION, "checkpoint_sha256": digest},
                )
            except BaseException:
                if created_checkpoint:
                    checkpoint_path.unlink(missing_ok=True)
                    _fsync_dir(checkpoint_path.parent)
                raise
            return checkpoint


def status(ledger: Path) -> dict[str, Any]:
    with runtime.USER_STATE_LOCK:
        with _LOCK:
            return _status_unlocked(Path(ledger))


def recovery_files(ledger: Path) -> list[Path]:
    """Return only the verified, head-reachable files needed to recover the chain."""

    with runtime.USER_STATE_LOCK:
        with _LOCK:
            ledger = Path(ledger)
            verified = _status_unlocked(ledger)
            current = verified["head"]
            if current is None:
                return []
            files = [_owned_checkpoint_path(ledger, "head.json")]
            while current is not None:
                path = _owned_checkpoint_path(ledger, f"lc_{current}.json")
                value = _checkpoint(path, current)
                files.append(path)
                current = value.get("previous_checkpoint_sha256")
            return files
