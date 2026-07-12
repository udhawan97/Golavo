#!/usr/bin/env python3
"""Watch martj42 for a genuinely-future international fixture and seal it.

Golavo's first *live* forecast is gated on upstream publishing a scheduled fixture
whose kickoff is still ahead (e.g. a World Cup final, added a few days out). Run on
a schedule, this script does nothing until such a fixture appears, then:

  1. pins the freshest CC0 martj42 snapshot (immutable, hash-manifested);
  2. seals a deterministic forecast for each future fixture into the forward
     ledger (``data/artifacts``), leak-safe at ``as_of = now``;
  3. rebuilds the committed match index so the fixture + snapshot are searchable;
  4. commits, and with ``--push`` pushes to ``main``.

Safe to run every day: it first checks the upstream results.csv *in memory*, so no
future fixture means a clean no-op (exit 0) with nothing fetched to disk, nothing
pinned, nothing committed. An already-sealed fixture is skipped (idempotent), and
nothing is backdated — ``as_of`` is the real clock, which the seal engine requires
to be < kickoff (a fixture whose 00:00 UTC day-proxy has passed is never sealed).
Network is confined to the martj42 fetch. ``--dry-run`` detects and reports only.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = REPO_ROOT / "data/artifacts"
INDEX_PATH = REPO_ROOT / "data/index/matches_index.parquet"
COMMIT_API = "https://api.github.com/repos/martj42/international_results/commits/master"
RESULTS_RAW = "https://raw.githubusercontent.com/martj42/international_results/{ref}/results.csv"
FAMILY = "dixon_coles"

sys.path.insert(0, str(REPO_ROOT / "core"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))


def _latest_ref() -> str:
    """The current HEAD sha of martj42/international_results (the data source)."""
    with urlopen(COMMIT_API, timeout=60) as response:  # noqa: S310 (pinned https)
        return str(json.load(response)["sha"])


def _fetch_results(ref: str) -> str:
    with urlopen(RESULTS_RAW.format(ref=ref), timeout=60) as response:  # noqa: S310 (pinned https)
        return response.read().decode("utf-8")


def future_fixtures_from_csv(csv_text: str, now: datetime) -> list[dict[str, str]]:
    """Scheduled (no-score) fixtures dated strictly after today.

    kickoff is the conservative 00:00 UTC day proxy, so a fixture whose date is
    today has already passed its proxy (now > 00:00) and is NOT sealable — only a
    strictly-later date is genuinely ahead. Pure over the CSV text, so it's unit
    testable without the network.
    """
    today = now.strftime("%Y-%m-%d")
    scheduled: list[dict[str, str]] = []
    for row in csv.DictReader(io.StringIO(csv_text)):
        no_score = (row.get("home_score") or "NA") in ("", "NA") and (
            row.get("away_score") or "NA"
        ) in ("", "NA")
        if no_score and row["date"] > today:
            scheduled.append(
                {"date": row["date"], "home_team": row["home_team"], "away_team": row["away_team"]}
            )
    return scheduled


def _already_sealed(fixture: dict[str, str]) -> bool:
    """True if the forward ledger already holds a seal for this (date, teams)."""
    if not ARTIFACT_DIR.exists():
        return False
    key = (fixture["date"], fixture["home_team"], fixture["away_team"])
    for path in ARTIFACT_DIR.glob("fa_*.json"):
        try:
            match = json.loads(path.read_text(encoding="utf-8")).get("match", {})
        except (ValueError, OSError, AttributeError):
            continue
        seal_key = (
            str(match.get("kickoff_utc"))[:10],
            match.get("home_team"),
            match.get("away_team"),
        )
        if seal_key == key:
            return True
    return False


def _pin_pack(ref: str) -> Path:
    from build_sourcepack import _registered_pack_for_ref, build_sourcepack

    existing = _registered_pack_for_ref(ref)
    if existing is not None:
        return REPO_ROOT / existing
    target = REPO_ROOT / f"packs/martj42-internationals-{ref[:12]}"
    build_sourcepack(ref, target, "full")
    return target


def _seal(pack_dir: Path, fixture: dict[str, str], now: datetime) -> Path:
    from golavo_core.artifacts import load_verified_artifact, seal_forecast

    path = seal_forecast(
        pack_dir=pack_dir,
        output_dir=ARTIFACT_DIR,
        date=fixture["date"],
        home_team=fixture["home_team"],
        away_team=fixture["away_team"],
        as_of_utc=now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        family=FAMILY,
    )
    try:  # best-effort notebook beside the seal, mirroring `golavo notebook`
        from golavo_core.facts import load_side_tables, notebook_for_artifact
        from golavo_core.ingest import load_matches

        artifact = load_verified_artifact(path)
        goalscorers, shootouts = load_side_tables(pack_dir)
        notebook = notebook_for_artifact(
            artifact, load_matches(pack_dir), goalscorers=goalscorers, shootouts=shootouts
        )
        out = ARTIFACT_DIR / "notebooks" / f"{artifact['artifact_id']}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(notebook, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except Exception as exc:  # noqa: BLE001 (notebook is context, never blocks the seal)
        print(f"[watch]   (notebook skipped: {exc})")
    return path


def _rebuild_index() -> None:
    from golavo_core.ingest import build_match_index, default_index_packs

    build_match_index(default_index_packs(REPO_ROOT), INDEX_PATH)


def _git(*args: str) -> None:
    subprocess.run(["git", "-C", str(REPO_ROOT), *args], check=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--push", action="store_true", help="git commit AND push to main")
    parser.add_argument("--dry-run", action="store_true", help="detect only; write nothing")
    args = parser.parse_args(argv)
    now = datetime.now(UTC)

    ref = _latest_ref()
    scheduled = future_fixtures_from_csv(_fetch_results(ref), now)
    todo = [f for f in scheduled if not _already_sealed(f)]
    listing = ", ".join(f"{f['home_team']} v {f['away_team']} ({f['date']})" for f in todo)

    if not todo:
        seen = f" ({len(scheduled)} scheduled, already sealed)" if scheduled else ""
        stamp = f"ref {ref[:12]}, {now:%Y-%m-%d}"
        print(f"[watch] no upcoming international fixture to seal ({stamp}){seen}.")
        return 0
    if args.dry_run:
        print(f"[watch] dry-run: WOULD seal {len(todo)} fixture(s): {listing}")
        return 0

    print(f"[watch] sealing {len(todo)} fixture(s): {listing}")
    pack_dir = _pin_pack(ref)
    for fixture in todo:
        path = _seal(pack_dir, fixture, now)
        print(f"[watch]   sealed {fixture['home_team']} v {fixture['away_team']} -> {path.name}")
    _rebuild_index()
    names = ", ".join(f"{f['home_team']} v {f['away_team']}" for f in todo)
    _git("add", "packs", "data/artifacts", "data/index")
    _git("commit", "-m", f"feat(ledger): first live seal(s) — {names}")
    if args.push:
        _git("push", "origin", "HEAD:main")
    outcome = "committed + pushed" if args.push else "committed (not pushed)"
    print(f"[watch] {outcome} {len(todo)} seal(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
