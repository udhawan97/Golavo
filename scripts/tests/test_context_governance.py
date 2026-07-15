from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import build_venue_context, validate_context_pack

ROOT = Path(__file__).resolve().parents[2]


def test_context_pack_is_schema_valid_and_fail_closed() -> None:
    counts = validate_context_pack.validate()
    assert counts["places"] == 1497
    assert counts["venues"] == 16
    assert counts["unresolved"] == 644


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('49°16\'36"N 123°6\'43"W', (49.2766666667, -123.1119444444)),
        ("37.403°N 121.970°W", (37.403, -121.970)),
        ('40°48\'48.7"N 74°4\'27.7"W', (40.8135277778, -74.0743611111)),
    ],
)
def test_source_coordinate_parser(text: str, expected: tuple[float, float]) -> None:
    actual = build_venue_context._coordinate(text)
    assert actual == pytest.approx(expected)


def test_conflicting_wikidata_link_is_not_merged() -> None:
    assignments = json.loads(
        (ROOT / "data/context/venue_assignments.json").read_text(encoding="utf-8")
    )["assignments"]
    entities = {
        item["entity_id"]: item
        for item in json.loads(
            (ROOT / "data/context/venue_entities.json").read_text(encoding="utf-8")
        )["entities"]
    }
    conflict = next(item for item in assignments if item["wikidata_link_status"] == "conflicting")
    identifiers = entities[conflict["venue_entity_id"]]["identifiers"]
    assert conflict["source_city"] == "Los Angeles (Inglewood)"
    assert not any(item["source_id"] == "wikidata" for item in identifiers)


def test_no_alias_or_collision_uses_a_population_tiebreak() -> None:
    metadata = json.loads(
        (ROOT / "data/enrichment/places.meta.json").read_text(encoding="utf-8")
    )
    assert metadata["ambiguous_pairs"] == 82
    assert metadata["alias_pending_pairs"] == 175
    assert "population" not in metadata["matching"].casefold()
