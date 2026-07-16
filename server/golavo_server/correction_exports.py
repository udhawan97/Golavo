"""Deterministic, license-gated correction exports with no raw evidence."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from golavo_server import correction_policy, correction_store


def _canonical_bytes(value: dict[str, Any]) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    ).encode("utf-8")


def _safe_excerpt(value: str) -> str:
    return value if len(value) <= 240 else value[:237] + "..."


def _export_matches_head(record: dict[str, Any], proposal: dict[str, Any]) -> bool:
    if record["proposal_head_event_id"] == proposal["head_event_id"]:
        return True
    history = proposal.get("events") or []
    if not history:
        return False
    latest = history[-1]
    previous_hash = latest.get("previous_event_hash")
    return bool(
        latest.get("event_type") == "exported"
        and latest.get("payload", {}).get("export_id") == record["export_id"]
        and previous_hash
        and record["proposal_head_event_id"] == f"ce_{previous_hash}"
    )


def _write_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    if path.exists():
        if path.is_symlink() or not path.is_file():
            raise correction_store.CorrectionStoreError(
                "export_path_unsafe", "an existing export is not a safe regular file", 503
            )
        if path.read_bytes() != payload:
            raise correction_store.CorrectionStoreError(
                "export_hash_collision", "an existing export has different bytes", 503
            )
        return
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".export-", delete=False) as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    try:
        os.chmod(temporary, 0o600)
    except OSError:
        pass
    os.replace(temporary, path)


def export_proposal(
    root: Path, proposal_id: str, *, expected_head_event_id: str | None = None
) -> dict[str, Any]:
    proposal = correction_store.get_proposal(root, proposal_id, include_events=True)
    if (
        expected_head_event_id is not None
        and proposal["head_event_id"] != expected_head_event_id
    ):
        raise correction_store.CorrectionStoreError(
            "proposal_changed", "proposal changed after export review"
        )
    if proposal["state"] not in {"validated_candidate", "accepted_local", "exported", "submitted"}:
        raise correction_store.CorrectionStoreError(
            "proposal_not_exportable", "only a conflict-free validated proposal can be exported"
        )
    if not correction_policy.can_export(proposal.get("source_id")):
        reason = (
            "OpenLigaDB proposals remain in the isolated ODbL namespace and cannot be exported"
            if proposal["license_namespace"] == "overlay-odbl-1.0"
            else "this source is not approved for redistributable correction exports"
        )
        raise correction_store.CorrectionStoreError("license_blocks_export", reason, 422)
    previous = correction_store.latest_export(root, proposal_id)
    if (
        previous is not None
        and proposal["state"] in {"exported", "submitted"}
        and _export_matches_head(previous, proposal)
    ):
        path = Path(root) / str(previous["relative_path"])
        if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == previous["sha256"]:
            return previous
    source = correction_policy.public_source(str(proposal["source_id"]))
    head = str(proposal["head_event_id"])
    body_without_id = {
        "schema_version": "0.1.0",
        "proposal_id": proposal_id,
        "proposal_head_event_id": head,
        "license_namespace": proposal["license_namespace"],
        "correction_type": proposal["correction_type"],
        "target": proposal["target"],
        "original": proposal["original"],
        "proposed": proposal["proposed"],
        "source": source,
        "evidence": [
            {
                "evidence_id": item["evidence_id"],
                "source_url": item["source_url"],
                "source_revision": item["source_revision"],
                "raw_sha256": item["raw_sha256"],
                "sanitized_excerpt": _safe_excerpt(item["sanitized_text"]),
                "snapshot_verified": item["snapshot_verified"],
            }
            for item in proposal["evidence"]
            if not item["redacted"]
        ],
        "history": [
            {
                "event_id": item["event_id"],
                "sequence": item["sequence"],
                "event_type": item["event_type"],
                "event_sha256": item["event_sha256"],
            }
            for item in proposal["events"]
        ],
        "disclosures": {
            "untrusted_candidate": True,
            "authoritative_override": False,
            "model_input": False,
            "settlement_input": False,
            "raw_evidence_included": False,
            "modifications_disclosed": True,
        },
    }
    export_id = "cx_" + hashlib.sha256(_canonical_bytes(body_without_id)).hexdigest()
    body = {"export_id": export_id, **body_without_id}
    payload = _canonical_bytes(body)
    digest = hashlib.sha256(payload).hexdigest()
    relative = (
        Path("exports") / proposal["license_namespace"] / f"{export_id}.golavo-correction.json"
    )
    _write_atomic(Path(root) / relative, payload)
    return correction_store.record_export(
        root,
        proposal_id,
        source_head_event_id=head,
        export_id=export_id,
        relative_path=relative.as_posix(),
        sha256=digest,
        byte_count=len(payload),
    )
