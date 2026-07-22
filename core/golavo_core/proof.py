"""Portable, deterministic verification bundles for immutable forecasts."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from golavo_core.artifacts import load_verified_artifact, verify_artifact_integrity
from golavo_core.resources import forecast_proof_schema_path

PROOF_SCHEMA_VERSION = "0.1.0"


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _bundle_sha256(proof: dict[str, Any]) -> str:
    stable = copy.deepcopy(proof)
    stable.pop("bundle_sha256", None)
    return f"sha256:{hashlib.sha256(_canonical(stable)).hexdigest()}"


def _verified_ledger(ledger_dir: Path) -> dict[str, dict[str, Any]]:
    artifacts: dict[str, dict[str, Any]] = {}
    for path in Path(ledger_dir).glob("fa_*.json"):
        try:
            artifact = load_verified_artifact(path)
        except (OSError, ValueError, KeyError):
            continue
        artifacts[artifact["artifact_id"]] = artifact
    return artifacts


def _lineage(root_id: str, ledger: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    connected = {root_id}
    changed = True
    while changed:
        changed = False
        for artifact_id, artifact in ledger.items():
            parent = artifact.get("supersedes")
            if (artifact_id in connected or parent in connected) and artifact_id not in connected:
                connected.add(artifact_id)
                changed = True
            if artifact_id in connected and parent in ledger and parent not in connected:
                connected.add(parent)
                changed = True
    return sorted(
        (ledger[artifact_id] for artifact_id in connected),
        key=lambda artifact: (artifact["provenance"]["created_at_utc"], artifact["artifact_id"]),
    )


def _manifest_index(pack_root: Path | None) -> dict[str, str]:
    if pack_root is None or not Path(pack_root).is_dir():
        return {}
    found: dict[str, str] = {}
    for path in Path(pack_root).rglob("manifest.json"):
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            continue
        found.setdefault(hashlib.sha256(raw.encode()).hexdigest(), raw)
    return found


def build_forecast_proof(
    artifact_path: Path, *, ledger_dir: Path | None = None, pack_root: Path | None = None
) -> dict[str, Any]:
    """Export a self-verifying artifact lineage plus its pinned source receipts."""
    root = load_verified_artifact(Path(artifact_path))
    ledger = _verified_ledger(ledger_dir or Path(artifact_path).parent)
    ledger[root["artifact_id"]] = root
    artifacts = _lineage(root["artifact_id"], ledger)
    descriptors: dict[tuple[str, str], dict[str, Any]] = {}
    for artifact in artifacts:
        for descriptor in artifact["inputs"]["snapshots"]:
            descriptors[(str(descriptor["source_id"]), str(descriptor["sha256"]))] = descriptor
    manifests = _manifest_index(pack_root)
    sources: list[dict[str, Any]] = []
    ordered_descriptors = sorted(
        descriptors.values(), key=lambda item: (item["source_id"], item["sha256"])
    )
    for descriptor in ordered_descriptors:
        manifest_json = manifests.get(str(descriptor["sha256"]))
        sources.append(
            {
                "descriptor": descriptor,
                "manifest_json": manifest_json,
                "verification": "manifest-hash-verified" if manifest_json else "descriptor-only",
            }
        )
    proof: dict[str, Any] = {
        "schema_version": PROOF_SCHEMA_VERSION,
        "root_artifact_id": root["artifact_id"],
        "artifacts": artifacts,
        "sources": sources,
        "contracts": {
            "forecast_artifact": str(root["schema_version"]),
            "forecast_proof": PROOF_SCHEMA_VERSION,
        },
        "verification": {
            "artifact_integrity": "verified",
            "lineage": "verified",
            "source_receipts": "verified-when-embedded",
        },
    }
    proof["bundle_sha256"] = _bundle_sha256(proof)
    verify_forecast_proof(proof)
    return proof


def verify_forecast_proof(proof: dict[str, Any]) -> dict[str, Any]:
    """Verify a proof without a Golavo ledger, pack directory, or network."""
    Draft202012Validator(
        json.loads(forecast_proof_schema_path().read_text(encoding="utf-8"))
    ).validate(proof)
    expected = _bundle_sha256(proof)
    if proof.get("bundle_sha256") != expected:
        raise ValueError("portable proof hash mismatch")
    artifacts: dict[str, dict[str, Any]] = {}
    for artifact in proof["artifacts"]:
        verified = verify_artifact_integrity(artifact)
        artifact_id = str(verified["artifact_id"])
        if artifact_id in artifacts:
            raise ValueError(f"duplicate proof artifact {artifact_id}")
        artifacts[artifact_id] = verified
    root_id = str(proof["root_artifact_id"])
    if root_id not in artifacts:
        raise ValueError("proof root artifact is missing")
    connected = {root_id}
    changed = True
    while changed:
        changed = False
        for artifact_id, artifact in artifacts.items():
            parent = artifact.get("supersedes")
            if artifact_id in connected and parent in artifacts and parent not in connected:
                connected.add(parent)
                changed = True
            if parent in connected and artifact_id not in connected:
                connected.add(artifact_id)
                changed = True
    if connected != set(artifacts):
        raise ValueError("proof contains artifacts outside the root lineage")
    for source in proof["sources"]:
        manifest_json = source.get("manifest_json")
        if manifest_json is None:
            continue
        digest = hashlib.sha256(manifest_json.encode()).hexdigest()
        if digest != source["descriptor"]["sha256"]:
            raise ValueError("embedded source manifest hash mismatch")
        json.loads(manifest_json)
    return {
        "verified": True,
        "root_artifact_id": root_id,
        "artifact_count": len(artifacts),
        "source_count": len(proof["sources"]),
        "bundle_sha256": expected,
    }
