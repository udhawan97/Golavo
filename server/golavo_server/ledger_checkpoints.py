"""Hash-chained local checkpoints over immutable forecast artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from golavo_core.artifacts import load_verified_artifact

SCHEMA_VERSION = "0.1.0"
LIMITS = [
    "The chain detects changes relative to earlier local checkpoints; it does not prove "
    "external authenticity.",
    "It cannot prove that an artifact was created before a particular real-world event.",
    "A checkpoint records the artifacts present at creation time and does not prevent "
    "explicit later removal.",
    "Cross-version migration, disaster recovery, and optional external anchoring remain "
    "separate release gates.",
]
_LOCK = threading.RLock()


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _digest(value: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _root(ledger: Path) -> Path:
    return Path(ledger) / "checkpoints"


def _fsync_dir(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic(path: Path, value: dict[str, Any]) -> None:
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
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"checkpoint is unreadable: {expected}") from exc
    if not isinstance(value, dict) or value.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("checkpoint schema is invalid")
    body = {key: item for key, item in value.items() if key != "checkpoint_sha256"}
    if value.get("checkpoint_sha256") != expected or _digest(body) != expected:
        raise ValueError("checkpoint hash mismatch")
    previous = value.get("previous_checkpoint_sha256")
    if previous is not None and (
        not isinstance(previous, str)
        or len(previous) != 64
        or any(character not in "0123456789abcdef" for character in previous)
    ):
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
        if (
            not isinstance(artifact_id, str)
            or artifact_id in seen
            or not isinstance(digest, str)
            or len(digest) != 64
        ):
            raise ValueError("checkpoint artifact entry is invalid")
        seen.add(artifact_id)
    return value


def _status_unlocked(ledger: Path) -> dict[str, Any]:
    ledger = Path(ledger)
    root = _root(ledger)
    head_path = root / "head.json"
    if not head_path.exists():
        if root.exists() and any(root.glob("lc_*.json")):
            raise ValueError("checkpoint head is missing while checkpoint records remain")
        return {
            "schema_version": SCHEMA_VERSION,
            "verified": True,
            "checkpoint_count": 0,
            "head": None,
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
        or head_value.get("schema_version") != SCHEMA_VERSION
        or not isinstance(head, str)
        or len(head) != 64
    ):
        raise ValueError("checkpoint head is invalid")
    current: str | None = head
    seen: set[str] = set()
    missing: set[str] = set()
    head_artifacts: set[str] = set()
    while current:
        if current in seen:
            raise ValueError("checkpoint chain contains a cycle")
        seen.add(current)
        value = _checkpoint(_root(ledger) / f"lc_{current}.json", current)
        entries = value["artifacts"]
        if len(seen) == 1:
            head_artifacts = {str(entry["artifact_id"]) for entry in entries}
        for entry in entries:
            artifact_id = str(entry["artifact_id"])
            artifact_path = ledger / f"{artifact_id}.json"
            if not artifact_path.exists():
                missing.add(artifact_id)
            elif hashlib.sha256(artifact_path.read_bytes()).hexdigest() != entry["sha256"]:
                raise ValueError(f"checkpointed artifact changed: {artifact_id}")
        current = value.get("previous_checkpoint_sha256")
    current_artifacts = {path.stem for path in ledger.glob("fa_*.json")}
    return {
        "schema_version": SCHEMA_VERSION,
        "verified": True,
        "checkpoint_count": len(seen),
        "head": head,
        "missing_artifacts": sorted(missing),
        "uncheckpointed_artifacts": sorted(current_artifacts - head_artifacts),
        "limits": LIMITS,
    }


def create(ledger: Path) -> dict[str, Any]:
    with _LOCK:
        ledger = Path(ledger)
        # Verify every predecessor before creating any bytes. A corrupt chain is
        # immutable evidence of a problem, never a base for a new head.
        verified = _status_unlocked(ledger)
        artifacts: list[dict[str, str]] = []
        for path in sorted(ledger.glob("fa_*.json")):
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
            "artifacts": artifacts,
            "limits": LIMITS,
        }
        digest = _digest(body)
        checkpoint = {**body, "checkpoint_sha256": digest}
        checkpoint_path = _root(ledger) / f"lc_{digest}.json"
        created_checkpoint = not checkpoint_path.exists()
        _atomic(checkpoint_path, checkpoint)
        try:
            _atomic(
                _root(ledger) / "head.json",
                {"schema_version": SCHEMA_VERSION, "checkpoint_sha256": digest},
            )
        except BaseException:
            if created_checkpoint:
                checkpoint_path.unlink(missing_ok=True)
                _fsync_dir(checkpoint_path.parent)
            raise
        return checkpoint


def status(ledger: Path) -> dict[str, Any]:
    with _LOCK:
        return _status_unlocked(Path(ledger))
