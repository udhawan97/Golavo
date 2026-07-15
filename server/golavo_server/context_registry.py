"""Read-only access to the validated, bundled display-context registry."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

from golavo_core import resources

MANIFEST_PATH = Path(resources.context_manifest_path())
VENUES_PATH = Path(resources.context_venue_entities_path())
ASSIGNMENTS_PATH = Path(resources.context_venue_assignments_path())

_CACHE: dict[str, Any] | None = None


def reset_cache() -> None:
    global _CACHE
    _CACHE = None


def _load() -> dict[str, Any]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    expected = {str(item["path"]): item for item in manifest["files"]}
    for path in (VENUES_PATH, ASSIGNMENTS_PATH):
        relative = path.relative_to(resources.resource_root()).as_posix()
        entry = expected.get(relative)
        if entry is None:
            raise OSError(f"context manifest omits {relative}")
        payload = path.read_bytes()
        if len(payload) != int(entry["bytes"]):
            raise OSError(f"context byte count mismatch for {relative}")
        if hashlib.sha256(payload).hexdigest() != entry["sha256"]:
            raise OSError(f"context hash mismatch for {relative}")
        lowered = payload.lower()
        if b"openligadb" in lowered or b"overlays/openligadb" in lowered:
            raise OSError(f"forbidden ODbL identity in {relative}")
    venues_payload = json.loads(VENUES_PATH.read_text(encoding="utf-8"))
    assignments_payload = json.loads(ASSIGNMENTS_PATH.read_text(encoding="utf-8"))
    venues = {str(item["entity_id"]): item for item in venues_payload["entities"]}
    if len(venues) != len(venues_payload["entities"]):
        raise OSError("duplicate venue entity id")
    _CACHE = {
        "manifest": manifest,
        "venues": venues,
        "assignments": assignments_payload["assignments"],
    }
    return _CACHE


def _value(row: Any, key: str) -> Any:
    try:
        value = row.get(key)
    except AttributeError:
        value = row[key] if key in row else None
    try:
        import pandas as pd

        return None if pd.isna(value) else value
    except (ImportError, TypeError, ValueError):
        return value


def _claim_map(entity: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item["field"]): item for item in entity.get("claims", [])}


def venue_for_match(row: Any) -> dict[str, Any]:
    try:
        payload = _load()
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return {
            "status": "unknown",
            "reason": "context-pack-unavailable",
            "entity_id": None,
            "name": None,
            "latitude": None,
            "longitude": None,
            "capacity": None,
            "identity_link_status": "unknown",
            "identity_conflict_reason": None,
            "provenance": {},
        }
    city = _value(row, "city")
    country = _value(row, "country")
    competition = _value(row, "competition")
    source_id = _value(row, "venue_source_id") or _value(row, "source_id")
    raw_date = _value(row, "date")
    try:
        match_date = (
            raw_date.date()
            if hasattr(raw_date, "date")
            else date.fromisoformat(str(raw_date)[:10])
        )
    except (TypeError, ValueError):
        match_date = None
    candidates = []
    for assignment in payload["assignments"]:
        if (
            str(city) != assignment["match_city"]
            or str(country) != assignment["match_country"]
            or str(competition) != assignment["competition"]
            or str(source_id) not in assignment["allowed_match_venue_source_ids"]
            or match_date is None
            or not date.fromisoformat(assignment["valid_from"])
            <= match_date
            <= date.fromisoformat(assignment["valid_to"])
        ):
            continue
        candidates.append(assignment)
    entity_ids = {item["venue_entity_id"] for item in candidates}
    if not candidates:
        return {
            "status": "unknown",
            "reason": "no-reviewed-stadium-assignment",
            "entity_id": None,
            "name": None,
            "latitude": None,
            "longitude": None,
            "capacity": None,
            "identity_link_status": "unknown",
            "identity_conflict_reason": None,
            "provenance": {},
        }
    if len(entity_ids) != 1:
        return {
            "status": "conflict",
            "reason": "multiple-reviewed-stadium-assignments",
            "entity_id": None,
            "name": None,
            "latitude": None,
            "longitude": None,
            "capacity": None,
            "identity_link_status": "conflicting",
            "identity_conflict_reason": "Multiple scoped venue assignments disagree.",
            "provenance": {},
        }
    assignment = candidates[0]
    entity = payload["venues"].get(next(iter(entity_ids)))
    if entity is None:
        raise OSError("venue assignment refers to a missing entity")
    claims = _claim_map(entity)

    def claim_value(field: str) -> Any:
        claim = claims.get(field)
        return claim.get("value") if claim else None

    return {
        "status": "available",
        "reason": None,
        "entity_id": entity["entity_id"],
        "name": claim_value("canonical_label"),
        "latitude": claim_value("latitude"),
        "longitude": claim_value("longitude"),
        "capacity": claim_value("capacity"),
        "identity_link_status": assignment["wikidata_link_status"],
        "identity_conflict_reason": assignment.get("conflict_reason"),
        "provenance": {
            field: {
                "claim_id": claim["claim_id"],
                "source_refs": claim["source_refs"],
            }
            for field, claim in claims.items()
            if field in {"canonical_label", "latitude", "longitude", "capacity"}
        },
    }


def source_catalog() -> list[dict[str, Any]]:
    try:
        return list(_load()["manifest"]["sources"])
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return []


def capabilities(index_fingerprint: str) -> dict[str, Any]:
    try:
        manifest = _load()["manifest"]
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        return {
            "schema_version": "0.1.0",
            "status": "unavailable",
            "display_only": True,
            "model_input": False,
            "context_pack_version": None,
            "context_pack_sha256": None,
            "index_fingerprint": index_fingerprint,
            "features": {},
            "reason_codes": [f"context-pack-invalid:{type(exc).__name__}"],
        }
    manifest_sha = hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()
    return {
        "schema_version": "0.1.0",
        "status": "partial",
        "display_only": True,
        "model_input": False,
        "context_pack_version": manifest["context_pack_version"],
        "context_pack_sha256": manifest_sha,
        "index_fingerprint": index_fingerprint,
        "features": {
            "place": "partial",
            "venue": "partial",
            "local_kickoff": "partial",
            "kickoff_gap": "partial",
            "travel": "partial",
            "map": "available",
            "weather": "blocked",
        },
        "reason_codes": [
            "place-resolution-is-reviewed-subset",
            "venue-coverage-is-world-cup-2026-only",
            "schedule-coverage-is-index-only",
        ],
    }
