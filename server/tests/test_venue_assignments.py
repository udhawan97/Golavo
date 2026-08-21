"""Resolving a match to a reviewed venue, for club fixtures as well as the World Cup.

The registry originally keyed every assignment on (city, country, competition).
That works for a tournament, whose pinned fixture rows carry a host city — and
resolves nothing at all for a club fixture, because not one of the 51,005 club
rows in the index has a city. A club assignment is therefore keyed on the home
team, which is the field a club fixture actually has.
"""

from __future__ import annotations

from typing import Any

import pytest
from golavo_server import context_registry


def _entity(entity_id: str, label: str, capacity: int) -> dict[str, Any]:
    def claim(field: str, value: Any) -> dict[str, Any]:
        return {
            "claim_id": f"ctxc_{entity_id}_{field}",
            "field": field,
            "value": value,
            "source_refs": [
                {
                    "source_id": "openfootball-clubs",
                    "source_record_id": label,
                    "source_revision": "deadbeef",
                    "snapshot_sha256": "0" * 64,
                    "retrieved_at_utc": "2026-07-29T00:00:00Z",
                    "field": field,
                }
            ],
        }

    return {
        "entity_id": entity_id,
        "entity_kind": "venue",
        "canonical_label": label,
        "claims": [
            claim("canonical_label", label),
            # Every real venue entity records the city its pinned club file
            # states, which is the only place a club fixture's city comes from.
            claim("source_city", "London"),
            claim("latitude", 51.5),
            claim("longitude", -0.1),
            claim("capacity", capacity),
        ],
    }


def _club_assignment(team: str, entity_id: str) -> dict[str, Any]:
    return {
        "source_id": "openfootball-clubs",
        "source_revision": "deadbeef",
        "match_home_team": team,
        "match_city": "London",
        "match_country": "England",
        "competition": "English Premier League",
        "valid_from": "2026-08-01",
        "valid_to": "2027-06-30",
        "allowed_match_venue_source_ids": ["openfootball-football-json"],
        "venue_entity_id": entity_id,
        "source_record_id": f"club:{team}",
        "wikidata_link_status": "accepted",
        "wikidata_candidate_qid": "Q1",
        "conflict_reason": None,
    }


@pytest.fixture(autouse=True)
def _registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        context_registry,
        "_CACHE",
        {
            "manifest": {"sources": [], "files": [], "context_pack_version": "test"},
            "venues": {"venue_a": _entity("venue_a", "Emirates Stadium", 60361)},
            "assignments": [_club_assignment("Arsenal", "venue_a")],
        },
        raising=False,
    )
    yield
    context_registry.reset_cache()


def _row(**overrides: Any) -> dict[str, Any]:
    row = {
        "home_team": "Arsenal",
        "away_team": "Chelsea",
        "city": None,
        "country": "England",
        "competition": "English Premier League",
        "source_id": "openfootball-football-json",
        "date": "2026-08-21",
    }
    row.update(overrides)
    return row


def test_a_club_fixture_resolves_on_its_home_team() -> None:
    venue = context_registry.venue_for_match(_row())

    assert venue["status"] == "available"
    assert venue["name"] == "Emirates Stadium"
    assert venue["capacity"] == 60361
    assert venue["identity_link_status"] == "accepted"
    assert "canonical_label" in venue["provenance"]


def test_a_club_assignment_does_not_need_the_row_to_carry_a_city() -> None:
    """No club row in the index has one, so requiring it would resolve nothing."""
    assert context_registry.venue_for_match(_row(city=None))["status"] == "available"


def test_the_away_side_never_borrows_the_home_ground() -> None:
    venue = context_registry.venue_for_match(_row(home_team="Chelsea", away_team="Arsenal"))
    assert venue["status"] == "unknown"
    assert venue["reason"] == "no-reviewed-stadium-assignment"


def test_a_fixture_outside_the_assignment_window_does_not_resolve() -> None:
    """Grounds move. An assignment is pinned to the season it was verified for."""
    assert context_registry.venue_for_match(_row(date="2019-03-01"))["status"] == "unknown"


def test_a_competition_the_assignment_does_not_cover_does_not_resolve() -> None:
    venue = context_registry.venue_for_match(_row(competition="UEFA Champions League"))
    assert venue["status"] == "unknown"


def test_a_match_source_outside_the_allowlist_does_not_resolve() -> None:
    venue = context_registry.venue_for_match(_row(source_id="overlay-odbl"))
    assert venue["status"] == "unknown"


def _place_entity(entity_id: str, city: str) -> dict[str, Any]:
    """A club home-city entity: it states a city and no ground at all."""

    def claim(field: str, value: Any) -> dict[str, Any]:
        return {
            "claim_id": f"ctxc_{entity_id}_{field}",
            "field": field,
            "value": value,
            "source_refs": [
                {
                    "source_id": "openfootball-clubs",
                    "source_record_id": city,
                    "source_revision": "deadbeef",
                    "snapshot_sha256": "0" * 64,
                    "retrieved_at_utc": "2026-07-29T00:00:00Z",
                    "field": "city",
                }
            ],
        }

    return {
        "entity_id": entity_id,
        "entity_kind": "place",
        "canonical_label": city,
        "claims": [claim("canonical_label", city), claim("source_city", city)],
    }


def test_the_reviewed_home_city_answers_for_a_club_row_that_has_none() -> None:
    """Every club row in the index lacks a city; the assignment is where one lives."""
    reviewed = context_registry.reviewed_home_city(_row())

    assert reviewed is not None
    assert reviewed["city"] == "London"
    assert reviewed["country"] == "England"
    assert reviewed["source_refs"][0]["source_id"] == "openfootball-clubs"


def test_no_reviewed_home_city_outside_the_assignment_window() -> None:
    """Clubs move. A city is claimed only for the season it was read for."""
    assert context_registry.reviewed_home_city(_row(date="2019-03-01")) is None


def test_the_away_side_never_borrows_the_home_city() -> None:
    assert context_registry.reviewed_home_city(_row(home_team="Chelsea")) is None


def test_a_city_only_assignment_yields_a_city_but_never_a_stadium(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La Liga and Serie A have a pinned home city and no pinned ground at all.

    Reporting that city as a stadium would invent the very fact the cross-check
    exists to withhold, so the venue must stay unknown while the city resolves.
    """
    monkeypatch.setattr(
        context_registry,
        "_CACHE",
        {
            "manifest": {"sources": [], "files": [], "context_pack_version": "test"},
            "venues": {"place_a": _place_entity("place_a", "Milano")},
            "assignments": [
                {
                    **_club_assignment("Inter", "place_a"),
                    "match_city": "Milano",
                    "match_country": "Italy",
                    "competition": "Serie A",
                    "wikidata_link_status": "unknown",
                    "wikidata_candidate_qid": None,
                }
            ],
        },
        raising=False,
    )
    row = _row(home_team="Inter", country="Italy", competition="Serie A")

    venue = context_registry.venue_for_match(row)
    assert venue["status"] == "unknown"
    assert venue["reason"] == "no-reviewed-stadium-assignment"
    assert venue["name"] is None

    reviewed = context_registry.reviewed_home_city(row)
    assert reviewed is not None
    assert reviewed["city"] == "Milano"
