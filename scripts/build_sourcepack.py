#!/usr/bin/env python3
"""Build Golavo's pinned martj42 internationals sourcepack.

Network access is explicit and confined to this build step. Runtime code reads
only the vendored, hash-verified pack.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import urlopen

SOURCE_ID = "martj42-international-results"
SOURCE_URL = "https://github.com/martj42/international_results"
UPSTREAM_REF = "ddd7249ac0c24c44a5bd8c3af1bf16fc971bebe9"
RAW_BASE = f"https://raw.githubusercontent.com/martj42/international_results/{UPSTREAM_REF}"
SOURCE_FILES = ("results.csv", "goalscorers.csv", "shootouts.csv", "former_names.csv")
LICENSE_FILE = "CC0-1.0.txt"


def _download(url: str) -> bytes:
    with urlopen(url, timeout=60) as response:  # noqa: S310 - URLs are pinned constants.
        return response.read()


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def build_sourcepack(output_dir: Path) -> dict[str, object]:
    """Download pinned files, write them, and return their manifest."""
    output_dir.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, str]] = []

    for name in SOURCE_FILES:
        payload = _download(f"{RAW_BASE}/{name}")
        (output_dir / name).write_bytes(payload)
        entries.append({"name": name, "sha256": _sha256(payload)})

    license_payload = _download(f"{RAW_BASE}/LICENSE")
    if b"CC0 1.0 Universal" not in license_payload:
        raise RuntimeError("upstream LICENSE is no longer the expected CC0 1.0 text")
    (output_dir / LICENSE_FILE).write_bytes(license_payload)
    entries.append({"name": LICENSE_FILE, "sha256": _sha256(license_payload)})

    manifest: dict[str, object] = {
        "source_id": SOURCE_ID,
        "url": SOURCE_URL,
        "upstream_ref": UPSTREAM_REF,
        "retrieved_at_utc": datetime.now(UTC).isoformat(timespec="seconds").replace(
            "+00:00", "Z"
        ),
        "files": entries,
        "license": "CC0-1.0",
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("packs/martj42-internationals"),
        help="sourcepack directory (default: packs/martj42-internationals)",
    )
    args = parser.parse_args()
    manifest = build_sourcepack(args.output)
    print(f"wrote {args.output} at {manifest['upstream_ref']}")


if __name__ == "__main__":
    main()
