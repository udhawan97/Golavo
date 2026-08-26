"""Append-only local application receipts for refresh generation changes."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from golavo_server import runtime

SCHEMA_VERSION = "0.1.0"
_LOCK = threading.RLock()
_STABLE_IDENTITY_SOURCES = {"openfootball-worldcup-json"}
_CERTIFICATE_FIELDS = (
    "expected_teams",
    "observed_teams",
    "expected_matches",
    "observed_matches",
    "unique_ordered_pairs",
    "duplicate_ordered_pairs",
    "self_fixtures",
    "incomplete_fixtures",
    "past_result_gaps",
    "future_completed_results",
    "complete_fixture_list",
)


def _path() -> Path:
    root = runtime.refresh_dir()
    if root is None:
        raise RuntimeError("refresh receipts require a writable data directory")
    return root / "receipts.jsonl"


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _fsync_dir(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_append(path: Path, line: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_bytes() if path.exists() else b""
    if existing and not existing.endswith(b"\n"):
        raise ValueError("refresh receipt history has a truncated final line")
    descriptor, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=".receipts.")
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(existing)
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _fsync_dir(path.parent)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _index_hash(manifest: dict[str, Any]) -> str | None:
    for entry in manifest.get("artifacts", []):
        if isinstance(entry, dict) and entry.get("path") == "index/matches_index.parquet":
            digest = entry.get("sha256")
            return str(digest) if isinstance(digest, str) else None
    return None


def _manifest_for(generation_id: str | None) -> dict[str, Any] | None:
    if not generation_id:
        return None
    try:
        from golavo_server import refresh_state

        return refresh_state.verify_generation(refresh_state.generation_dir(generation_id))
    except (OSError, RuntimeError, ValueError, KeyError, json.JSONDecodeError):
        return None


def _source_summaries(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for value in manifest.get("source_snapshots", []):
        if not isinstance(value, dict):
            continue
        summaries.append(
            {
                "source_id": value.get("source_id"),
                "upstream_ref": value.get("upstream_ref"),
                "license": value.get("license"),
                "file_count": len(value.get("files", []))
                if isinstance(value.get("files"), list)
                else None,
            }
        )
    return sorted(summaries, key=lambda item: str(item.get("source_id")))


def _capability_summaries(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for value in manifest.get("capabilities", []):
        if not isinstance(value, dict):
            continue
        certificate = value.get("certificate")
        summaries.append(
            {
                "source_id": value.get("source_id"),
                "competition": value.get("competition"),
                "season": value.get("season"),
                "capability": value.get("capability"),
                "last_known_good": bool(value.get("last_known_good", False)),
                "schedule_certificate": (
                    {key: certificate.get(key) for key in _CERTIFICATE_FIELDS}
                    if isinstance(certificate, dict)
                    else None
                ),
            }
        )
    return sorted(
        summaries,
        key=lambda item: (str(item.get("source_id")), str(item.get("competition"))),
    )


def _stable_index(generation_id: str) -> tuple[dict[tuple[str, str], dict[str, Any]], int]:
    from golavo_server import refresh_state

    manifest = refresh_state.verify_generation(refresh_state.generation_dir(generation_id))
    path = refresh_state.generation_dir(generation_id) / "index" / "matches_index.parquet"
    import pandas as pd

    frame = pd.read_parquet(path)
    source_column = "identity_source_id" if "identity_source_id" in frame.columns else "source_id"
    if "upstream_fixture_key" not in frame.columns or source_column not in frame.columns:
        return {}, int(len(frame))
    candidates = frame.loc[
        frame[source_column].astype("string").isin(_STABLE_IDENTITY_SOURCES)
        & frame["upstream_fixture_key"].notna()
    ]
    counts = candidates.groupby([source_column, "upstream_fixture_key"], dropna=False).size()
    unique = counts[counts.eq(1)].index
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    for source_id, fixture_key in unique:
        selected = candidates.loc[
            candidates[source_column].astype("string").eq(str(source_id))
            & candidates["upstream_fixture_key"].astype("string").eq(str(fixture_key))
        ].iloc[0]
        rows[(str(source_id), str(fixture_key))] = {
            "match_id": str(selected.get("match_id") or ""),
            "is_complete": bool(selected.get("is_complete")),
        }
    # The verified manifest read above is intentional: comparison never reads an
    # index whose generation receipts failed verification.
    assert manifest.get("generation_id") == generation_id
    return rows, int(len(frame) - len(rows))


def _safe_change_summary(
    previous_generation_id: str | None, active_generation_id: str
) -> dict[str, Any]:
    if previous_generation_id is None:
        return {
            "status": "baseline_unavailable",
            "stable_identity_counts": None,
            "reason": "no prior generation exists for a rekey-safe comparison",
        }
    try:
        previous, unresolved_previous = _stable_index(previous_generation_id)
        active, unresolved_active = _stable_index(active_generation_id)
    except (OSError, RuntimeError, ValueError, KeyError, ImportError):
        return {
            "status": "comparison_unavailable",
            "stable_identity_counts": None,
            "reason": "one verified generation index was unavailable",
        }
    previous_keys = set(previous)
    active_keys = set(active)
    shared = previous_keys & active_keys
    return {
        "status": "partial_stable_identity",
        "stable_identity_sources": sorted(_STABLE_IDENTITY_SOURCES),
        "stable_identity_counts": {
            "added": len(active_keys - previous_keys),
            "removed": len(previous_keys - active_keys),
            "new_results": sum(
                1
                for key in shared
                if not previous[key]["is_complete"] and active[key]["is_complete"]
            ),
            "rekeyed": sum(
                1 for key in shared if previous[key]["match_id"] != active[key]["match_id"]
            ),
        },
        "unresolved_previous_rows": unresolved_previous,
        "unresolved_active_rows": unresolved_active,
        "reason": (
            "counts cover only source-owned identities proven stable and unique in both indexes; "
            "unresolved rows are not labeled added or removed"
        ),
    }


def append(
    *,
    operation: str,
    previous_generation_id: str | None,
    active_generation_id: str,
    manifest: dict[str, Any],
    occurred_at_utc: str | None = None,
) -> dict[str, Any]:
    if operation not in {"refresh_activation", "rollback"}:
        raise ValueError("unsupported refresh receipt operation")
    occurred = occurred_at_utc or datetime.now(UTC).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
    previous_manifest = _manifest_for(previous_generation_id)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "operation": operation,
        "outcome": "activated" if operation == "refresh_activation" else "rolled_back",
        "occurred_at_utc": occurred,
        "previous_generation_id": previous_generation_id,
        "active_generation_id": active_generation_id,
        "previous_index_sha256": _index_hash(previous_manifest or {}),
        "active_index_sha256": _index_hash(manifest),
        "source_summaries": _source_summaries(manifest),
        "capability_summaries": _capability_summaries(manifest),
        "change_summary": _safe_change_summary(previous_generation_id, active_generation_id),
        "limitations": [
            "This is an append-only local application history, not a tamper-proof audit log.",
            "Change counts cover only stable unique source identities; unresolved rows are "
            "reported separately and never guessed through an upstream rekey.",
        ],
    }
    payload["receipt_id"] = "rr_" + hashlib.sha256(_canonical(payload)).hexdigest()
    path = _path()
    with _LOCK:
        _atomic_append(path, _canonical(payload) + b"\n")
    return payload


def list_receipts(*, limit: int = 20) -> dict[str, Any]:
    if limit < 1 or limit > 100:
        raise ValueError("limit must be 1..100")
    path = _path()
    if not path.exists():
        return {"schema_version": SCHEMA_VERSION, "items": []}
    items: list[dict[str, Any]] = []
    with _LOCK:
        raw = path.read_bytes()
    truncated_tail = bool(raw and not raw.endswith(b"\n"))
    lines = raw.splitlines()
    if truncated_tail:
        lines = lines[:-1]
    for line in lines:
        value = json.loads(line.decode("utf-8"))
        if not isinstance(value, dict) or not str(value.get("receipt_id", "")).startswith("rr_"):
            raise ValueError("refresh receipt history is corrupt")
        claimed = value["receipt_id"]
        body = {key: item for key, item in value.items() if key != "receipt_id"}
        if claimed != "rr_" + hashlib.sha256(_canonical(body)).hexdigest():
            raise ValueError("refresh receipt hash mismatch")
        items.append(value)
    return {
        "schema_version": SCHEMA_VERSION,
        "items": list(reversed(items[-limit:])),
        "truncated_tail": truncated_tail,
    }
