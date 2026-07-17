"""The 2026-27 domestic unlock: the catalog's claim must match the bundled bytes.

``competitions.py`` is deliberately data-only, so its capability statuses are
static declarations. That is only honest while something proves the declaration
against the shipped index — otherwise 'available' is a promise nobody checks.
These tests are that proof: whatever the catalog claims about a domestic
league's simulation, the bundled index must actually be able to back.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from golavo_core.competitions import competition_catalog
from golavo_core.season_outlook import certify_schedule
from golavo_core.standings import football_season, league_rule

REPO_ROOT = Path(__file__).resolve().parents[2]
SEASON = "2026-27"

# competition_id -> (indexed competition label, published fixture count)
DOMESTIC = {
    "england-premier-league": ("English Premier League", 380),
    "germany-bundesliga": ("Bundesliga", 306),
    "spain-la-liga": ("La Liga", 380),
    "italy-serie-a": ("Serie A", 380),
    "france-ligue-1": ("Ligue 1", 306),
}


@pytest.fixture(scope="module")
def index() -> pd.DataFrame:
    frame = pd.read_parquet(REPO_ROOT / "data" / "index" / "matches_index.parquet")
    frame = frame.copy()
    frame["season"] = frame["date"].map(football_season)
    return frame


@pytest.mark.parametrize(("competition_id", "expected"), sorted(DOMESTIC.items()))
def test_bundled_index_certifies_the_2026_27_schedule(
    index: pd.DataFrame, competition_id: str, expected: tuple[str, int]
) -> None:
    label, published = expected
    rule = league_rule(competition_id)
    season = index[index["competition"].eq(label) & index["season"].eq(SEASON)]

    certificate = certify_schedule(
        season, expected_teams=rule.expected_teams, as_of_utc="2026-08-01T00:00:00Z"
    )

    assert certificate["observed_matches"] == published
    assert certificate["observed_teams"] == rule.expected_teams
    assert certificate["duplicate_ordered_pairs"] == 0
    assert certificate["self_fixtures"] == 0
    assert certificate["future_completed_results"] == 0
    assert certificate["complete_fixture_list"] is True


@pytest.mark.parametrize("competition_id", sorted(DOMESTIC))
def test_catalog_simulation_claim_is_backed_by_the_certificate(
    index: pd.DataFrame, competition_id: str
) -> None:
    catalog = {item["competition_id"]: item for item in competition_catalog()["competitions"]}
    capability = catalog[competition_id]["capabilities"]["simulation"]
    label, _ = DOMESTIC[competition_id]
    rule = league_rule(competition_id)
    season = index[index["competition"].eq(label) & index["season"].eq(SEASON)]
    certified = certify_schedule(
        season, expected_teams=rule.expected_teams, as_of_utc="2026-08-01T00:00:00Z"
    )["complete_fixture_list"]

    # The catalog may only promise a seeded outlook where the schedule certifies.
    assert (capability["status"] == "available") is certified
    assert "openfootball-england" in str(capability["source_ids"]) or certified


@pytest.mark.parametrize("competition_id", sorted(DOMESTIC))
def test_fixture_rows_are_never_training_rows(
    index: pd.DataFrame, competition_id: str
) -> None:
    """A scheduled fixture carries no result, so it can never train a forecast."""
    label, _ = DOMESTIC[competition_id]
    season = index[index["competition"].eq(label) & index["season"].eq(SEASON)]
    assert not season["is_complete"].any()
    assert not season["training_eligible"].any()
    assert season["training_source_id"].isna().all()
    assert season["result_source_id"].isna().all()


def test_every_row_has_its_own_upstream_fixture_key(index: pd.DataFrame) -> None:
    """The key identifies one fixture, and callers rely on that.

    server.main._missing_fixture_match resolves a correction proposal by taking
    the first row matching this key. A key shared by a whole matchday would let a
    'missing fixture' correction validate against an arbitrary other match.
    """
    keys = index["upstream_fixture_key"].astype("string")
    duplicated = keys[keys.duplicated(keep=False)]
    assert duplicated.empty, sorted(duplicated.unique())[:5]


@pytest.mark.parametrize("competition_id", sorted(DOMESTIC))
def test_fixture_rows_credit_the_repo_that_published_them(
    index: pd.DataFrame, competition_id: str
) -> None:
    """Fixtures came from the .txt repos, not football.json — the rows must say so."""
    label, _ = DOMESTIC[competition_id]
    season = index[index["competition"].eq(label) & index["season"].eq(SEASON)]
    identity = set(season["identity_source_id"].dropna().astype(str))
    assert identity and identity != {"openfootball-football-json"}
    assert all(source.startswith("openfootball-") for source in identity)
    # Training truth still belongs to the pack's own source.
    assert set(season["source_id"].astype(str)) == {"openfootball-football-json"}
