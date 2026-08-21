#!/usr/bin/env python3
"""Build and validate the compact, display-only runtime context manifest."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
CONTEXT_VERSION = "2026.08.21.1"
CREATED_AT = "2026-07-15T18:00:00Z"
RUNTIME_PATHS = (
    "data/enrichment/places.json",
    "data/enrichment/places.meta.json",
    "data/enrichment/world_110m.geojson",
    "data/context/venue_entities.json",
    "data/context/venue_assignments.json",
)
# Every source that may appear in the runtime context. Attribution is emitted per
# PACK rather than per source id: two packs now carry Wikidata entities (the World
# Cup stadiums and the club grounds), each pinned to its own entity revisions, and
# keying by source id silently dropped whichever one lost the collision.
SOURCE_IDS = frozenset(
    {
        "geonames",
        "natural-earth",
        "openfootball-worldcup-json",
        "openfootball-clubs",
        "wikidata",
    }
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read(path: str | Path) -> Any:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def main() -> None:
    source_registry = {
        item["source_id"]: item
        for item in _read("data/sources/registry.json")["sources"]
    }
    enrichments = sorted(
        _read("packs/enrichment.json")["snapshots"], key=lambda item: item["pack"]
    )
    sources = []
    for snapshot in enrichments:
        source_id = str(snapshot["source_id"])
        if source_id not in SOURCE_IDS:
            raise ValueError(f"{snapshot['pack']}: {source_id} is not a declared context source")
        source = source_registry[source_id]
        sources.append(
            {
                "source_id": source_id,
                "upstream_ref": snapshot["upstream_ref"],
                "retrieved_at_utc": snapshot["retrieved_at_utc"],
                "manifest_sha256": snapshot["manifest_sha256"],
                "license": source["license"],
                "attribution": source["attribution"],
            }
        )
    files = []
    runtime_bytes = 0
    for relative in RUNTIME_PATHS:
        data = (ROOT / relative).read_bytes()
        if b"openligadb" in data.lower() or b"overlays/openligadb" in data.lower():
            raise ValueError(f"{relative}: forbidden ODbL identity/path in context runtime data")
        files.append({"path": relative, "sha256": _sha(data), "bytes": len(data)})
        runtime_bytes += len(data)
    places = _read("data/enrichment/places.json")
    venues = _read("data/context/venue_entities.json")["entities"]
    wikidata_count = sum(
        1
        for venue in venues
        if any(identifier["source_id"] == "wikidata" for identifier in venue["identifiers"])
    )
    manifest = {
        "schema_version": "0.1.0",
        "context_pack_version": CONTEXT_VERSION,
        "created_at_utc": CREATED_AT,
        "display_only": True,
        "model_input": False,
        "sources": sources,
        "files": files,
        "limits": {
            "runtime_bytes": runtime_bytes,
            "entity_count": len({item["entity_id"] for item in places.values()}) + len(venues),
            "wikidata_entity_count": wikidata_count,
        },
    }
    schema = _read("docs/contracts/context_pack.schema.json")
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(manifest)
    output = ROOT / "data/context/manifest.json"
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"context manifest: {manifest['limits']['entity_count']} entities, "
        f"{runtime_bytes} runtime bytes"
    )


if __name__ == "__main__":
    main()
