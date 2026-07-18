"""Pin the pre-2010 footballcsv league history into isolated history packs.

footballcsv (CC0) mirrors openfootball with decades the bundled football.json
packs stop short of. This fetches only the seasons BEFORE openfootball's earliest
bundled season (2010-11), so the history never overlaps — and so never duplicates
— the football.json rows already in the index.

England: 1992-93 → 2009-10 (18 seasons). Germany: 1963-64 → 2009-10 (47 seasons).

Usage: python scripts/build_footballcsv_history.py [--check]
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "core"))
sys.path.insert(0, str(REPO_ROOT))

from golavo_core.ingest.footballcsv import parse_footballcsv  # noqa: E402

from scripts.packlib import sha256  # noqa: E402

_RAW = "https://raw.githubusercontent.com/footballcsv"
_MAX_BYTES = 4_000_000

# league -> (pack, repo, football.json code, file code, pinned commit, committed_at,
#            first season start, last season start inclusive)
LEAGUES = {
    "england": (
        "footballcsv-eng-history",
        "england",
        "en.1",
        "eng.1",
        "52b7e5f5f37b28db72dba1fdc8dbec1adae4c8d0",
        "2023-05-28T13:09:55Z",
        1992,
        2009,
    ),
    "deutschland": (
        "footballcsv-deu-history",
        "deutschland",
        "de.1",
        "de.1",
        "178324626681a9e4c42b81463f59f9c4500dbd53",
        "2020-12-01T06:05:32Z",
        1963,
        2009,
    ),
}


def _season(start: int) -> str:
    return f"{start}-{str(start + 1)[2:]}"


def _fetch(repo: str, path: str, ref: str) -> bytes | None:
    url = f"{_RAW}/{repo}/{ref}/{path}"
    request = urllib.request.Request(url, headers={"User-Agent": "golavo-pack-builder"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - pinned host
            payload = response.read(_MAX_BYTES + 1)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise
    if len(payload) > _MAX_BYTES:
        raise ValueError(f"{url}: season file exceeds {_MAX_BYTES} bytes")
    return payload


def build(check_only: bool = False) -> int:
    drift = 0
    for _repo, (
        pack_name,
        repo_name,
        code,
        file_code,
        ref,
        committed_at,
        first,
        last,
    ) in LEAGUES.items():
        pack_dir = REPO_ROOT / "packs" / pack_name
        files: list[dict] = []
        total = 0
        for start in range(first, last + 1):
            season = _season(start)
            decade = f"{start // 10 * 10}s"
            path = f"{decade}/{season}/{file_code}.csv"
            payload = _fetch(repo_name, path, ref)
            if payload is None:
                print(f"  {pack_name}: {season} not published upstream; skipped")
                continue
            frame = parse_footballcsv(payload.decode("utf-8"), league_code=code)
            file_name = f"{season}.{code}.csv"
            total += len(frame)
            files.append(
                {
                    "name": file_name,
                    "season": season,
                    "sha256": sha256(payload),
                    "source_match_count": int(len(frame)),
                }
            )
            if check_only:
                existing = pack_dir / file_name
                if not existing.is_file() or sha256(existing.read_bytes()) != sha256(payload):
                    print(f"DRIFT {pack_name}/{file_name}")
                    drift += 1
            else:
                pack_dir.mkdir(parents=True, exist_ok=True)
                (pack_dir / file_name).write_bytes(payload)

        if check_only:
            continue

        license_text = _fetch(repo_name, "LICENSE.md", ref)
        if license_text is not None:
            (pack_dir / "CC0-1.0.txt").write_bytes(license_text)
            files.append({"name": "CC0-1.0.txt", "sha256": sha256(license_text)})

        manifest = {
            "source_id": pack_name,
            "url": f"https://github.com/footballcsv/{repo_name}",
            "upstream_ref": ref,
            "upstream_committed_at_utc": committed_at,
            # Historical bytes pinned at the upstream commit; provenance is anchored
            # to that commit, so retrieval time is recorded as the commit instant.
            "retrieved_at_utc": committed_at,
            "competition": parse_footballcsv(
                f"Round,Date,Team 1,FT,Team 2\n1,Sat Aug 1 {first},A,0-0,B\n", league_code=code
            )["tournament"].iloc[0],
            "license": "CC0-1.0",
            "coverage": f"{_season(first)}..{_season(last)}",
            "files": sorted(files, key=lambda entry: entry["name"]),
        }
        (pack_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"{pack_name}: pinned {total} matches over {_season(first)}..{_season(last)}")
    return drift


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="report drift without writing")
    args = parser.parse_args()
    return build(check_only=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
