#!/usr/bin/env python3
"""Validate every vendored sourcepack byte and the retained-snapshot registry.

With no arguments this discovers every pack under packs/ that carries a
manifest, validates each declared byte, and cross-checks packs/snapshots.json:
every discovered pack must be registered, every registry entry must point at an
existing pack whose manifest still hashes to the recorded value. Retention is
append-only, so any mismatch means a retained snapshot was rewritten — that is
always an error, never a warning.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "packs/snapshots.json"
ISOLATED_REGISTRY_PATH = REPO_ROOT / "packs/isolated.json"
ALLOWED_LICENSES = {"CC0-1.0"}


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def discover_packs() -> list[Path]:
    isolated = isolated_pack_paths()
    return sorted(
        path.parent
        for path in (REPO_ROOT / "packs").glob("*/manifest.json")
        if path.parent.relative_to(REPO_ROOT).as_posix() not in isolated
    )


def isolated_pack_paths() -> set[str]:
    if not ISOLATED_REGISTRY_PATH.is_file():
        return set()
    registry = json.loads(ISOLATED_REGISTRY_PATH.read_text(encoding="utf-8"))
    return {str(entry["pack"]) for entry in registry.get("snapshots", [])}


def validate_pack(pack_dir: Path) -> dict[str, Any]:
    manifest_path = pack_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("license") not in ALLOWED_LICENSES:
        raise ValueError(
            f"{manifest_path}: license {manifest.get('license')!r} "
            f"not in {sorted(ALLOWED_LICENSES)}"
        )
    for field in ("source_id", "upstream_ref", "retrieved_at_utc", "url"):
        if not manifest.get(field):
            raise ValueError(f"{manifest_path}: missing {field}")
    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"{manifest_path}: files must be a non-empty list")
    for entry in entries:
        path = pack_dir / entry["name"]
        actual = _sha256(path.read_bytes())
        if actual != entry["sha256"]:
            raise ValueError(f"{path}: sha256 mismatch; expected {entry['sha256']}, got {actual}")
    return manifest


def validate_registry(packs: list[Path]) -> None:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    entries = registry.get("snapshots")
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"{REGISTRY_PATH}: snapshots must be a non-empty list")

    by_pack: dict[str, dict[str, Any]] = {}
    for entry in entries:
        pack = str(entry["pack"])
        if pack in by_pack:
            raise ValueError(f"{REGISTRY_PATH}: duplicate registry entry for {pack}")
        by_pack[pack] = entry
        pack_dir = REPO_ROOT / pack
        manifest_path = pack_dir / "manifest.json"
        if not manifest_path.is_file():
            raise ValueError(f"{REGISTRY_PATH}: {pack} is registered but missing on disk")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        actual_sha = _sha256(manifest_path.read_bytes())
        if actual_sha != entry["manifest_sha256"]:
            raise ValueError(
                f"{pack}: manifest sha256 {actual_sha} does not match the registered "
                f"{entry['manifest_sha256']}; retained snapshots are immutable"
            )
        for field in ("source_id", "upstream_ref", "retrieved_at_utc"):
            if str(manifest[field]) != str(entry[field]):
                raise ValueError(f"{pack}: registry {field} disagrees with the manifest")
        if manifest.get("upstream_committed_at_utc") != entry["upstream_committed_at_utc"]:
            raise ValueError(f"{pack}: registry upstream_committed_at_utc disagrees")

    unregistered = [
        pack.relative_to(REPO_ROOT).as_posix()
        for pack in packs
        if pack.relative_to(REPO_ROOT).as_posix() not in by_pack
    ]
    if unregistered:
        raise ValueError(f"packs missing from {REGISTRY_PATH}: {unregistered}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "packs",
        nargs="*",
        type=Path,
        help="specific pack directories (default: discover all and check the registry)",
    )
    args = parser.parse_args()
    if args.packs:
        for pack_dir in args.packs:
            validate_pack(pack_dir)
            print(f"provenance: OK ({pack_dir})")
        return
    packs = discover_packs()
    for pack_dir in packs:
        validate_pack(pack_dir)
        print(f"provenance: OK ({pack_dir.relative_to(REPO_ROOT).as_posix()})")
    validate_registry(packs)
    print(f"registry: OK ({len(packs)} retained snapshots)")


if __name__ == "__main__":
    main()
