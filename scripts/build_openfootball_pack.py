#!/usr/bin/env python3
"""Build Golavo's pinned openfootball English Premier League sourcepack (CC0).

Network access is confined to this build step; runtime reads only the vendored,
hash-verified pack. openfootball/football.json is dedicated to the public domain
(CC0-1.0). This pack is the club-coverage AUDIT CANDIDATE — the gate verdict is
in docs/handoff/openfootball-audit.md.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import Request, urlopen

SOURCE_ID = "openfootball-football-json"
SOURCE_URL = "https://github.com/openfootball/football.json"
UPSTREAM_REF = "a5dd38b3bcbe3aa2477cf400f569264253d51431"
RAW_BASE = f"https://raw.githubusercontent.com/openfootball/football.json/{UPSTREAM_REF}"
API_LICENSE = "https://api.github.com/repos/openfootball/football.json/license"
LEAGUE_FILE = "en.1.json"  # English Premier League
COMPETITION = "English Premier League"
SEASONS = (
    "2010-11", "2011-12", "2012-13", "2013-14", "2014-15", "2015-16",
    "2016-17", "2017-18", "2018-19", "2019-20", "2020-21", "2021-22",
    "2022-23", "2023-24", "2024-25", "2025-26",
)
LICENSE_FILE = "CC0-1.0.txt"


def _get(url: str, accept: str | None = None) -> bytes:
    headers = {"User-Agent": "golavo-sourcepack"}
    if accept:
        headers["Accept"] = accept
    with urlopen(Request(url, headers=headers), timeout=60) as response:  # noqa: S310
        return response.read()


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def build_pack(output_dir: Path) -> dict[str, object]:
    """Download pinned PL season files + license, write them, return the manifest."""
    output_dir.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, str]] = []

    for season in SEASONS:
        name = f"{season}.en.1.json"
        payload = _get(f"{RAW_BASE}/{season}/{LEAGUE_FILE}")
        json.loads(payload)  # fail loudly on malformed JSON
        (output_dir / name).write_bytes(payload)
        entries.append({"name": name, "season": season, "sha256": _sha256(payload)})

    license_meta = json.loads(_get(API_LICENSE, accept="application/vnd.github+json"))
    spdx = license_meta.get("license", {}).get("spdx_id", "")
    license_text = base64.b64decode(license_meta["content"])
    if spdx != "CC0-1.0" or b"CC0 1.0 Universal" not in license_text:
        raise RuntimeError(f"upstream license is not the expected CC0-1.0 (got {spdx!r})")
    (output_dir / LICENSE_FILE).write_bytes(license_text)
    entries.append({"name": LICENSE_FILE, "sha256": _sha256(license_text)})

    manifest: dict[str, object] = {
        "source_id": SOURCE_ID,
        "url": SOURCE_URL,
        "upstream_ref": UPSTREAM_REF,
        "retrieved_at_utc": datetime.now(UTC)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "competition": COMPETITION,
        "files": entries,
        "license": "CC0-1.0",
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("packs/openfootball-eng-pl"))
    args = parser.parse_args()
    manifest = build_pack(args.output)
    print(f"wrote {args.output} at {manifest['upstream_ref']} ({len(manifest['files'])} files)")


if __name__ == "__main__":
    main()
