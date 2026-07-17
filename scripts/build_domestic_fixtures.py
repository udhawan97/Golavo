"""Pin the OpenFootball 2026-27 domestic fixture lists into the league packs.

football.json — the source every bundled domestic pack is built from — stops at
2025-26 and upstream has not regenerated it for 2026-27. The schedules exist
only as Football.TXT in the per-country repos, so this script fetches one pinned
file per league and adds it to that league's existing pack.

The fixtures are a CO-SOURCE, not a new source: a fixture's training history is
scoped to its own ``source_id``, so a 2026-27 row carried under a separate
source would have no history to learn from. The pack therefore keeps
``source_id: openfootball-football-json`` (which still supplies every result the
models train on) and records the fixture list's true origin two ways:

* ``co_sources`` in the manifest — repo, pinned commit, license, file hash;
* ``field_provenance.csv`` — per row, that identity and kickoff came from the
  .txt repo, that no result source exists yet, and ``training_eligible=false``.

This mirrors the World Cup co-source path in ``server/golavo_server/refresh.py``.

Usage: python scripts/build_domestic_fixtures.py [--check]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SEASON = "2026-27"
SOURCE_ID = "openfootball-football-json"
_MAX_BYTES = 2_000_000
_RAW = "https://raw.githubusercontent.com/openfootball"

# league code -> (pack, upstream repo, path in that repo, pinned commit,
#                 committed_at, published fixture count)
LEAGUES: dict[str, tuple[str, str, str, str, str, int]] = {
    "en.1": (
        "openfootball-eng-pl", "england", "2026-27/1-premierleague.txt",
        "afc118c3314171ef0b2cbb43ea0144ca3ebaf0b9", "2026-07-02T16:05:26Z", 380,
    ),
    "de.1": (
        "openfootball-deu-bl", "deutschland", "2026-27/1-bundesliga.txt",
        "68a414df2703cdd67b1b5eb1c413c5f07837e36d", "2026-07-06T12:35:05Z", 306,
    ),
    "es.1": (
        "openfootball-esp-ll", "espana", "2026-27/1-liga.txt",
        "a3fd997aabb623ccdc1f8006e5f31525be6f89c6", "2026-07-02T16:05:28Z", 380,
    ),
    "it.1": (
        "openfootball-ita-sa", "italy", "2026-27/1-seriea.txt",
        "0ecb64bc6e8f771a5374abacaf9ecb0e8a886c7b", "2026-07-02T16:05:32Z", 380,
    ),
    "fr.1": (
        # France has no repo of its own; Ligue 1 lives in openfootball/europe.
        "openfootball-fra-l1", "europe", "france/2026-27_fr1.txt",
        "159d7367f7d82748682f0225096e5ef48bbaf49d", "2026-07-08T11:55:24Z", 306,
    ),
}


def _fetch(repo: str, path: str, ref: str) -> bytes:
    url = f"{_RAW}/{repo}/{ref}/{path}"
    request = urllib.request.Request(url, headers={"User-Agent": "golavo-pack-builder"})
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - pinned host
        payload = response.read(_MAX_BYTES + 1)
    if len(payload) > _MAX_BYTES:
        raise ValueError(f"{url}: fixture file exceeds {_MAX_BYTES} bytes")
    return payload


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _provenance_rows(frame) -> list[dict[str, str]]:
    """Per-fixture provenance: the .txt repo gave identity and kickoff, nothing else."""
    return [
        {
            "date": row.date.strftime("%Y-%m-%d"),
            "home_team": row.home_team,
            "away_team": row.away_team,
            "identity_source_id": row.co_source_id,
            "result_source_id": "",
            "kickoff_source_id": row.co_source_id,
            "venue_source_id": "",
            "training_source_id": "",
            "upstream_fixture_key": f"{row.co_source_id}:{SEASON}:{row.matchday}",
            "training_eligible": "false",
        }
        for row in frame.itertuples(index=False)
    ]


def build(check_only: bool = False) -> int:
    import pandas as pd

    sys.path.insert(0, str(REPO_ROOT / "core"))
    from golavo_core.ingest.domestictxt import parse_domestic_txt

    drift = 0
    for code, (pack_name, repo, path, ref, committed_at, expected) in LEAGUES.items():
        pack_dir = REPO_ROOT / "packs" / pack_name
        payload = _fetch(repo, path, ref)
        text = payload.decode("utf-8")
        frame = parse_domestic_txt(text, season=SEASON, league_code=code)
        if len(frame) != expected:
            raise ValueError(
                f"{repo}/{path}: parsed {len(frame)} fixtures, expected {expected}"
            )
        co_source_id = f"openfootball-{repo}"
        file_name = f"{SEASON}.{code}.txt"

        if check_only:
            existing = pack_dir / file_name
            if not existing.is_file() or _sha256(existing.read_bytes()) != _sha256(payload):
                print(f"DRIFT {pack_name}/{file_name}: pinned bytes differ from upstream {ref[:8]}")
                drift += 1
            continue

        (pack_dir / file_name).write_bytes(payload)

        manifest = json.loads((pack_dir / "manifest.json").read_text(encoding="utf-8"))
        files = [e for e in manifest["files"] if e["name"] != file_name]
        files.append(
            {
                "name": file_name,
                "season": SEASON,
                "sha256": _sha256(payload),
                "source_match_count": expected,
            }
        )
        manifest["files"] = sorted(files, key=lambda e: e["name"])
        manifest["co_sources"] = [
            {
                "source_id": co_source_id,
                "url": f"https://github.com/openfootball/{repo}",
                "upstream_ref": ref,
                "upstream_committed_at_utc": committed_at,
                "license": "CC0-1.0",
                "sha256_file": file_name,
                "raw_sha256": {path: _sha256(payload)},
            }
        ]
        (pack_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

        provenance = frame.assign(co_source_id=co_source_id)
        pd.DataFrame(
            _provenance_rows(provenance),
            columns=[
                "date", "home_team", "away_team", "identity_source_id",
                "result_source_id", "kickoff_source_id", "venue_source_id",
                "training_source_id", "upstream_fixture_key", "training_eligible",
            ],
        ).to_csv(pack_dir / "field_provenance.csv", index=False, lineterminator="\n")

        # field_provenance.csv is itself pack bytes: declare and hash it too.
        manifest = json.loads((pack_dir / "manifest.json").read_text(encoding="utf-8"))
        files = [e for e in manifest["files"] if e["name"] != "field_provenance.csv"]
        files.append(
            {
                "name": "field_provenance.csv",
                "sha256": _sha256((pack_dir / "field_provenance.csv").read_bytes()),
            }
        )
        manifest["files"] = sorted(files, key=lambda e: e["name"])
        (pack_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"{pack_name}: pinned {expected} {SEASON} fixtures from {repo}@{ref[:8]}")
    return drift


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="report drift between the pinned bytes and upstream without writing",
    )
    args = parser.parse_args()
    return build(check_only=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
