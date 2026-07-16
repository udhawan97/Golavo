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

import hashlib
import json
from pathlib import Path
from typing import Any

import jsonschema

REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "data/sources/registry.json"
SCHEMA_PATH = REPO_ROOT / "data/sources/registry.schema.json"
SNAPSHOTS_PATH = REPO_ROOT / "packs/snapshots.json"
ISOLATED_PATH = REPO_ROOT / "packs/isolated.json"
ENRICHMENT_PATH = REPO_ROOT / "packs/enrichment.json"

# Only core sources may be folded into the match index. Enrichment is bundled
# through its own registry and may join read-only at display time only.
BUNDLEABLE = frozenset({"core"})
# Classes that carry a redistribution/attribution duty.
REDISTRIBUTABLE = frozenset({"core", "enrichment", "odbl-pack", "by-sa-pack", "research-pack"})
ISOLATED_CLASSES = frozenset({"by-sa-pack", "odbl-pack", "research-pack"})


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
        correction = entry.get("corrections")
        if isinstance(correction, dict):
            expected_namespace = {
                ("core", "CC0-1.0"): "core-cc0",
                ("enrichment", "CC0-1.0"): "enrichment-cc0",
                ("enrichment", "PUBLIC-DOMAIN"): "enrichment-public-domain",
                ("enrichment", "CC-BY-4.0"): "enrichment-cc-by-4.0",
                ("by-sa-pack", "CC-BY-SA-4.0"): "research-cc-by-sa-4.0",
                ("odbl-pack", "ODbL-1.0"): "overlay-odbl-1.0",
            }.get((entry["classification"], entry["license"]))
            if correction["license_namespace"] != expected_namespace:
                raise ValueError(f"{sid}: correction namespace disagrees with source class/license")
            isolated_local = {"overlay-odbl-1.0", "research-cc-by-sa-4.0"}
            if expected_namespace in isolated_local and correction["redistributable_export"]:
                raise ValueError(f"{sid}: isolated corrections cannot be redistributable exports")
            if (
                expected_namespace not in isolated_local
                and not correction["redistributable_export"]
            ):
                raise ValueError(f"{sid}: free/open correction policy unexpectedly blocks export")
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


def validate_isolated_packs(
    by_id: dict[str, dict[str, Any]],
    *,
    isolated_path: Path = ISOLATED_PATH,
    snapshots_path: Path = SNAPSHOTS_PATH,
    repo_root: Path = REPO_ROOT,
) -> None:
    """Validate isolated pack licenses and hashes without making them bundleable."""
    isolated = _load(isolated_path)["snapshots"] if isolated_path.is_file() else []
    bundled_paths = {str(item["pack"]) for item in _load(snapshots_path)["snapshots"]}
    for snap in isolated:
        pack = str(snap["pack"])
        if pack in bundled_paths:
            raise ValueError(f"{pack}: isolated pack is also present in snapshots.json")
        source_id = str(snap["source_id"])
        entry = by_id.get(source_id)
        if entry is None:
            raise ValueError(f"{pack}: isolated source {source_id!r} is absent from registry")
        if entry["classification"] not in ISOLATED_CLASSES:
            raise ValueError(
                f"{pack}: classification {entry['classification']!r} is not isolated-pack safe"
            )
        pack_dir = repo_root / pack
        manifest_path = pack_dir / "manifest.json"
        manifest_bytes = manifest_path.read_bytes()
        if hashlib.sha256(manifest_bytes).hexdigest() != str(snap["manifest_sha256"]):
            raise ValueError(f"{pack}: manifest hash disagrees with isolated.json")
        manifest = json.loads(manifest_bytes)
        if str(manifest.get("source_id")) != source_id:
            raise ValueError(f"{pack}: manifest source_id disagrees with isolated.json")
        if str(manifest.get("license")) != str(entry["license"]):
            raise ValueError(
                f"{pack}: manifest license {manifest.get('license')!r} disagrees with "
                f"registry license {entry['license']!r}"
            )
        for item in manifest.get("files", []):
            file_path = pack_dir / str(item["name"])
            digest = hashlib.sha256(file_path.read_bytes()).hexdigest()
            if digest != str(item["sha256"]):
                raise ValueError(f"{pack}/{item['name']}: sha256 mismatch")


def validate_enrichment_packs(
    by_id: dict[str, dict[str, Any]],
    *,
    enrichment_path: Path = ENRICHMENT_PATH,
    snapshots_path: Path = SNAPSHOTS_PATH,
    isolated_path: Path = ISOLATED_PATH,
    repo_root: Path = REPO_ROOT,
) -> None:
    """Validate attributed enrichment packs as side tables, never match packs."""
    if not enrichment_path.is_file():
        return
    snapshots = _load(enrichment_path).get("snapshots", [])
    match_paths = {str(item["pack"]) for item in _load(snapshots_path)["snapshots"]}
    isolated_paths = (
        {str(item["pack"]) for item in _load(isolated_path)["snapshots"]}
        if isolated_path.is_file()
        else set()
    )
    for snap in snapshots:
        pack = str(snap["pack"])
        if pack in match_paths or pack in isolated_paths:
            raise ValueError(f"{pack}: enrichment pack crosses a registry boundary")
        source_id = str(snap["source_id"])
        entry = by_id.get(source_id)
        if entry is None or entry.get("classification") not in {"core", "enrichment"}:
            raise ValueError(
                f"{pack}: source {source_id!r} is not registered as core/enrichment"
            )
        manifest_path = repo_root / pack / "manifest.json"
        manifest_bytes = manifest_path.read_bytes()
        if hashlib.sha256(manifest_bytes).hexdigest() != str(snap["manifest_sha256"]):
            raise ValueError(f"{pack}: manifest hash disagrees with enrichment.json")
        manifest = json.loads(manifest_bytes)
        if str(manifest.get("license")) != str(entry.get("license")):
            raise ValueError(f"{pack}: enrichment manifest license disagrees with registry")
        if str(manifest.get("source_id")) != source_id:
            raise ValueError(f"{pack}: manifest source_id disagrees with enrichment.json")
        for item in manifest.get("files", []):
            file_path = repo_root / pack / str(item["name"])
            if hashlib.sha256(file_path.read_bytes()).hexdigest() != str(item["sha256"]):
                raise ValueError(f"{pack}/{item['name']}: sha256 mismatch")


def main() -> None:
    by_id = validate_registry()
    validate_bundled_packs(by_id)
    validate_isolated_packs(by_id)
    validate_enrichment_packs(by_id)
    classes = sorted({e["classification"] for e in by_id.values()})
    print(f"source registry: OK ({len(by_id)} sources; classes: {', '.join(classes)})")


if __name__ == "__main__":
    main()
