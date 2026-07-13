#!/usr/bin/env python3
"""Render THIRD_PARTY_NOTICES.md from the machine-readable source registry.

The registry (data/sources/registry.json) is the single source of truth for data
attribution; this script turns it into a human-readable notices file so the two
can never silently drift. Run with --check in CI to fail if the committed file is
stale. Software dependency notices come from the release SBOM (Syft), not here.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "data/sources/registry.json"
SNAPSHOTS_PATH = REPO_ROOT / "packs/snapshots.json"
OUTPUT_PATH = REPO_ROOT / "THIRD_PARTY_NOTICES.md"

_HEADING = {
    "core": "Bundled data (public domain / CC0)",
    "enrichment": "Bundled enrichment data (CC BY)",
    "odbl-pack": "Optional isolated packs — ODbL (share-alike)",
    "by-sa-pack": "Optional isolated packs — CC BY-SA (share-alike)",
    "research-pack": "Optional research packs (historical event/tracking data)",
    "blocked": "Evaluated but blocked (not used)",
    "rejected": "Reviewed and rejected (not used)",
}
_ORDER = ["core", "enrichment", "odbl-pack", "by-sa-pack", "research-pack", "blocked", "rejected"]


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _bundled_source_ids() -> set[str]:
    return {str(s["source_id"]) for s in _load(SNAPSHOTS_PATH)["snapshots"]}


def render() -> str:
    registry = _load(REGISTRY_PATH)
    bundled = _bundled_source_ids()
    by_class: dict[str, list[dict[str, Any]]] = {}
    for entry in registry["sources"]:
        by_class.setdefault(entry["classification"], []).append(entry)

    lines: list[str] = [
        "# Third-party notices",
        "",
        "Golavo's own code is licensed Apache-2.0 (see `LICENSE`). This file, generated",
        "from `data/sources/registry.json` by `scripts/gen_third_party_notices.py`, records",
        "the data sources Golavo carries, plans, or has rejected. Software dependency",
        "notices ship as an SPDX/CycloneDX SBOM alongside each release.",
        "",
        "> Do not edit by hand — run `python scripts/gen_third_party_notices.py`.",
        "",
    ]
    for cls in _ORDER:
        entries = sorted(by_class.get(cls, []), key=lambda e: e["source_id"])
        if not entries:
            continue
        lines.append(f"## {_HEADING[cls]}")
        lines.append("")
        for entry in entries:
            status = ""
            if cls in {"core", "enrichment"}:
                status = (
                    " — **bundled**"
                    if entry["source_id"] in bundled
                    else " — available, not bundled"
                )
            elif cls in {"odbl-pack", "by-sa-pack", "research-pack"}:
                status = " — optional download, isolated pack"
            lines.append(f"### {entry['name']}{status}")
            lines.append("")
            lines.append(f"- Source: {entry['url']}")
            lines.append(f"- Contributors: {', '.join(entry['contributors'])}")
            lines.append(f"- License: {entry['license']}"
                         + (f" ({entry['license_url']})" if entry.get("license_url") else ""))
            if entry.get("attribution"):
                lines.append(f"- Attribution: {entry['attribution']}")
            if entry.get("citation_key"):
                lines.append(f"- Citation key: `{entry['citation_key']}` (see CITATIONS.bib)")
            if entry.get("recheck_by"):
                lines.append(f"- Recheck by: {entry['recheck_by']}")
            lines.append(f"- Notes: {entry['notes']}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if the committed file is stale")
    args = parser.parse_args()
    rendered = render()
    if args.check:
        current = OUTPUT_PATH.read_text(encoding="utf-8") if OUTPUT_PATH.is_file() else ""
        if current != rendered:
            print(
                "::error::THIRD_PARTY_NOTICES.md is stale — "
                "run scripts/gen_third_party_notices.py"
            )
            sys.exit(1)
        print("THIRD_PARTY_NOTICES.md: up to date")
        return
    OUTPUT_PATH.write_text(rendered, encoding="utf-8")
    print(f"wrote {OUTPUT_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
