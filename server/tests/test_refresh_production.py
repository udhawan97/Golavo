from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from golavo_core.ingest import build_match_index
from golavo_server import refresh
from golavo_server.refresh_sources import MARTJ42, WORLDCUP


def _raw_snapshot(root: Path, martj_ref: str, worldcup_ref: str, *, score: str = "2,1") -> None:
    martj = root / MARTJ42 / martj_ref
    martj.mkdir(parents=True)
    (martj / "results.csv").write_text(
        "date,home_team,away_team,home_score,away_score,tournament,city,country,neutral\n"
        f"2020-01-01,Alpha,Beta,{score},Friendly,A City,Aland,FALSE\n",
        encoding="utf-8",
    )
    (martj / "former_names.csv").write_text(
        "current,former,start_date,end_date\n", encoding="utf-8"
    )
    (martj / "goalscorers.csv").write_text(
        "date,home_team,away_team,team,scorer,minute,own_goal,penalty\n", encoding="utf-8"
    )
    (martj / "shootouts.csv").write_text(
        "date,home_team,away_team,winner,first_shooter\n", encoding="utf-8"
    )
    (martj / "LICENSE").write_text("CC0 1.0 Universal", encoding="utf-8")

    worldcup = root / WORLDCUP / worldcup_ref / "2026"
    worldcup.mkdir(parents=True)
    (worldcup / "worldcup.json").write_text(
        json.dumps(
            {
                "matches": [
                    {
                        "num": 104,
                        "date": "2026-08-01",
                        "time": "15:00 UTC-4",
                        "team1": "France",
                        "team2": "Spain",
                        "ground": "Test City",
                        "score": {},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (worldcup / "worldcup.stadiums.json").write_text(
        json.dumps({"stadiums": [{"city": "Test City", "cc": "us"}]}), encoding="utf-8"
    )
    (root / WORLDCUP / worldcup_ref / "LICENSE.md").write_text(
        "CC0 1.0 Universal", encoding="utf-8"
    )


def test_runtime_pack_adds_fixture_with_field_provenance(tmp_path: Path) -> None:
    martj_ref, worldcup_ref = "1" * 40, "2" * 40
    _raw_snapshot(tmp_path / "raw", martj_ref, worldcup_ref)
    pack = tmp_path / "pack"
    result = refresh.build_international_runtime_pack(
        tmp_path / "raw",
        martj_ref=martj_ref,
        martj_committed_at="2026-07-15T00:00:00Z",
        worldcup_ref=worldcup_ref,
        worldcup_committed_at="2026-07-15T00:00:00Z",
        retrieved_at_utc="2026-07-15T01:00:00Z",
        output_dir=pack,
    )
    assert result["added_worldcup_fixtures"] == 1
    index_path = tmp_path / "index" / "matches_index.parquet"
    build_match_index([pack], index_path)
    frame = pd.read_parquet(index_path)
    fixture = frame.loc[frame["home_team"] == "France"].iloc[0]
    assert fixture["identity_source_id"] == WORLDCUP
    assert fixture["kickoff_source_id"] == WORLDCUP
    assert pd.isna(fixture["training_source_id"])
    assert bool(fixture["training_eligible"]) is False


def test_runtime_pack_omits_only_scoreless_unresolved_placeholders(tmp_path: Path) -> None:
    martj_ref, worldcup_ref = "1" * 40, "2" * 40
    _raw_snapshot(tmp_path / "raw", martj_ref, worldcup_ref)
    results = tmp_path / "raw" / MARTJ42 / martj_ref / "results.csv"
    with results.open("a", encoding="utf-8") as handle:
        handle.write(
            "2026-07-19,Spain,NA,NA,NA,FIFA World Cup,East Rutherford,United States,TRUE\n"
        )
    pack = tmp_path / "pack"
    result = refresh.build_international_runtime_pack(
        tmp_path / "raw",
        martj_ref=martj_ref,
        martj_committed_at="2026-07-15T00:00:00Z",
        worldcup_ref=worldcup_ref,
        worldcup_committed_at="2026-07-15T00:00:00Z",
        retrieved_at_utc="2026-07-15T01:00:00Z",
        output_dir=pack,
    )
    assert result["omitted_unresolved_fixtures"] == 1
    derived = pd.read_csv(pack / "results.csv")
    assert derived[["home_team", "away_team"]].notna().all(axis=None)


def test_completed_score_rewrite_is_quarantined(tmp_path: Path) -> None:
    old_ref, new_ref, worldcup_ref = "1" * 40, "3" * 40, "2" * 40
    _raw_snapshot(tmp_path / "old-raw", old_ref, worldcup_ref, score="2,1")
    old_pack = tmp_path / "old-pack"
    refresh.build_international_runtime_pack(
        tmp_path / "old-raw",
        martj_ref=old_ref,
        martj_committed_at="2026-07-15T00:00:00Z",
        worldcup_ref=worldcup_ref,
        worldcup_committed_at="2026-07-15T00:00:00Z",
        retrieved_at_utc="2026-07-15T01:00:00Z",
        output_dir=old_pack,
    )
    old_index = tmp_path / "old-index" / "matches_index.parquet"
    build_match_index([old_pack], old_index)

    _raw_snapshot(tmp_path / "new-raw", new_ref, worldcup_ref, score="3,1")
    new_pack = tmp_path / "new-pack"
    refresh.build_international_runtime_pack(
        tmp_path / "new-raw",
        martj_ref=new_ref,
        martj_committed_at="2026-07-15T02:00:00Z",
        worldcup_ref=worldcup_ref,
        worldcup_committed_at="2026-07-15T00:00:00Z",
        retrieved_at_utc="2026-07-15T03:00:00Z",
        output_dir=new_pack,
    )
    candidate = refresh.merge_refresh_generation(
        new_pack, [], old_index, tmp_path / "candidate", season_start="9999-07-01"
    )
    with pytest.raises(refresh.RefreshConflict, match="rewrites completed evidence"):
        refresh.assert_safe_change(old_index, candidate, tmp_path / "ledger")


def test_sealed_fixture_kickoff_rewrite_is_quarantined(tmp_path: Path) -> None:
    martj_ref, worldcup_ref = "1" * 40, "2" * 40
    _raw_snapshot(tmp_path / "raw", martj_ref, worldcup_ref)
    pack = tmp_path / "pack"
    refresh.build_international_runtime_pack(
        tmp_path / "raw",
        martj_ref=martj_ref,
        martj_committed_at="2026-07-15T00:00:00Z",
        worldcup_ref=worldcup_ref,
        worldcup_committed_at="2026-07-15T00:00:00Z",
        retrieved_at_utc="2026-07-15T01:00:00Z",
        output_dir=pack,
    )
    base_index = tmp_path / "base" / "matches_index.parquet"
    build_match_index([pack], base_index)
    base = pd.read_parquet(base_index)
    fixture = base.loc[base["home_team"] == "France"].iloc[0]

    candidate = base.copy()
    candidate.loc[candidate["match_id"] == fixture["match_id"], "kickoff_utc"] = pd.Timestamp(
        fixture["kickoff_utc"]
    ) + pd.Timedelta(hours=1)
    candidate_path = tmp_path / "candidate" / "matches_index.parquet"
    candidate_path.parent.mkdir()
    candidate.to_parquet(candidate_path, index=False)

    ledger = tmp_path / "ledger"
    ledger.mkdir()
    (ledger / "fa_sealed.json").write_text(
        json.dumps(
            {
                "match": {
                    "match_id": fixture["match_id"],
                    "home_team": fixture["home_team"],
                    "away_team": fixture["away_team"],
                    "kickoff_utc": pd.Timestamp(fixture["kickoff_utc"]).isoformat(),
                    "competition": fixture["competition"],
                    "city": fixture["city"],
                    "country": fixture["country"],
                    "neutral_venue": bool(fixture["neutral"]),
                }
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(refresh.RefreshConflict, match="changes sealed fixture fields"):
        refresh.assert_safe_change(base_index, candidate_path, ledger)
