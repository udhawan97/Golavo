#!/usr/bin/env python3
"""Build a refreshed internationals pack that also carries the World Cup fixtures
martj42 hasn't published yet, sourced from CC0 openfootball/worldcup.json.

Flow (network confined to this build step):
  1. download martj42 at a pinned commit (results + side tables + CC0 text);
  2. cross-check every completed World Cup result in worldcup.json against martj42 —
     a single disagreement fails the build closed;
  3. append the SCHEDULED World Cup fixtures worldcup.json carries but martj42 lacks
     (real teams only; W###/L### placeholders are skipped) with their venue/country;
  4. write a kickoffs.csv overlay of exact kickoff instants for every parsed fixture;
  5. record BOTH sources in the manifest — martj42 as the results/training source, and
     worldcup.json as the fixture/kickoff co-source — and append the pack to
     packs/snapshots.json (immutable, append-only).

The engine then trains on martj42 history, seals the added fixtures with exact windows,
and names both sources in each artifact's provenance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import build_sourcepack as bsp

from golavo_core.ingest.snapshot import load_match_table
from golavo_core.ingest.worldcup import (
    TOURNAMENT,
    crosscheck_completed,
    kickoff_overlay,
    missing_fixtures,
    parse_worldcup,
)

WC_RAW = "https://raw.githubusercontent.com/openfootball/worldcup.json/{commit}/{year}/{name}"
_CC_COUNTRY = {"us": "United States", "ca": "Canada", "mx": "Mexico"}


def _fetch_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _now_z() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _download_martj42(ref: str, out_dir: Path) -> None:
    raw_base = f"{bsp.RAW_BASE}/{ref}"
    for name in bsp.FILE_SETS["full"]:
        payload = bsp._download(f"{raw_base}/{name}")
        if name == "results.csv" and not payload.startswith(bsp.RESULTS_HEADER):
            raise RuntimeError("upstream results.csv header changed — re-audit before vendoring")
        (out_dir / name).write_bytes(payload)
    license_payload = bsp._download(f"{raw_base}/LICENSE")
    if b"CC0 1.0 Universal" not in license_payload:
        raise RuntimeError("upstream LICENSE is no longer the expected CC0 1.0 text")
    (out_dir / bsp.LICENSE_FILE).write_bytes(license_payload)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--martj42-ref", required=True, help="full martj42 commit sha")
    parser.add_argument("--wc-commit", required=True, help="pinned worldcup.json commit sha")
    parser.add_argument("--year", default="2026")
    parser.add_argument("--output", type=Path, help="pack dir (default packs/martj42-internationals-<ref12>)")
    parser.add_argument("--wc-input", type=Path, help="local worldcup.json (skip fetch)")
    parser.add_argument("--stadiums-input", type=Path, help="local worldcup.stadiums.json (skip fetch)")
    args = parser.parse_args()

    out_dir: Path = args.output or bsp.REPO_ROOT / f"packs/martj42-internationals-{args.martj42_ref[:12]}"
    if out_dir.exists():
        raise FileExistsError(f"{out_dir} already exists; snapshots are immutable — pick a new dir")

    wc = json.loads(args.wc_input.read_text()) if args.wc_input else _fetch_json(
        WC_RAW.format(commit=args.wc_commit, year=args.year, name="worldcup.json")
    )
    stadiums = json.loads(args.stadiums_input.read_text()) if args.stadiums_input else _fetch_json(
        WC_RAW.format(commit=args.wc_commit, year=args.year, name="worldcup.stadiums.json")
    )
    city_country = {s["city"]: _CC_COUNTRY.get(s["cc"], s["cc"]) for s in stadiums}

    out_dir.mkdir(parents=True)
    _download_martj42(args.martj42_ref, out_dir)

    reference = load_match_table(out_dir)
    parsed = parse_worldcup(wc)

    disagreements = crosscheck_completed(parsed, reference)
    if disagreements:
        print("::error::worldcup.json disagrees with martj42 on completed results:")
        for d in disagreements:
            print(f"  {d['date']} {d['home_team']} v {d['away_team']}: "
                  f"worldcup {d['worldcup']} != martj42 {d['reference']}")
        raise SystemExit(1)

    added = missing_fixtures(parsed, reference, city_country)
    results = out_dir / "results.csv"
    text = results.read_text(encoding="utf-8")
    if not text.endswith("\n"):
        text += "\n"
    for row in added.itertuples(index=False):
        text += (
            f"{row.date},{row.home_team},{row.away_team},NA,NA,"
            f"{row.tournament},{row.city},{row.country},TRUE\n"
        )
    results.write_text(text, encoding="utf-8")

    overlay = kickoff_overlay(parsed)
    overlay = overlay.assign(date=overlay["date"].dt.strftime("%Y-%m-%d"))
    overlay.to_csv(out_dir / "kickoffs.csv", index=False)

    committed_at = bsp.upstream_committed_at(args.martj42_ref)
    file_names = sorted([*bsp.FILE_SETS["full"], bsp.LICENSE_FILE, "kickoffs.csv"])
    manifest = {
        "source_id": bsp.SOURCE_ID,
        "url": bsp.SOURCE_URL,
        "upstream_ref": args.martj42_ref,
        "upstream_committed_at_utc": committed_at,
        "retrieved_at_utc": _now_z(),
        "files": [{"name": n, "sha256": _sha256(out_dir / n)} for n in file_names],
        "license": "CC0-1.0",
        "co_sources": [
            {
                "source_id": "openfootball-worldcup-json",
                "url": "https://github.com/openfootball/worldcup.json",
                "upstream_ref": args.wc_commit,
                "retrieved_at_utc": _now_z(),
                "license": "CC0-1.0",
                "sha256_file": "kickoffs.csv",
            }
        ],
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    bsp.register(out_dir, manifest)
    print(
        f"wrote {out_dir.relative_to(bsp.REPO_ROOT)}: +{len(added)} World Cup fixtures, "
        f"{len(overlay)} exact kickoffs; cross-check clean vs martj42. "
        "Now run: python -m golavo_core index && commit data/index + the pack + snapshots.json"
    )


if __name__ == "__main__":
    main()
