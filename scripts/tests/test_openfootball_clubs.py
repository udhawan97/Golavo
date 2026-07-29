"""The openfootball/clubs grammar, which is looser than any other pinned source.

Four properties are load-bearing and pinned here, all verified against the real
files:

* the ground is optional and most clubs have none — England prints one for 89 of
  203 clubs, Spain and Italy for none at all. A club without one must be skipped,
  not guessed at;
* fields are positional but ragged: ``name, founded, @ ground, city`` in England,
  ``name, city`` in Spain, so the ground can only be found by its ``@`` marker;
* a club's own line is flush left; alias lines (``|``), address lines and reserve
  teams (``ii)``) are indented or prefixed and are not clubs;
* ``#`` and ``##`` start comments that can carry commas, so they must be stripped
  before the line is split.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.openfootball_clubs import parse_clubs_txt  # noqa: E402

ENGLAND = """====================================
=  England


#  note: see wal.txt for teams from wales


Arsenal FC, 1886, @ Emirates Stadium, London (Highbury)   ## Greater London
  | Arsenal | FC Arsenal
  | Arsenal Football Club
Chelsea FC, 1905, @ Stamford Bridge, London (Fulham)    ## Greater London
  | Chelsea | FC Chelsea
Manchester United FC, 1878, @ Old Trafford, Manchester
ii) Manchester United II
  | Man Utd II
Reading FC, 1871, Reading
"""


def test_a_clubs_ground_and_city_are_read_from_its_own_line() -> None:
    clubs = parse_clubs_txt(ENGLAND, league_code="en.1")

    arsenal = next(club for club in clubs if club.name == "Arsenal FC")
    assert arsenal.ground == "Emirates Stadium"
    assert arsenal.city == "London"
    assert arsenal.team == "Arsenal"  # canonical, as the index carries it


def test_a_comment_never_becomes_a_field() -> None:
    """'## Greater London' would otherwise be read as a fourth positional field."""
    clubs = parse_clubs_txt(ENGLAND, league_code="en.1")
    chelsea = next(club for club in clubs if club.name == "Chelsea FC")
    assert chelsea.city == "London"
    assert "Greater London" not in (chelsea.city or "")


def test_a_district_qualifier_is_not_part_of_the_city() -> None:
    clubs = parse_clubs_txt(ENGLAND, league_code="en.1")
    chelsea = next(club for club in clubs if club.name == "Chelsea FC")
    assert chelsea.city == "London"


def test_a_club_with_no_ground_is_skipped_rather_than_guessed() -> None:
    clubs = parse_clubs_txt(ENGLAND, league_code="en.1")
    assert "Reading FC" not in {club.name for club in clubs}


def test_alias_address_and_reserve_lines_are_not_clubs() -> None:
    clubs = parse_clubs_txt(ENGLAND, league_code="en.1")
    names = {club.name for club in clubs}
    assert names == {"Arsenal FC", "Chelsea FC", "Manchester United FC"}


def test_the_german_grammar_reads_the_same_way() -> None:
    german = """============================================
= Germany • Deutschland


== Bayern ==

Bayern München, 1900,    @ Allianz Arena,   München
  | Bayern | Bayern Mün.
 Säbener Straße 51-57 // 81547 München
ii) Bayern München II

TSV 1860 München, 1860, München
"""
    clubs = parse_clubs_txt(german, league_code="de.1")
    assert [(club.team, club.ground, club.city) for club in clubs] == [
        ("Bayern München", "Allianz Arena", "München")
    ]


def test_a_french_region_suffix_is_stripped_from_the_city() -> None:
    french = """=  France

Paris Saint-Germain, 1970, @ Parc des Princes,   Paris › Île-de-France
Lille OSC,  1944,  @ Stade Pierre-Mauroy,   Lille      ## Nord > Nord-Pas-de-Calais
"""
    clubs = parse_clubs_txt(french, league_code="fr.1")
    assert [(club.ground, club.city) for club in clubs] == [
        ("Parc des Princes", "Paris"),
        ("Stade Pierre-Mauroy", "Lille"),
    ]
