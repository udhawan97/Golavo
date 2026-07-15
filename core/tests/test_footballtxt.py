from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from golavo_core.competitions import competition_by_id
from golavo_core.ingest import load_matches
from golavo_core.ingest.footballtxt import parse_footballtxt

REPO_ROOT = Path(__file__).resolve().parents[2]

EXPECTED_PACKS = {
    "openfootball-uefa-champions-league": (878, 878, "2020-10-20", "2026-05-30"),
    "openfootball-uefa-europa-league": (815, 817, "2020-10-22", "2025-05-21"),
    "openfootball-uefa-conference-league": (576, 576, "2021-09-14", "2025-05-28"),
}

SAMPLE = (
    """= UEFA Champions League 2025/26

▪ League, Matchday 1
  Tue Sep 16 2025
    18:45  Arsenal FC (ENG)        v Club Atlético de Madrid (ESP)  2-1 (1-0)
           FC Internazionale Milano (ITA) v Olympique de Marseille (FRA)  """
    """4-3 pen. 1-1 a.e.t. (1-1, 0-1)

▪ Finals, Round of 16
  Wed Mar 11
    21:00  RB Leipzig (GER)        v Spartak Moskva (RUS)     [cancelled]
"""
)


def test_parser_carries_dates_clocks_stages_and_match_scores() -> None:
    frame = parse_footballtxt(
        SAMPLE, season="2025-26", competition="UEFA Champions League"
    )
    assert len(frame) == 3
    assert frame.loc[0, "date"] == pd.Timestamp("2025-09-16")
    assert frame.loc[1, "local_time"] == "18:45"
    assert frame.loc[1, ["home_score", "away_score"]].tolist() == [1, 1]
    assert frame.loc[1, ["ht_home_score", "ht_away_score"]].tolist() == [0, 1]
    assert frame.loc[1, ["home_team", "away_team"]].tolist() == ["Inter", "Marseille"]
    assert frame.loc[2, "date"] == pd.Timestamp("2026-03-11")
    assert frame.loc[2, "stage"] == "Finals, Round of 16"
    assert frame.loc[2, "result_status"] == "cancelled"


def test_parser_rejects_unrecognized_match_grammar() -> None:
    broken = """= UEFA Champions League 2025/26
  Tue Sep 16 2025
  Arsenal FC (ENG) v mystery
"""
    with pytest.raises(ValueError, match="unsupported Football.TXT match syntax"):
        parse_footballtxt(broken, season="2025-26", competition="UEFA Champions League")


def test_parser_rejects_impossible_half_time_score() -> None:
    broken = """= UEFA Champions League 2025/26
  Tue Sep 16 2025
  Arsenal FC (ENG) v Chelsea FC (ENG) 1-0 (2-0)
"""
    with pytest.raises(ValueError, match="half-time score exceeds"):
        parse_footballtxt(broken, season="2025-26", competition="UEFA Champions League")


def test_parser_rejects_title_identity_drift() -> None:
    with pytest.raises(ValueError, match="title does not match"):
        parse_footballtxt(
            SAMPLE, season="2024-25", competition="UEFA Champions League"
        )


def test_pinned_uefa_packs_are_complete_unique_and_day_precise() -> None:
    for pack, (rows, source_rows, first, last) in EXPECTED_PACKS.items():
        pack_dir = REPO_ROOT / "packs" / pack
        frame = load_matches(pack_dir)
        manifest = json.loads((pack_dir / "manifest.json").read_text(encoding="utf-8"))
        assert len(frame) == rows, pack
        assert sum(item.get("source_match_count", 0) for item in manifest["files"]) == source_rows
        assert frame["is_complete"].all(), pack
        assert frame["match_id"].is_unique, pack
        assert frame["date"].min() == pd.Timestamp(first), pack
        assert frame["date"].max() == pd.Timestamp(last), pack
        assert frame["kickoff_utc"].dt.hour.eq(0).all(), pack
        assert frame["kickoff_precision"].eq("day").all(), pack
        catalog = competition_by_id(manifest["competition_id"])
        assert catalog is not None
        declared_eras = {era["format_era_id"] for era in catalog["format_eras"]}
        packed_eras = {
            item["format_era_id"] for item in manifest["files"] if "format_era_id" in item
        }
        assert packed_eras <= declared_eras


def test_uefa_names_reuse_audited_domestic_identities() -> None:
    teams: set[str] = set()
    for pack in EXPECTED_PACKS:
        frame = load_matches(REPO_ROOT / "packs" / pack)
        teams.update(frame["home_team"].astype(str))
        teams.update(frame["away_team"].astype(str))
    assert "Borussia Mönchengladbach" in teams
    assert "Real Sociedad" in teams
    assert "Lyon" in teams
    assert "Lens" in teams
    assert "Bor. Mönchengladbach" not in teams
    assert "Real Sociedad de Fútbol" not in teams
    assert "Olympique Lyonnais" not in teams
    assert "Racing Club de Lens" not in teams
