#!/usr/bin/env python3
"""Build and register pinned OpenFootball UEFA club-competition sourcepacks.

Only completed main-competition seasons that passed an exact row-count and
Football.TXT grammar audit are vendored. Qualifying files are intentionally out
of scope. Runtime ingestion remains network-free and verifies every file hash.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from golavo_core.ingest.footballtxt import parse_footballtxt

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.packlib import append_snapshot, sha256  # noqa: E402

REGISTRY_PATH = REPO_ROOT / "packs/snapshots.json"
SOURCE_ID = "openfootball-champions-league"
SOURCE_URL = "https://github.com/openfootball/champions-league"
UPSTREAM_REF = "abfaeddc2ee3d14f99ecc163c9ddb46cb4d67cef"
UPSTREAM_COMMITTED_AT_UTC = "2026-07-02T15:56:11Z"
RAW_BASE = f"https://raw.githubusercontent.com/openfootball/champions-league/{UPSTREAM_REF}"
LICENSE_FILE = "CC0-1.0.txt"
MATCH_COUNT = re.compile(r"^# Matches\s+(?P<count>\d+)\s*$", re.MULTILINE)


def _seasons(first: int, last: int) -> tuple[str, ...]:
    return tuple(f"{year}-{str(year + 1)[-2:]}" for year in range(first, last + 1))


COMPETITIONS: dict[str, dict[str, Any]] = {
    "cl": {
        "pack": "openfootball-uefa-champions-league",
        "competition_id": "uefa-champions-league",
        "competition": "UEFA Champions League",
        "seasons": _seasons(2020, 2025),
    },
    "el": {
        "pack": "openfootball-uefa-europa-league",
        "competition_id": "uefa-europa-league",
        "competition": "UEFA Europa League",
        "seasons": _seasons(2020, 2024),
    },
    "conf": {
        "pack": "openfootball-uefa-conference-league",
        "competition_id": "uefa-conference-league",
        "competition": "UEFA Conference League",
        "seasons": _seasons(2021, 2024),
    },
}


def _get(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "golavo-sourcepack"})
    with urlopen(request, timeout=60) as response:  # noqa: S310 - pinned HTTPS only
        return response.read()


def _format_era(competition_id: str, season: str) -> str:
    if season >= "2024-25":
        return f"{competition_id}-league-2024"
    return f"{competition_id}-group-2021"


def _audit_file(payload: bytes, *, season: str, code: str, competition: str) -> dict[str, Any]:
    text = payload.decode("utf-8")
    declared = MATCH_COUNT.search(text)
    if declared is None:
        raise RuntimeError(f"{season}/{code}.txt has no declared match count")
    source_match_count = int(declared["count"])
    match_lines = sum(" v " in line for line in text.splitlines())
    if match_lines != source_match_count:
        raise RuntimeError(
            f"{season}/{code}.txt carries {match_lines} match lines, "
            f"but declares {source_match_count}"
        )
    frame = parse_footballtxt(text, season=season, competition=competition)
    if len(frame) != source_match_count:
        raise RuntimeError(
            f"{season}/{code}.txt parsed {len(frame)} matches, expected {source_match_count}"
        )
    cancelled = int(frame["result_status"].eq("cancelled").sum())
    completed = int(frame[["home_score", "away_score"]].notna().all(axis=1).sum())
    if completed + cancelled != source_match_count:
        raise RuntimeError(f"{season}/{code}.txt contains an unresolved non-cancelled fixture")
    return {
        "source_match_count": source_match_count,
        "cancelled_match_count": cancelled,
        "indexed_match_count": completed,
        "data_from": frame["date"].min().date().isoformat(),
        "data_through": frame["date"].max().date().isoformat(),
    }


def _register(pack_dir: Path, manifest: dict[str, Any]) -> None:
    append_snapshot(
        REGISTRY_PATH,
        {
            "pack": pack_dir.relative_to(REPO_ROOT).as_posix(),
            "source_id": SOURCE_ID,
            "upstream_ref": UPSTREAM_REF,
            "upstream_committed_at_utc": UPSTREAM_COMMITTED_AT_UTC,
            "retrieved_at_utc": manifest["retrieved_at_utc"],
            "manifest_sha256": sha256((pack_dir / "manifest.json").read_bytes()),
        },
    )


def build_pack(code: str, output_root: Path, license_text: bytes) -> Path:
    spec = COMPETITIONS[code]
    output_dir = output_root / str(spec["pack"])
    if output_dir.exists():
        raise FileExistsError(f"{output_dir} already exists; retained packs are immutable")

    downloads: list[tuple[str, bytes, dict[str, Any]]] = []
    data_from: list[str] = []
    data_through: list[str] = []
    for season in spec["seasons"]:
        source_path = f"{season}/{code}.txt"
        payload = _get(f"{RAW_BASE}/{source_path}")
        audit = _audit_file(
            payload,
            season=str(season),
            code=code,
            competition=str(spec["competition"]),
        )
        downloads.append((f"{season}.{code}.txt", payload, audit))
        data_from.append(str(audit["data_from"]))
        data_through.append(str(audit["data_through"]))

    output_dir.mkdir(parents=True)
    entries: list[dict[str, Any]] = []
    for name, payload, audit in downloads:
        (output_dir / name).write_bytes(payload)
        season = name.split(".", 1)[0]
        entries.append(
            {
                "name": name,
                "source_path": f"{season}/{code}.txt",
                "season": season,
                "sha256": sha256(payload),
                "format_era_id": _format_era(str(spec["competition_id"]), season),
                **audit,
            }
        )
    (output_dir / LICENSE_FILE).write_bytes(license_text)
    entries.append({"name": LICENSE_FILE, "sha256": sha256(license_text)})

    manifest: dict[str, Any] = {
        "source_id": SOURCE_ID,
        "url": SOURCE_URL,
        "upstream_ref": UPSTREAM_REF,
        "upstream_committed_at_utc": UPSTREAM_COMMITTED_AT_UTC,
        "retrieved_at_utc": datetime.now(UTC)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "competition": spec["competition"],
        "competition_id": spec["competition_id"],
        "competition_code": code,
        "coverage": {
            "status": "complete-historical-main-competition-results-at-pin",
            "data_from": min(data_from),
            "data_through": max(data_through),
            "qualifiers_included": False,
            "kickoff_precision": "day",
        },
        "files": entries,
        "license": "CC0-1.0",
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _register(output_dir, manifest)
    return output_dir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("codes", nargs="*", choices=sorted(COMPETITIONS))
    parser.add_argument("--output-root", type=Path, default=REPO_ROOT / "packs")
    args = parser.parse_args()

    license_text = _get(f"{RAW_BASE}/LICENSE.md")
    if b"CC0 1.0 Universal" not in license_text:
        raise RuntimeError("upstream LICENSE.md is no longer the expected CC0 text")
    for code in args.codes or list(COMPETITIONS):
        output = build_pack(code, args.output_root, license_text)
        print(f"wrote {output.relative_to(REPO_ROOT)} at {UPSTREAM_REF}")


if __name__ == "__main__":
    main()
