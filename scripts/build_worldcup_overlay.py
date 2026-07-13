#!/usr/bin/env python3
"""Build an exact-kickoff overlay for an internationals pack from openfootball/worldcup.json.

Reads a pinned worldcup.json (fetched at a commit, or a local file), parses its exact
kickoff times, cross-checks every completed World Cup result against the target pack's
own results.csv, and — only if the cross-check is clean — writes ``kickoffs.csv`` into
the pack and records it (name + sha256) in the manifest plus a kickoff-source provenance
block. A single disagreeing result fails the build, so the overlay can never quietly
rewrite history.

This is a build tool (network is allowed here, never at runtime). Golavo's refresh path
calls the same core functions against a freshly downloaded pack.

Usage:
  python scripts/build_worldcup_overlay.py --pack-dir packs/<intl-pack> \
      --commit 056c53ec82feb3fb68da63d1ce74ec59fc23e95d [--input worldcup.json] [--year 2026]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

from golavo_core.ingest import load_match_table
from golavo_core.ingest.worldcup import crosscheck_completed, kickoff_overlay, parse_worldcup

RAW_URL = "https://raw.githubusercontent.com/openfootball/worldcup.json/{commit}/{year}/worldcup.json"


def _load_worldcup(args: argparse.Namespace) -> dict:
    if args.input:
        return json.loads(Path(args.input).read_text(encoding="utf-8"))
    url = RAW_URL.format(commit=args.commit, year=args.year)
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack-dir", type=Path, required=True, help="internationals pack")
    parser.add_argument("--commit", required=True, help="pinned worldcup.json commit sha")
    parser.add_argument("--year", default="2026", help="tournament dir (default 2026)")
    parser.add_argument("--input", type=Path, help="local worldcup.json instead of fetching")
    args = parser.parse_args()

    pack_dir: Path = args.pack_dir
    parsed = parse_worldcup(_load_worldcup(args))
    reference = load_match_table(pack_dir)

    disagreements = crosscheck_completed(parsed, reference)
    if disagreements:
        print("::error::worldcup.json disagrees with the pack on completed results:")
        for d in disagreements:
            print(f"  {d['date']} {d['home_team']} v {d['away_team']}: "
                  f"worldcup {d['worldcup']} != reference {d['reference']}")
        sys.exit(1)

    overlay = kickoff_overlay(parsed)
    overlay_path = pack_dir / "kickoffs.csv"
    overlay.to_csv(overlay_path, index=False)

    manifest_path = pack_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = [e for e in manifest.get("files", []) if e.get("name") != "kickoffs.csv"]
    files.append({"name": "kickoffs.csv", "sha256": _sha256(overlay_path)})
    manifest["files"] = sorted(files, key=lambda e: e["name"])
    manifest["kickoff_source"] = {
        "source_id": "openfootball-worldcup-json",
        "url": "https://github.com/openfootball/worldcup.json",
        "upstream_ref": args.commit,
        "license": "CC0-1.0",
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    complete = int(parsed["is_complete"].sum())
    print(
        f"wrote {overlay_path.name}: {len(overlay)} exact kickoffs; "
        f"cross-check clean ({complete} completed WC results, 0 disagreements vs the pack). "
        "Overlay matches on normalized team names; unmatched rows keep the date proxy."
    )


if __name__ == "__main__":
    main()
