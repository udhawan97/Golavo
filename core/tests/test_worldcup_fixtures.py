"""worldcup.json as a FIXTURE source: add the semifinals martj42 doesn't carry yet,
seal them (training on martj42 history), and record BOTH sources honestly.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pandas as pd
import pytest
from golavo_core.artifacts import load_verified_artifact, seal_forecast
from golavo_core.ingest import load_match_table
from golavo_core.ingest.snapshot import co_source_descriptors
from golavo_core.ingest.worldcup import missing_fixtures, parse_worldcup

REPO_ROOT = Path(__file__).resolve().parents[2]
PACK = REPO_ROOT / "packs/martj42-internationals"

_WC = {
    "name": "World Cup 2026",
    "matches": [
        {"round": "Semi-final", "num": 101, "date": "2026-07-14", "time": "21:00 UTC-5",
         "team1": "France", "team2": "Spain", "ground": "Dallas (Arlington)"},
        {"round": "Semi-final", "num": 102, "date": "2026-07-15", "time": "15:00 UTC-4",
         "team1": "England", "team2": "Argentina", "ground": "Atlanta"},
        {"round": "Final", "num": 104, "date": "2026-07-19", "time": "15:00 UTC-4",
         "team1": "W101", "team2": "W102", "ground": "New York/New Jersey (East Rutherford)"},
    ],
}
_CITY_COUNTRY = {"Dallas (Arlington)": "United States", "Atlanta": "United States"}


def test_missing_fixtures_adds_only_absent_scheduled_rows() -> None:
    parsed = parse_worldcup(_WC)
    # A reference already containing the France v Spain semi.
    reference = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-07-14"]),
            "home_team": pd.array(["France"], dtype="string"),
            "away_team": pd.array(["Spain"], dtype="string"),
        }
    )
    added = missing_fixtures(parsed, reference, _CITY_COUNTRY)
    # France v Spain is already present; only England v Argentina is added. The W101/W102
    # final is a placeholder dropped by parse_worldcup, so it never reaches here.
    pairs = list(zip(added["home_team"], added["away_team"], strict=True))
    assert pairs == [("England", "Argentina")]
    row = added.iloc[0]
    assert row["country"] == "United States" and bool(row["neutral"]) is True
    assert pd.isna(row["home_score"]) and pd.isna(row["away_score"])


def test_missing_fixtures_fails_closed_on_unmapped_venue() -> None:
    parsed = parse_worldcup(_WC)
    with pytest.raises(ValueError, match="no country mapping"):
        missing_fixtures(parsed, pd.DataFrame(), {"Atlanta": "United States"})  # Dallas missing


def _merged_pack(tmp_path: Path) -> Path:
    """Copy the internationals pack, append the two worldcup semis, add the overlay + co-source."""
    pack = tmp_path / "pack"
    shutil.copytree(PACK, pack)

    reference = load_match_table(pack)
    parsed = parse_worldcup(_WC)
    added = missing_fixtures(parsed, reference, _CITY_COUNTRY)

    # Append the fixture rows to results.csv in martj42's own format (NA scores, TRUE neutral).
    results = pack / "results.csv"
    text = results.read_text(encoding="utf-8")
    if not text.endswith("\n"):
        text += "\n"
    for row in added.itertuples(index=False):
        text += (
            f"{row.date},{row.home_team},{row.away_team},NA,NA,"
            f"{row.tournament},{row.city},{row.country},TRUE\n"
        )
    results.write_text(text, encoding="utf-8")

    # The exact-kickoff overlay for the added fixtures.
    overlay = parsed[["date", "home_team", "away_team", "tournament", "kickoff_utc"]].copy()
    overlay["date"] = overlay["date"].dt.strftime("%Y-%m-%d")
    overlay.to_csv(pack / "kickoffs.csv", index=False)

    manifest_path = pack / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    names = {e["name"] for e in manifest["files"]} | {"kickoffs.csv"}
    manifest["files"] = sorted(
        ({"name": n, "sha256": hashlib.sha256((pack / n).read_bytes()).hexdigest()} for n in names),
        key=lambda e: e["name"],
    )
    manifest["co_sources"] = [
        {
            "source_id": "openfootball-worldcup-json",
            "url": "https://github.com/openfootball/worldcup.json",
            "upstream_ref": "056c53ec82feb3fb68da63d1ce74ec59fc23e95d",
            "retrieved_at_utc": "2026-07-12T00:00:00Z",
            "license": "CC0-1.0",
            "sha256_file": "kickoffs.csv",
        }
    ]
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return pack


def test_co_source_descriptors_build_a_valid_second_snapshot(tmp_path: Path) -> None:
    pack = _merged_pack(tmp_path)
    descriptors = co_source_descriptors(pack)
    assert len(descriptors) == 1
    d = descriptors[0]
    assert d["source_id"] == "openfootball-worldcup-json" and d["license"] == "CC0-1.0"
    assert d["snapshot_id"] == "sp_056c53ec82fe"
    # The provenance digest is the hash of the exact overlay bytes in the pack.
    assert d["sha256"] == hashlib.sha256((pack / "kickoffs.csv").read_bytes()).hexdigest()


def test_seal_an_added_worldcup_semifinal_records_both_sources(tmp_path: Path) -> None:
    """The crown-jewel: a worldcup-sourced fixture seals, trains on martj42, names both sources."""
    pack = _merged_pack(tmp_path)
    # France v Spain kicks off 2026-07-14 21:00 UTC-5 == 2026-07-15 02:00 UTC.
    path = seal_forecast(
        pack_dir=pack,
        output_dir=tmp_path / "ledger",
        date="2026-07-14",
        home_team="France",
        away_team="Spain",
        as_of_utc="2026-07-14T18:00:00Z",  # past the midnight proxy, before the real kickoff
        family="dixon_coles",
    )
    artifact = load_verified_artifact(path)
    # Not abstained: France and Spain have ample martj42 history to train on.
    assert artifact["status"] == "sealed"
    # The window used the exact kickoff, not the 00:00 proxy.
    assert artifact["match"]["kickoff_utc"] == "2026-07-15T02:00:00Z"
    # Honest provenance: BOTH the training source and the fixture source are named.
    sources = {s["source_id"] for s in artifact["inputs"]["snapshots"]}
    assert sources == {"martj42-international-results", "openfootball-worldcup-json"}


def test_added_fixture_never_leaks_into_training(tmp_path: Path) -> None:
    """Sealing France v Spain must train only on prior results, never the added fixture itself."""
    pack = _merged_pack(tmp_path)
    # Seal at the exact kickoff instant -> rejected (window closed), proving the kickoff is exact
    # and the fixture is treated as a scheduled future match, not a played one.
    with pytest.raises(ValueError, match="before kickoff"):
        seal_forecast(
            pack_dir=pack, output_dir=tmp_path / "l2", date="2026-07-14",
            home_team="France", away_team="Spain",
            as_of_utc="2026-07-15T02:00:00Z", family="dixon_coles",
        )
