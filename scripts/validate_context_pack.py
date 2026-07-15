#!/usr/bin/env python3
"""Validate the bundled display-only context pack and identity boundaries."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]

CONTEXT_ONLY_SOURCE_IDS = {
    "geonames",
    "natural-earth",
    "wikidata",
}
MODEL_AND_ARTIFACT_SINKS = (
    "core/golavo_core/analysis.py",
    "core/golavo_core/analytics.py",
    "core/golavo_core/artifacts.py",
    "core/golavo_core/calibration.py",
    "core/golavo_core/evaluation.py",
    "core/golavo_core/models",
    "core/golavo_core/outlook.py",
    "core/golavo_core/score_matrix.py",
    "core/golavo_core/season_outlook.py",
    "server/golavo_server/analysis.py",
    "server/golavo_server/analytics.py",
    "server/golavo_server/outlook.py",
    "server/golavo_server/seal.py",
    "server/golavo_server/settlement.py",
)
FORBIDDEN_RUNTIME_MARKERS = (
    "golavo_server.context_registry",
    "golavo_server.conditions",
    "context_manifest_path",
    "context_venue_entities_path",
    "context_venue_assignments_path",
    "geonames_places_path",
    "natural_earth_world_path",
    "data/context/",
    "data/enrichment/",
)


def _read(relative: str) -> Any:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def _validate(schema_path: str, value: Any) -> None:
    schema = _read(schema_path)
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        first = errors[0]
        raise ValueError(f"{schema_path}: {list(first.absolute_path)}: {first.message}")


def _source_ids(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "source_id" and isinstance(item, str):
                found.add(item)
            elif key == "source_ids" and isinstance(item, list):
                found.update(str(source_id) for source_id in item)
            found.update(_source_ids(item))
    elif isinstance(value, list):
        for item in value:
            found.update(_source_ids(item))
    return found


def validate_display_boundary(root: Path = ROOT) -> None:
    """Prove display context cannot become a model, artifact, or index input."""
    for relative in MODEL_AND_ARTIFACT_SINKS:
        target = root / relative
        paths = target.rglob("*.py") if target.is_dir() else [target]
        for path in paths:
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8").casefold()
            marker = next((item for item in FORBIDDEN_RUNTIME_MARKERS if item in text), None)
            if marker:
                raise ValueError(
                    f"{path.relative_to(root)} imports display context into a model/artifact sink: "
                    f"{marker}"
                )

    for folder_relative in ("data/fixtures/sample_artifacts", "packs/core-cc0"):
        folder = root / folder_relative
        if not folder.is_dir():
            continue
        for path in folder.rglob("*.json"):
            overlap = _source_ids(json.loads(path.read_text(encoding="utf-8"))) & (
                CONTEXT_ONLY_SOURCE_IDS
            )
            if overlap:
                raise ValueError(
                    f"{path.relative_to(root)} contains display-only context sources: "
                    f"{sorted(overlap)}"
                )

    meta_path = root / "data/index/matches_index.meta.json"
    if meta_path.is_file():
        built_from = _read_from(root, "data/index/matches_index.meta.json").get(
            "built_from", []
        )
        overlap = {
            str(item.get("source_id"))
            for item in built_from
            if item.get("source_id") in CONTEXT_ONLY_SOURCE_IDS
        }
        if overlap:
            raise ValueError(
                f"match index metadata contains display-only context sources: {sorted(overlap)}"
            )

    index_path = root / "data/index/matches_index.parquet"
    if index_path.is_file():
        try:
            import pyarrow.parquet as parquet
        except ImportError as exc:  # pragma: no cover - validation env ships pyarrow
            raise ValueError("pyarrow is required to inspect context provenance") from exc
        parquet_file = parquet.ParquetFile(index_path)
        columns = [
            name
            for name in parquet_file.schema_arrow.names
            if name == "source_id" or name.endswith("_source_id")
        ]
        table = parquet_file.read(columns=columns)
        for name in columns:
            values = {str(item) for item in table.column(name).to_pylist() if item is not None}
            overlap = values & CONTEXT_ONLY_SOURCE_IDS
            if overlap:
                raise ValueError(
                    f"match index parquet contains display-only context in {name}: "
                    f"{sorted(overlap)}"
                )


def _read_from(root: Path, relative: str) -> Any:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def validate() -> dict[str, int]:
    manifest = _read("data/context/manifest.json")
    places = _read("data/enrichment/places.json")
    place_meta = _read("data/enrichment/places.meta.json")
    resolutions = _read("data/context/place_resolutions.json")
    reviews = _read("data/context/place_alias_reviews.json")
    venue_registry = _read("data/context/venue_entities.json")
    assignments = _read("data/context/venue_assignments.json")

    _validate("docs/contracts/context_pack.schema.json", manifest)
    _validate("docs/contracts/context_resolution.schema.json", resolutions)
    _validate("docs/contracts/context_resolution.schema.json", reviews)
    _validate("docs/contracts/context_entity_registry.schema.json", venue_registry)

    for file in manifest["files"]:
        payload = (ROOT / file["path"]).read_bytes()
        if len(payload) != file["bytes"]:
            raise ValueError(f"{file['path']}: byte count disagrees with context manifest")
        if hashlib.sha256(payload).hexdigest() != file["sha256"]:
            raise ValueError(f"{file['path']}: sha256 disagrees with context manifest")
        lowered = payload.lower()
        if b"openligadb" in lowered or b"overlays/openligadb" in lowered:
            raise ValueError(f"{file['path']}: forbidden ODbL identity/path")

    place_ids = [str(value.get("entity_id", "")) for value in places.values()]
    if any(not value.startswith("place_") for value in place_ids):
        raise ValueError("every resolved place must carry a stable place_ entity id")
    if any(value.get("source_id") != "geonames" for value in places.values()):
        raise ValueError("resolved place facts must remain GeoNames-sourced")
    if place_meta.get("ambiguous_pairs", 0) <= 0 or place_meta.get("alias_pending_pairs", 0) <= 0:
        raise ValueError("context metadata must disclose fail-closed ambiguity and alias queues")
    if "population" in str(place_meta.get("matching", "")).casefold():
        raise ValueError("population must not remain an identity tiebreak")

    entities = {item["entity_id"]: item for item in venue_registry["entities"]}
    if len(entities) != len(venue_registry["entities"]):
        raise ValueError("duplicate context entity id")
    for assignment in assignments["assignments"]:
        entity = entities.get(assignment["venue_entity_id"])
        if entity is None:
            raise ValueError("venue assignment refers to an unknown entity")
        qids = [item for item in entity["identifiers"] if item["source_id"] == "wikidata"]
        if assignment["wikidata_link_status"] == "accepted" and len(qids) != 1:
            raise ValueError("accepted Wikidata venue link must carry exactly one QID")
        if assignment["wikidata_link_status"] == "conflicting" and qids:
            raise ValueError("conflicting Wikidata venue link must fail closed")

    source_ids = {source["source_id"] for source in manifest["sources"]}
    expected_sources = {"geonames", "natural-earth", "openfootball-worldcup-json", "wikidata"}
    if source_ids != expected_sources:
        raise ValueError(f"context sources differ: expected {sorted(expected_sources)}")
    if manifest["display_only"] is not True or manifest["model_input"] is not False:
        raise ValueError("context pack crossed the display-only boundary")

    validate_display_boundary()

    return {
        "places": len(set(place_ids)),
        "venues": len(entities),
        "unresolved": len(resolutions["resolutions"]),
    }


def main() -> None:
    counts = validate()
    print(
        f"context pack: OK ({counts['places']} places; {counts['venues']} venues; "
        f"{counts['unresolved']} unresolved reviews)"
    )


if __name__ == "__main__":
    main()
