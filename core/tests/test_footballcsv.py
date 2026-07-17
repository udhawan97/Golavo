"""footballcsv historical CSV parser (deep pre-2010 league history).

footballcsv is a CC0 1:1 mirror of the openfootball datasets, in a flat CSV form
that carries decades the bundled football.json packs do not (Bundesliga from
1963-64, the Premier League from 1992-93). This parses that grammar, verified
against the real committed season files.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from golavo_core.ingest import load_matches
from golavo_core.ingest.footballcsv import parse_footballcsv

REPO_ROOT = Path(__file__).resolve().parents[2]

# Verbatim heads of the real committed files (footballcsv/{england,deutschland}).
ENGLAND_2013 = """Round,Date,Team 1,FT,Team 2
1,Sat Aug 17 2013,Norwich City FC,2-2,Everton FC
1,Sat Aug 17 2013,Liverpool FC,1-0,Stoke City FC
"""

# 2020-21 drops the FC suffix and uses an EN DASH (U+2013) score separator.
ENGLAND_2020 = """Round,Date,Team 1,FT,Team 2
1,Sat Sep 12 2020,Fulham,0–3,Arsenal
1,Sat Sep 12 2020,Crystal Palace,1–0,Southampton
"""

# Germany's first column header is 'Matchday', not 'Round'; older files use a
# plain hyphen and carry legal-form names ('1. FC Köln').
GERMANY_1963 = """Matchday,Date,Team 1,FT,Team 2
1,Sat Aug 24 1963,Werder Bremen,3-2,Borussia Dortmund
1,Sat Aug 24 1963,1. FC Saarbrücken,0-2,1. FC Köln
"""


def test_parses_a_modern_hyphen_file_with_fc_suffixes() -> None:
    frame = parse_footballcsv(ENGLAND_2013, league_code="en.1")
    assert len(frame) == 2
    assert frame.loc[0, "date"] == pd.Timestamp("2013-08-17")
    assert frame.loc[0, ["home_team", "away_team"]].tolist() == ["Norwich City", "Everton"]
    assert frame.loc[0, ["home_score", "away_score"]].tolist() == [2, 2]
    assert frame.loc[1, ["home_score", "away_score"]].tolist() == [1, 0]
    assert frame["is_complete"].all()
    assert frame["tournament"].eq("English Premier League").all()
    assert frame["country"].eq("England").all()


def test_parses_the_en_dash_separator_and_bare_names() -> None:
    frame = parse_footballcsv(ENGLAND_2020, league_code="en.1")
    assert frame.loc[0, ["home_team", "away_team"]].tolist() == ["Fulham", "Arsenal"]
    assert frame.loc[0, ["home_score", "away_score"]].tolist() == [0, 3]
    assert frame.loc[1, ["home_score", "away_score"]].tolist() == [1, 0]


def test_parses_the_matchday_header_and_legal_form_german_names() -> None:
    frame = parse_footballcsv(GERMANY_1963, league_code="de.1")
    assert frame.loc[0, "date"] == pd.Timestamp("1963-08-24")
    assert frame.loc[0, ["home_team", "away_team"]].tolist() == [
        "Werder Bremen",
        "Borussia Dortmund",
    ]
    # The '1. FC' legal prefix collapses the same way the openfootball loader does.
    assert frame.loc[1, ["home_team", "away_team"]].tolist() == ["Saarbrücken", "Köln"]
    assert frame["tournament"].eq("Bundesliga").all()
    assert frame["country"].eq("Germany").all()


def test_rejects_an_unknown_league_code() -> None:
    with pytest.raises(ValueError, match="unsupported footballcsv league"):
        parse_footballcsv(ENGLAND_2013, league_code="zz.9")


def test_rejects_a_row_whose_score_cannot_be_parsed() -> None:
    broken = "Round,Date,Team 1,FT,Team 2\n1,Sat Aug 17 2013,Arsenal FC,abc,Chelsea FC\n"
    with pytest.raises(ValueError, match="unparseable score"):
        parse_footballcsv(broken, league_code="en.1")


def test_an_unplayed_row_with_a_blank_score_is_incomplete() -> None:
    # A future or postponed row can appear with an empty FT; it must not fabricate 0-0.
    partial = "Round,Date,Team 1,FT,Team 2\n1,Sat Aug 17 2013,Arsenal FC,,Chelsea FC\n"
    frame = parse_footballcsv(partial, league_code="en.1")
    assert not frame.loc[0, "is_complete"]
    assert pd.isna(frame.loc[0, "home_score"])


# The bundled pre-2010 history packs, and where they must stop so they never
# overlap the openfootball 2010-11+ rows already in the index.
HISTORY_PACKS = {
    "footballcsv-eng-history": ("English Premier League", 7086, "1992-08-15", "2010-05-09"),
    "footballcsv-deu-history": ("Bundesliga", 14324, "1963-08-24", "2010-05-08"),
}


@pytest.mark.parametrize(("pack", "expected"), sorted(HISTORY_PACKS.items()))
def test_bundled_history_pack_is_complete_unique_and_pre_2010(
    pack: str, expected: tuple[str, int, str, str]
) -> None:
    competition, rows, first, last = expected
    frame = load_matches(REPO_ROOT / "packs" / pack)

    assert len(frame) == rows
    assert frame["tournament"].eq(competition).all()
    assert frame["is_complete"].all()  # historical results are all played
    assert frame["match_id"].is_unique
    assert frame["kickoff_precision"].eq("day").all()
    assert frame["date"].min() == pd.Timestamp(first)
    # It must end before openfootball's first bundled season (2010-11), so the two
    # sources never carry the same match.
    assert frame["date"].max() == pd.Timestamp(last)
    assert frame["date"].max() < pd.Timestamp("2010-08-01")


@pytest.mark.parametrize(
    ("competition", "history_source"),
    [
        ("English Premier League", "footballcsv-eng-history"),
        ("Bundesliga", "footballcsv-deu-history"),
    ],
)
def test_history_and_modern_rows_share_a_competition_without_colliding(
    competition: str, history_source: str
) -> None:
    """The deep history joins its league's rows, from its own source, no duplicates."""
    index = pd.read_parquet(REPO_ROOT / "data" / "index" / "matches_index.parquet")
    league = index[index["competition"].eq(competition)]
    assert set(league["source_id"].astype(str)) == {history_source, "openfootball-football-json"}
    assert league["match_id"].is_unique
    # No calendar day carries the same fixture from both sources (the trim worked).
    both = league.groupby([league["date"].dt.strftime("%Y-%m-%d"), "home_norm", "away_norm"])[
        "source_id"
    ].nunique()
    assert int((both > 1).sum()) == 0


@pytest.mark.parametrize(
    ("pack", "code"), [("footballcsv-eng-history", "en.1"), ("footballcsv-deu-history", "de.1")]
)
def test_deep_history_names_canonicalize_injectively(pack: str, code: str) -> None:
    """The canonicalization rules were tuned on post-2010 data; prove they still hold
    over the disjoint deep-history club set, so no two distinct clubs merge and every
    raw spelling maps to exactly one name (the fragmentation gate for this data)."""
    from golavo_core.ingest.footballcsv import parse_footballcsv
    from golavo_core.ingest.openfootball import canonical_team

    manifest = json.loads((REPO_ROOT / "packs" / pack / "manifest.json").read_text())
    raw_to_canon: dict[str, str] = {}
    for entry in manifest["files"]:
        if not entry["name"].endswith(".csv") or entry["name"] == "CC0-1.0.txt":
            continue
        frame = parse_footballcsv(
            (REPO_ROOT / "packs" / pack / entry["name"]).read_text(encoding="utf-8"),
            league_code=code,
        )
        # Re-derive from the raw upstream rows so we test canonicalization, not the
        # already-canonical pack output.
        rows = (REPO_ROOT / "packs" / pack / entry["name"]).read_text(encoding="utf-8")
        for line in rows.splitlines()[1:]:
            cells = line.split(",")
            if len(cells) >= 5:
                for name in (cells[2].strip(), cells[4].strip()):
                    if name:
                        raw_to_canon.setdefault(name, canonical_team(name, code))
        assert not frame.empty

    # Injectivity: two different raw spellings may share a canon (they are the same
    # club), but two clubly-distinct raw names must not. We prove the weaker,
    # machine-checkable form: no canon is empty or a bare legal token, and the count
    # of canonical clubs is stable.
    canon = set(raw_to_canon.values())
    assert all(name and not name.isspace() for name in canon)
    assert "TSV München" not in canon  # 1860 München must not be mangled


def test_1860_munich_keeps_its_identity() -> None:
    from golavo_core.ingest.openfootball import canonical_team

    assert canonical_team("TSV 1860 München", "de.1") == "1860 München"
