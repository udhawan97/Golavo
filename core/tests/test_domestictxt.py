from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest
from golavo_core.ingest.domestictxt import DOMESTIC_TXT_TITLES, parse_domestic_txt
from golavo_core.ingest.openfootball import canonical_team, load_openfootball_table

# Verbatim head of openfootball/england 2026-27/1-premierleague.txt (CC0), the
# grammar this parser is pinned to: '=' title, '#' metadata, U+25AA matchday
# marker, a year only on the matchday's first date, and a kickoff clock that
# carries down to the fixtures printed beneath it.
SAMPLE = """= English Premier League 2026/27

# Date       Fri Aug 21 2026 - Sun May 30 2027 (282d)
# Teams      20
# Matches    380


▪ Matchday 1
  Fri Aug 21 2026
    20:00  Arsenal FC              v Coventry City FC
  Sat Aug 22
    12:30  Hull City AFC           v Manchester United FC
    15:00  Ipswich Town FC         v Sunderland AFC
           Nottingham Forest FC    v Leeds United FC

▪ Matchday 2
  Sat Jan 2 2027
    15:00  Everton FC              v Crystal Palace FC
"""


def test_parser_carries_matchday_year_and_kickoff_clock() -> None:
    frame = parse_domestic_txt(SAMPLE, season="2026-27", league_code="en.1")

    assert len(frame) == 5
    # The matchday's first date carries its year; the next date omits it.
    assert frame.loc[0, "date"] == pd.Timestamp("2026-08-21")
    assert frame.loc[1, "date"] == pd.Timestamp("2026-08-22")
    assert frame.loc[0, "matchday"] == 1
    # A fixture with no clock of its own inherits the one printed above it.
    assert frame.loc[3, "local_time"] == "15:00"
    assert frame.loc[3, ["home_team", "away_team"]].tolist() == ["Nottingham Forest", "Leeds United"]
    # Unplayed fixtures carry no score and are never complete.
    assert frame["home_score"].isna().all()
    assert not frame["is_complete"].any()
    # The season spans a calendar-year boundary: a bare 'Jan 2' belongs to 2027.
    assert frame.loc[4, "date"] == pd.Timestamp("2027-01-02")
    assert frame.loc[4, "matchday"] == 2


def test_parser_canonicalizes_team_names_to_index_identities() -> None:
    frame = parse_domestic_txt(SAMPLE, season="2026-27", league_code="en.1")
    teams = set(frame["home_team"]) | set(frame["away_team"])
    assert "Arsenal" in teams and "Arsenal FC" not in teams
    assert "Hull City" in teams and "Hull City AFC" not in teams


def test_parser_reads_a_played_result_with_optional_half_time() -> None:
    played = """= English Premier League 2026/27

▪ Matchday 1
  Fri Aug 21 2026
    20:00  Arsenal FC              v Coventry City FC       4-2 (1-0)
           Everton FC              v Fulham FC              0-0
"""
    frame = parse_domestic_txt(played, season="2026-27", league_code="en.1")
    assert frame.loc[0, ["home_score", "away_score"]].tolist() == [4, 2]
    assert frame.loc[0, ["ht_home_score", "ht_away_score"]].tolist() == [1, 0]
    assert frame.loc[1, ["home_score", "away_score"]].tolist() == [0, 0]
    assert pd.isna(frame.loc[1, "ht_home_score"])
    assert frame["is_complete"].all()


def test_parser_accepts_crlf_line_endings() -> None:
    # openfootball line endings drift by season: the 2025-26 EPL file is CRLF.
    frame = parse_domestic_txt(
        SAMPLE.replace("\n", "\r\n"), season="2026-27", league_code="en.1"
    )
    assert len(frame) == 5
    assert frame.loc[0, "home_team"] == "Arsenal"


def test_parser_rejects_a_title_that_is_not_the_expected_league_and_season() -> None:
    with pytest.raises(ValueError, match="title does not match"):
        parse_domestic_txt(SAMPLE, season="2025-26", league_code="en.1")
    with pytest.raises(ValueError, match="title does not match"):
        parse_domestic_txt(SAMPLE, season="2026-27", league_code="de.1")


def test_parser_rejects_a_fixture_whose_away_side_is_missing() -> None:
    # A dropped away side must fail loudly rather than index a club named '4-2'.
    broken = """= English Premier League 2026/27

▪ Matchday 1
  Fri Aug 21 2026
    20:00  Arsenal FC              v  4-2 (1-0)
"""
    with pytest.raises(ValueError, match="unsupported domestic Football.TXT match syntax"):
        parse_domestic_txt(broken, season="2026-27", league_code="en.1")


def test_parser_rejects_a_fixture_printed_before_any_date() -> None:
    broken = """= English Premier League 2026/27

▪ Matchday 1
    20:00  Arsenal FC              v Coventry City FC
"""
    with pytest.raises(ValueError, match="match appears before a date header"):
        parse_domestic_txt(broken, season="2026-27", league_code="en.1")


def _mixed_pack(tmp_path: Path) -> Path:
    """A league pack holding one played .json season and one .txt fixture season."""
    pack = tmp_path / "openfootball-mini"
    pack.mkdir(parents=True)
    played = json.dumps(
        {
            "matches": [
                {
                    "date": "2025-08-16",
                    "team1": "Arsenal FC",
                    "team2": "Everton FC",
                    "score": {"ft": [2, 1]},
                }
            ]
        }
    )
    fixtures = """= English Premier League 2026/27

▪ Matchday 1
  Fri Aug 21 2026
    20:00  Arsenal FC              v Coventry City FC
"""
    (pack / "2025-26.en.1.json").write_text(played, encoding="utf-8")
    (pack / "2026-27.en.1.txt").write_text(fixtures, encoding="utf-8")
    manifest = {
        "source_id": "openfootball-football-json",
        "upstream_ref": "deadbeef",
        "license": "CC0-1.0",
        "competition": "English Premier League",
        "files": [
            {
                "name": "2025-26.en.1.json",
                "sha256": hashlib.sha256(played.encode()).hexdigest(),
            },
            {
                "name": "2026-27.en.1.txt",
                "season": "2026-27",
                "sha256": hashlib.sha256(fixtures.encode()).hexdigest(),
                "source_match_count": 1,
            },
        ],
    }
    (pack / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return pack


def test_loader_folds_txt_fixtures_beside_json_results_of_the_same_league(
    tmp_path: Path,
) -> None:
    """Fixtures must land in their own league's pack, not a separate source.

    History is scoped to a fixture's own source_id, so a 2026-27 fixture carried
    under a different source would have no history to learn from at all.
    """
    frame = load_openfootball_table(_mixed_pack(tmp_path))

    assert len(frame) == 2
    assert frame["tournament"].eq("English Premier League").all()
    played = frame.loc[frame["date"].eq(pd.Timestamp("2025-08-16"))].iloc[0]
    fixture = frame.loc[frame["date"].eq(pd.Timestamp("2026-08-21"))].iloc[0]
    assert bool(played["is_complete"]) is True
    assert bool(fixture["is_complete"]) is False
    assert pd.isna(fixture["home_score"])
    # A fixture's clock is venue-local with no timezone upstream, so it stays
    # date evidence only — never a false UTC instant.
    assert fixture["kickoff_utc"] == pd.Timestamp("2026-08-21", tz="UTC")
    assert fixture["kickoff_precision"] == "day"
    assert frame["match_id"].is_unique


def test_loader_handles_a_pack_of_fixtures_only(tmp_path: Path) -> None:
    """A pack with no played season yet must load, not crash on a missing column."""
    pack = _mixed_pack(tmp_path)
    (pack / "2025-26.en.1.json").unlink()
    manifest = json.loads((pack / "manifest.json").read_text(encoding="utf-8"))
    manifest["files"] = [e for e in manifest["files"] if e["name"].endswith(".txt")]
    (pack / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    frame = load_openfootball_table(pack)
    assert len(frame) == 1
    assert not frame["is_complete"].any()
    assert "time" not in frame.columns


def test_loader_rejects_a_txt_season_whose_match_count_drifts(tmp_path: Path) -> None:
    """A silently truncated upstream fixture list must fail the build, not shrink the season."""
    pack = _mixed_pack(tmp_path)
    manifest = json.loads((pack / "manifest.json").read_text(encoding="utf-8"))
    for entry in manifest["files"]:
        if entry["name"].endswith(".txt"):
            entry["source_match_count"] = 380
    (pack / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="parsed 1 matches, expected 380"):
        load_openfootball_table(pack)


def test_every_supported_league_declares_its_upstream_title() -> None:
    # The upstream .txt titles are not our canonical labels ('Deutsche
    # Bundesliga' upstream vs 'Bundesliga' in the index), so each must be pinned.
    assert DOMESTIC_TXT_TITLES == {
        "en.1": "English Premier League",
        "es.1": "Spain Primera División",
        "de.1": "Deutsche Bundesliga",
        "it.1": "Italian Serie A",
        "fr.1": "French Ligue 1",
    }


def test_new_season_spellings_resolve_to_the_clubs_existing_identity() -> None:
    """2026-27 spellings must not fragment a club away from its own history.

    openfootball prints Troyes as 'ESTAC Troyes' in the seasons already indexed
    (2015-16..2022-23) but as 'ES Troyes AC' in the 2026-27 fixture list. Left
    unmapped, the promoted side would be a brand-new club to the models, and the
    league table would carry both spellings as separate entries.

    The inputs here are the verbatim upstream spellings: aliases are keyed on the
    raw name, so asserting an already-canonicalized string would pass while the
    real fixture rows stayed fragmented.
    """
    assert canonical_team("ES Troyes AC", "fr.1") == "Troyes"
    assert canonical_team("ESTAC Troyes", "fr.1") == "Troyes"
    # A genuinely new club keeps its own clean identity.
    assert canonical_team("Le Mans FC", "fr.1") == "Le Mans"


def test_promoted_clubs_are_named_like_their_league_peers() -> None:
    # The token rules cannot collapse this legal name, so it would stand as the
    # one five-word entry in a table of short names ('Celta Vigo', 'Real Betis').
    assert canonical_team("Real Racing Club de Santander", "es.1") == "Racing Santander"


def test_upstream_titles_are_translated_to_the_indexed_competition_label() -> None:
    """The .txt title must never become the competition identity.

    Four of the five upstream titles differ from the label the index already
    carries for that league. Emitting the upstream string would file 2026-27
    rows under a competition that does not exist in the historical index, and
    both training (competition-scoped) and standings would silently see two
    leagues instead of one.
    """
    bundesliga = """= Deutsche Bundesliga 2026/27

▪ Matchday 1
  Fri Aug 28 2026
    20:30  FC Bayern München       v Bayer 04 Leverkusen
"""
    frame = parse_domestic_txt(bundesliga, season="2026-27", league_code="de.1")
    assert frame["tournament"].eq("Bundesliga").all()
    assert not frame["tournament"].eq("Deutsche Bundesliga").any()
    assert frame["country"].eq("Germany").all()
    # And the canonical label matches what the historical league pack indexes.
    from golavo_core.ingest.openfootball import LEAGUES

    assert frame.loc[0, "tournament"] == LEAGUES["de.1"][0]
