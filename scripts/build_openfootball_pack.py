#!/usr/bin/env python3
"""Build Golavo's pinned openfootball top-league sourcepacks (CC0).

One pack per league (leagues are modeled independently — domestic files carry no
inter-league matches), each mirroring packs/openfootball-eng-pl: pinned season
JSON + CC0 text + a manifest with per-file SHA-256. Network access is confined
to this build step; runtime reads only the vendored, hash-verified packs.
openfootball/football.json is dedicated to the public domain (CC0-1.0). Every
pack is an AUDIT CANDIDATE — the per-league gate verdicts live in
docs/handoff/openfootball-audit.md.

Season ranges below are the exact per-league inventory at the pinned ref
(listed via the GitHub trees API): en.1/de.1 start 2010-11, es.1 2012-13,
it.1 2013-14, fr.1 2014-15; all run through 2025-26.
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
LICENSE_FILE = "CC0-1.0.txt"


def _seasons(first: int, last: int) -> tuple[str, ...]:
    return tuple(f"{year}-{str(year + 1)[-2:]}" for year in range(first, last + 1))


LEAGUES: dict[str, dict[str, object]] = {
    "en.1": {
        "pack": "openfootball-eng-pl",
        "competition": "English Premier League",
        "seasons": _seasons(2010, 2025),
    },
    "es.1": {
        "pack": "openfootball-esp-ll",
        "competition": "La Liga",
        "seasons": _seasons(2012, 2025),
    },
    "de.1": {
        "pack": "openfootball-deu-bl",
        "competition": "Bundesliga",
        "seasons": _seasons(2010, 2025),
    },
    "it.1": {
        "pack": "openfootball-ita-sa",
        "competition": "Serie A",
        "seasons": _seasons(2013, 2025),
    },
    "fr.1": {
        "pack": "openfootball-fra-l1",
        "competition": "Ligue 1",
        "seasons": _seasons(2014, 2025),
    },
}
NEW_LEAGUES = ("es.1", "de.1", "it.1", "fr.1")  # en.1 shipped in Phase 1; do not re-vendor


def _get(url: str, accept: str | None = None) -> bytes:
    headers = {"User-Agent": "golavo-sourcepack"}
    if accept:
        headers["Accept"] = accept
    with urlopen(Request(url, headers=headers), timeout=60) as response:  # noqa: S310
        return response.read()


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _fetch_license() -> bytes:
    license_meta = json.loads(_get(API_LICENSE, accept="application/vnd.github+json"))
    spdx = license_meta.get("license", {}).get("spdx_id", "")
    license_text = base64.b64decode(license_meta["content"])
    if spdx != "CC0-1.0" or b"CC0 1.0 Universal" not in license_text:
        raise RuntimeError(f"upstream license is not the expected CC0-1.0 (got {spdx!r})")
    return license_text


def build_pack(league: str, output_dir: Path, license_text: bytes) -> dict[str, object]:
    """Download one league's pinned season files, write the pack, return the manifest."""
    spec = LEAGUES[league]
    output_dir.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, str]] = []

    for season in spec["seasons"]:
        name = f"{season}.{league}.json"
        payload = _get(f"{RAW_BASE}/{season}/{league}.json")
        json.loads(payload)  # fail loudly on malformed JSON
        (output_dir / name).write_bytes(payload)
        entries.append({"name": name, "season": season, "sha256": _sha256(payload)})

    (output_dir / LICENSE_FILE).write_bytes(license_text)
    entries.append({"name": LICENSE_FILE, "sha256": _sha256(license_text)})

    manifest: dict[str, object] = {
        "source_id": SOURCE_ID,
        "url": SOURCE_URL,
        "upstream_ref": UPSTREAM_REF,
        "retrieved_at_utc": datetime.now(UTC)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "competition": spec["competition"],
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
        "leagues",
        nargs="*",
        choices=sorted(LEAGUES),
        help="league codes to vendor (default: the four Phase 2 leagues; "
        "en.1 is already vendored and re-vendoring would churn its manifest)",
    )
    parser.add_argument("--output-root", type=Path, default=Path("packs"))
    args = parser.parse_args()
    leagues = args.leagues or list(NEW_LEAGUES)
    license_text = _fetch_license()
    for league in leagues:
        output_dir = args.output_root / str(LEAGUES[league]["pack"])
        manifest = build_pack(league, output_dir, license_text)
        print(f"wrote {output_dir} at {manifest['upstream_ref']} ({len(manifest['files'])} files)")


if __name__ == "__main__":
    main()
