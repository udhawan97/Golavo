#!/usr/bin/env python3
"""Build and register one pinned, immutable martj42 internationals snapshot.

Network access is explicit and confined to this build step. Runtime code reads
only vendored, hash-verified packs. Snapshots are retained forever: a pinned
upstream ref is fetched at most once, an existing pack directory is never
overwritten, and packs/snapshots.json only ever gains entries.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.request import urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.packlib import append_snapshot, sha256  # noqa: E402

REGISTRY_PATH = REPO_ROOT / "packs/snapshots.json"

SOURCE_ID = "martj42-international-results"
SOURCE_URL = "https://github.com/martj42/international_results"
# Phase 0 pinned ref; kept as the default so the historical build stays reproducible.
DEFAULT_REF = "ddd7249ac0c24c44a5bd8c3af1bf16fc971bebe9"
RAW_BASE = "https://raw.githubusercontent.com/martj42/international_results"
COMMIT_API = "https://api.github.com/repos/martj42/international_results/commits/{ref}"

FILE_SETS = {
    # Everything Phase 0 vendored.
    "full": ("results.csv", "goalscorers.csv", "shootouts.csv", "former_names.csv"),
    # The minimum the canonical match table reads; used for retained forward-loop
    # snapshots so retention does not grow the repository by unused bytes.
    "core": ("results.csv", "former_names.csv"),
}
LICENSE_FILE = "CC0-1.0.txt"
RESULTS_HEADER = b"date,home_team,away_team,home_score,away_score,tournament,city,country,neutral"


def _download(url: str) -> bytes:
    with urlopen(url, timeout=60) as response:  # noqa: S310 - pinned https URLs only.
        return response.read()


def _utc_z(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def upstream_committed_at(ref: str) -> str:
    """Return the pinned ref's upstream commit time (the data-state anchor)."""
    payload = json.loads(_download(COMMIT_API.format(ref=ref)).decode("utf-8"))
    return _utc_z(payload["commit"]["committer"]["date"])


def load_registry() -> dict[str, Any]:
    if REGISTRY_PATH.exists():
        return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    return {"schema_version": "0.1.0", "snapshots": []}


def registry_entry(pack_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    manifest_bytes = (pack_dir / "manifest.json").read_bytes()
    return {
        "pack": pack_dir.relative_to(REPO_ROOT).as_posix(),
        "source_id": str(manifest["source_id"]),
        "upstream_ref": str(manifest["upstream_ref"]),
        "upstream_committed_at_utc": manifest.get("upstream_committed_at_utc"),
        "retrieved_at_utc": str(manifest["retrieved_at_utc"]),
        "manifest_sha256": sha256(manifest_bytes),
    }


def register(pack_dir: Path, manifest: dict[str, Any]) -> None:
    """Append the snapshot to the registry; existing entries are immutable."""
    append_snapshot(REGISTRY_PATH, registry_entry(pack_dir, manifest))


def _registered_pack_for_ref(ref: str) -> str | None:
    for entry in load_registry()["snapshots"]:
        if entry["source_id"] == SOURCE_ID and entry["upstream_ref"] == ref:
            return str(entry["pack"])
    return None


def build_sourcepack(ref: str, output_dir: Path, file_set: str) -> dict[str, Any]:
    """Download pinned files at one ref, write an immutable pack, register it."""
    if not re.fullmatch(r"[0-9a-f]{40}", ref):
        raise ValueError("upstream ref must be a full 40-hex commit sha (pin exactly)")
    if output_dir.exists():
        raise FileExistsError(
            f"{output_dir} already exists; snapshots are immutable — pick a new directory"
        )

    raw_base = f"{RAW_BASE}/{ref}"
    downloads: list[tuple[str, bytes]] = []
    for name in FILE_SETS[file_set]:
        payload = _download(f"{raw_base}/{name}")
        if name == "results.csv" and not payload.startswith(RESULTS_HEADER):
            raise RuntimeError(
                "upstream results.csv no longer starts with the expected header; "
                "the source schema changed — stop and re-audit before vendoring"
            )
        downloads.append((name, payload))

    license_payload = _download(f"{raw_base}/LICENSE")
    if b"CC0 1.0 Universal" not in license_payload:
        raise RuntimeError("upstream LICENSE is no longer the expected CC0 1.0 text")
    downloads.append((LICENSE_FILE, license_payload))
    committed_at = upstream_committed_at(ref)

    output_dir.mkdir(parents=True)
    entries = []
    for name, payload in downloads:
        (output_dir / name).write_bytes(payload)
        entries.append({"name": name, "sha256": sha256(payload)})
    manifest: dict[str, Any] = {
        "source_id": SOURCE_ID,
        "url": SOURCE_URL,
        "upstream_ref": ref,
        "upstream_committed_at_utc": committed_at,
        "retrieved_at_utc": datetime.now(UTC).isoformat(timespec="seconds").replace(
            "+00:00", "Z"
        ),
        "files": entries,
        "license": "CC0-1.0",
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    register(output_dir, manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", default=DEFAULT_REF, help="full upstream commit sha to pin")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="pack directory (default: packs/martj42-internationals-<ref12>)",
    )
    parser.add_argument(
        "--files",
        choices=sorted(FILE_SETS),
        default="full",
        help="which upstream files to vendor (default: full)",
    )
    args = parser.parse_args()

    existing = _registered_pack_for_ref(args.ref)
    if existing is not None:
        print(f"ref {args.ref} is already retained at {existing}; nothing to do")
        return
    output = args.output or REPO_ROOT / f"packs/martj42-internationals-{args.ref[:12]}"
    manifest = build_sourcepack(args.ref, output, args.files)
    print(f"wrote {output} at {manifest['upstream_ref']} ({args.files} file set)")


if __name__ == "__main__":
    main()
