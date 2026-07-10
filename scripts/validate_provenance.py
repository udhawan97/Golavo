#!/usr/bin/env python3
"""Validate every byte declared by a Golavo sourcepack manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

REQUIRED_FILES = {
    "results.csv",
    "goalscorers.csv",
    "shootouts.csv",
    "former_names.csv",
    "CC0-1.0.txt",
}


def validate_pack(pack_dir: Path) -> None:
    manifest_path = pack_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("license") != "CC0-1.0":
        raise ValueError(f"{manifest_path}: expected CC0-1.0 license")
    if manifest.get("source_id") != "martj42-international-results":
        raise ValueError(f"{manifest_path}: unexpected source_id")

    entries = manifest.get("files")
    if not isinstance(entries, list):
        raise ValueError(f"{manifest_path}: files must be a list")
    declared = {entry.get("name") for entry in entries}
    if declared != REQUIRED_FILES:
        raise ValueError(f"{manifest_path}: files mismatch: {sorted(declared)}")

    for entry in entries:
        name = entry["name"]
        path = pack_dir / name
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != entry["sha256"]:
            raise ValueError(f"{path}: sha256 mismatch; expected {entry['sha256']}, got {actual}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "packs",
        nargs="*",
        type=Path,
        default=[Path("packs/martj42-internationals")],
    )
    args = parser.parse_args()
    for pack_dir in args.packs:
        validate_pack(pack_dir)
        print(f"provenance: OK ({pack_dir})")


if __name__ == "__main__":
    main()
