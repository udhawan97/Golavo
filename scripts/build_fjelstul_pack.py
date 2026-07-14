#!/usr/bin/env python3
"""Vendor the pinned, isolated Fjelstul men's World Cup history pack.

Network access is confined to this build step. Runtime code reads only the
committed, hash-verified files. The upstream license grant lives in README.md
and DESCRIPTION at the pinned commit, so both are retained as license evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = "fjelstul-worldcup"
SOURCE_URL = "https://github.com/jfjelstul/worldcup"
PIN = "f942c6b"
FULL_REF = "f942c6b9844d8a2bc0621e45ee5c187a56670100"
RAW_BASE = f"https://raw.githubusercontent.com/jfjelstul/worldcup/{FULL_REF}"
OUTPUT = REPO_ROOT / f"packs/fjelstul-worldcup-{PIN}"
ISOLATED_PATH = REPO_ROOT / "packs/isolated.json"

CSV_FILES = (
    "tournaments.csv",
    "tournament_standings.csv",
    "team_appearances.csv",
    "awards.csv",
    "award_winners.csv",
    "host_countries.csv",
    "teams.csv",
)
EVIDENCE_FILES = ("README.md", "DESCRIPTION")
EXPECTED_HEADERS = {
    "tournaments.csv": "key_id,tournament_id,tournament_name,year,start_date,end_date",
    "tournament_standings.csv": "key_id,tournament_id,tournament_name,position,team_id",
    "team_appearances.csv": "key_id,tournament_id,tournament_name,match_id,match_name",
    "awards.csv": "key_id,award_id,award_name,award_description",
    "award_winners.csv": "key_id,tournament_id,tournament_name,award_id,award_name,shared",
    "host_countries.csv": "key_id,tournament_id,tournament_name,team_id,team_name",
    "teams.csv": "key_id,team_id,team_name,team_code",
}


def _get(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "golavo-sourcepack"})
    with urlopen(request, timeout=60) as response:  # noqa: S310 - fixed HTTPS origin/ref.
        return response.read()


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _register(output: Path, manifest: dict[str, object]) -> None:
    registry = (
        json.loads(ISOLATED_PATH.read_text(encoding="utf-8"))
        if ISOLATED_PATH.is_file()
        else {"schema_version": "0.1.0", "snapshots": []}
    )
    entry = {
        "manifest_sha256": _sha256((output / "manifest.json").read_bytes()),
        "pack": output.relative_to(REPO_ROOT).as_posix(),
        "retrieved_at_utc": manifest["retrieved_at"],
        "source_id": SOURCE_ID,
        "upstream_committed_at_utc": "2023-07-20T01:14:23Z",
        "upstream_ref": PIN,
    }
    for current in registry["snapshots"]:
        if current["pack"] == entry["pack"]:
            if current != entry:
                raise RuntimeError("isolated pack registration differs; packs are immutable")
            return
    registry["snapshots"].append(entry)
    ISOLATED_PATH.write_text(
        json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def build(output: Path = OUTPUT) -> dict[str, object]:
    if output.exists():
        raise FileExistsError(f"{output} already exists; isolated packs are immutable")
    downloads: list[tuple[str, bytes]] = []
    for name in CSV_FILES:
        payload = _get(f"{RAW_BASE}/data-csv/{name}")
        header = payload.splitlines()[0].decode("utf-8")
        if not header.startswith(EXPECTED_HEADERS[name]):
            raise RuntimeError(f"{name}: upstream schema changed; stop and re-audit")
        downloads.append((name, payload))
    for name in EVIDENCE_FILES:
        payload = _get(f"{RAW_BASE}/{name}")
        downloads.append((name, payload))

    readme = dict(downloads)["README.md"]
    description = dict(downloads)["DESCRIPTION"]
    if b"CC-BY-SA 4.0 license" not in readme or b"License: CC-BY-SA 4.0" not in description:
        raise RuntimeError("pinned README/DESCRIPTION no longer prove CC-BY-SA-4.0")

    output.mkdir(parents=True)
    entries = []
    for name, payload in downloads:
        (output / name).write_bytes(payload)
        entries.append({"name": name, "sha256": _sha256(payload)})
    manifest: dict[str, object] = {
        "files": entries,
        "license": "CC-BY-SA-4.0",
        "retrieved_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "source_id": SOURCE_ID,
        "upstream_ref": PIN,
        "url": SOURCE_URL,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _register(output, manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    manifest = build(args.output)
    print(f"wrote {args.output} at {manifest['upstream_ref']}")


if __name__ == "__main__":
    main()
