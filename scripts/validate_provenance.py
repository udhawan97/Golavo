#!/usr/bin/env python3
"""Validate every byte declared by each Golavo sourcepack manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ALLOWED_LICENSES = {"CC0-1.0"}
DEFAULT_PACKS = (
    Path("packs/martj42-internationals"),
    Path("packs/openfootball-eng-pl"),
    Path("packs/openfootball-esp-ll"),
    Path("packs/openfootball-deu-bl"),
    Path("packs/openfootball-ita-sa"),
    Path("packs/openfootball-fra-l1"),
)


def validate_pack(pack_dir: Path) -> None:
    manifest_path = pack_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("license") not in ALLOWED_LICENSES:
        raise ValueError(
            f"{manifest_path}: license {manifest.get('license')!r} "
            f"not in {sorted(ALLOWED_LICENSES)}"
        )
    if not manifest.get("source_id"):
        raise ValueError(f"{manifest_path}: missing source_id")
    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"{manifest_path}: files must be a non-empty list")
    for entry in entries:
        path = pack_dir / entry["name"]
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != entry["sha256"]:
            raise ValueError(
                f"{path}: sha256 mismatch; expected {entry['sha256']}, got {actual}"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packs", nargs="*", type=Path, default=list(DEFAULT_PACKS))
    args = parser.parse_args()
    for pack_dir in args.packs:
        validate_pack(pack_dir)
        print(f"provenance: OK ({pack_dir})")


if __name__ == "__main__":
    main()
