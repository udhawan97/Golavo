from __future__ import annotations

import json
from pathlib import Path

from golavo_core.competitions import (
    competition_by_id,
    competition_catalog,
    competition_id_for_source_name,
)
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]


def test_catalog_matches_the_frozen_schema_and_has_unique_identities() -> None:
    catalog = competition_catalog()
    schema = json.loads(
        (ROOT / "docs/contracts/competition_catalog.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(catalog)

    ids = [item["competition_id"] for item in catalog["competitions"]]
    slugs = [item["slug"] for item in catalog["competitions"]]
    era_ids = [
        era["format_era_id"]
        for item in catalog["competitions"]
        for era in item["format_eras"]
    ]
    assert len(ids) == len(set(ids))
    assert len(slugs) == len(set(slugs))
    assert len(era_ids) == len(set(era_ids))


def test_target_scope_covers_domestic_and_mens_uefa_competitions() -> None:
    catalog = competition_catalog()
    assert catalog["scope"] == {
        "team_category": "mens-senior",
        "club_history": "current-plus-five-completed-seasons",
        "cross_era_default": "strict",
    }
    ids = {item["competition_id"] for item in catalog["competitions"]}
    assert {
        "england-premier-league",
        "spain-la-liga",
        "germany-bundesliga",
        "italy-serie-a",
        "france-ligue-1",
        "uefa-champions-league",
        "uefa-europa-league",
        "uefa-conference-league",
        "fifa-world-cup",
        "uefa-euro",
        "uefa-euro-qualification",
        "uefa-nations-league",
        "uefa-world-cup-qualification",
    } == ids


def test_capabilities_never_claim_blocked_features_are_available() -> None:
    catalog = competition_catalog()
    for item in catalog["competitions"]:
        expected_simulation = (
            "available" if item["competition_id"] == "fifa-world-cup" else "blocked"
        )
        assert item["capabilities"]["simulation"]["status"] == expected_simulation
        assert item["capabilities"]["weather_context"]["status"] == "blocked"
        assert item["capabilities"]["weather_context"]["source_ids"] == []
        assert item["capabilities"]["conditions"]["status"] == "partial"
        assert item["capabilities"]["conditions"]["source_ids"] == [
            "geonames",
            "natural-earth",
        ]
    assert catalog["refresh_policy"]["byok_api"] == "blocked"


def test_phase_one_capabilities_match_the_shipped_analytics() -> None:
    catalog = {item["competition_id"]: item for item in competition_catalog()["competitions"]}
    premier = catalog["england-premier-league"]["capabilities"]
    assert premier["report_cards"]["status"] == "available"
    assert premier["strength_trends"]["status"] == "available"
    assert premier["rest_congestion"]["status"] == "available"
    assert premier["schedule_difficulty"]["status"] == "blocked"

    euro = catalog["uefa-euro"]["capabilities"]
    assert euro["report_cards"]["status"] == "available"
    assert euro["strength_trends"]["status"] == "available"
    ucl = catalog["uefa-champions-league"]["capabilities"]
    assert ucl["results"]["status"] == "available"
    assert ucl["fixtures"]["status"] == "partial"
    assert ucl["report_cards"]["status"] == "planned"
    assert ucl["strength_trends"]["status"] == "available"
    assert ucl["rest_congestion"]["status"] == "available"
    assert ucl["schedule_difficulty"]["status"] == "blocked"
    world_cup = catalog["fifa-world-cup"]["capabilities"]
    assert world_cup["simulation"]["status"] == "available"
    assert world_cup["simulation"]["source_ids"] == [
        "martj42-international-results",
        "openfootball-worldcup-json",
    ]
    assert world_cup["research"]["status"] == "partial"
    assert world_cup["research"]["source_ids"] == ["pappalardo-wyscout-events"]
    assert premier["research"]["status"] == "partial"


def test_source_alias_resolution_is_exact_and_does_not_guess_region() -> None:
    assert competition_id_for_source_name("English Premier League") == "england-premier-league"
    assert competition_id_for_source_name("UEFA Nations League") == "uefa-nations-league"
    assert competition_id_for_source_name("FIFA World Cup") == "fifa-world-cup"
    assert competition_id_for_source_name("FIFA World Cup qualification") is None
    assert competition_id_for_source_name("premier league") is None
    assert competition_by_id("missing") is None


def test_catalog_returns_defensive_copies() -> None:
    first = competition_catalog()
    first["competitions"][0]["display_name"] = "mutated"
    assert competition_catalog()["competitions"][0]["display_name"] == "Premier League"
