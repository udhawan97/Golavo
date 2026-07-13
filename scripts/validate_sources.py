#!/usr/bin/env python3
"""Validate data/sources/registry.json and tie it to the bundled packs.

The source registry is the single machine-readable record of every dataset
Golavo carries, plans, or rejects — its attribution, license, and license class.
This gate makes the registry load-bearing rather than decorative:

* the registry validates against its own JSON Schema;
* source_ids are unique;
* every bundled pack (packs/snapshots.json) maps to a registry entry whose
  classification is bundleable (core/enrichment) and whose license matches the
  manifest — so an ODbL/CC-BY-SA/research/rejected source can never be folded
  into the committed CC0 index without first failing here;
* redistributable classes carry an attribution string.

Network-free and deterministic, so it runs in CI beside validate_provenance.py.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "data/sources/registry.json"
SCHEMA_PATH = REPO_ROOT / "data/sources/registry.schema.json"
SNAPSHOTS_PATH = REPO_ROOT / "packs/snapshots.json"

# Classes that may be folded into the bundled, redistributed index.
BUNDLEABLE = frozenset({"core", "enrichment"})
# Classes that carry a redistribution/attribution duty.
REDISTRIBUTABLE = frozenset({"core", "enrichment", "odbl-pack", "by-sa-pack", "research-pack"})


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_registry() -> dict[str, dict[str, Any]]:
    """Schema-validate the registry and return {source_id: entry}, uniqueness enforced."""
    registry = _load(REGISTRY_PATH)
    schema = _load(SCHEMA_PATH)
    jsonschema.validate(registry, schema)

    by_id: dict[str, dict[str, Any]] = {}
    for entry in registry["sources"]:
        sid = str(entry["source_id"])
        if sid in by_id:
            raise ValueError(f"{REGISTRY_PATH}: duplicate source_id {sid!r}")
        if entry["classification"] in REDISTRIBUTABLE and not entry.get("attribution"):
            raise ValueError(
                f"{sid}: classification {entry['classification']!r} requires an attribution string"
            )
        by_id[sid] = entry
    return by_id


def validate_bundled_packs(by_id: dict[str, dict[str, Any]]) -> None:
    """Every bundled pack's source must be a bundleable, license-matching registry entry."""
    snapshots = _load(SNAPSHOTS_PATH)["snapshots"]
    for snap in snapshots:
        pack = str(snap["pack"])
        source_id = str(snap["source_id"])
        entry = by_id.get(source_id)
        if entry is None:
            raise ValueError(
                f"{pack}: source_id {source_id!r} is bundled but absent from the source registry"
            )
        if entry["classification"] not in BUNDLEABLE:
            raise ValueError(
                f"{pack}: source {source_id!r} is classified {entry['classification']!r}, "
                f"which must never be folded into the bundled index "
                f"(bundleable: {sorted(BUNDLEABLE)})"
            )
        manifest = _load(REPO_ROOT / pack / "manifest.json")
        if str(manifest.get("license")) != str(entry["license"]):
            raise ValueError(
                f"{pack}: manifest license {manifest.get('license')!r} disagrees with "
                f"registry license {entry['license']!r} for {source_id!r}"
            )
        # A pack may draw fixtures/kickoffs from a co-source (e.g. worldcup.json); it is
        # bundled just as much as the primary, so it too must be a registered, bundleable,
        # license-matching source.
        for co in manifest.get("co_sources", []):
            co_id = str(co.get("source_id"))
            co_entry = by_id.get(co_id)
            if co_entry is None:
                raise ValueError(
                    f"{pack}: co-source {co_id!r} is bundled but absent from the source registry"
                )
            if co_entry["classification"] not in BUNDLEABLE:
                raise ValueError(
                    f"{pack}: co-source {co_id!r} is classified {co_entry['classification']!r}, "
                    f"which must never be bundled (bundleable: {sorted(BUNDLEABLE)})"
                )
            if str(co.get("license")) != str(co_entry["license"]):
                raise ValueError(
                    f"{pack}: co-source {co_id!r} license {co.get('license')!r} disagrees with "
                    f"registry license {co_entry['license']!r}"
                )


def main() -> None:
    by_id = validate_registry()
    validate_bundled_packs(by_id)
    classes = sorted({e["classification"] for e in by_id.values()})
    print(f"source registry: OK ({len(by_id)} sources; classes: {', '.join(classes)})")


if __name__ == "__main__":
    main()
