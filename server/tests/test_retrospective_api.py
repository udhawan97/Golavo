from __future__ import annotations

from pathlib import Path

import pytest
from golavo_server import matches
from golavo_server import retrospective as server_retrospective


@pytest.fixture(autouse=True)
def _reset():
    matches.reset_cache()
    server_retrospective.reset_cache()
    yield
    matches.reset_cache()
    server_retrospective.reset_cache()


def test_matches_reset_clears_the_retrospective_cache() -> None:
    """A repointed index must never serve a retrospective from the old frame."""
    server_retrospective._CACHE[("probe",)] = {"stale": True}
    matches.reset_cache()
    assert server_retrospective._CACHE == {}


def test_build_stamps_both_layers_with_one_pack(monkeypatch) -> None:
    """Story and trust must never describe different packs."""
    monkeypatch.setattr(
        server_retrospective,
        "_story",
        lambda frame, progress, is_cancelled: {
            "schema_version": "0.1.0",
            "status": "available",
            "coverage": {"status": "complete", "scored": 1, "pending": 0, "note": "n"},
            "matches": [],
            "biggest_surprises": [],
        },
    )
    monkeypatch.setattr(
        server_retrospective, "_trust", lambda pack_dir: {"competition": "FIFA World Cup"}
    )
    result = server_retrospective.build()
    assert result["provenance"]["index_sha256"]
    assert result["provenance"]["pack"]
    assert result["trust"]["competition"] == "FIFA World Cup"


def test_trust_selects_the_fifa_world_cup_card_not_just_the_first_one(monkeypatch) -> None:
    """evaluate() returns one report card PER COMPETITION; picking the wrong one
    is a plausible bug the schema cannot catch, since trust.competition is typed
    as a plain string, not a const."""
    from golavo_core import evaluation

    cards = [
        {"competition": "UEFA Euro", "models": [{"family": "climatological"}]},
        {
            "competition": "FIFA World Cup",
            "models": [{"family": "climatological"}],
            "marker": "the-one-we-want",
        },
    ]
    monkeypatch.setattr(evaluation, "evaluate", lambda pack_dir: {"report_cards": cards})

    card = server_retrospective._trust(Path("/unused"))

    assert card is not None
    assert card["competition"] == "FIFA World Cup"
    assert card["marker"] == "the-one-we-want"


def test_trust_is_none_when_no_world_cup_card_is_present(monkeypatch) -> None:
    from golavo_core import evaluation

    monkeypatch.setattr(
        evaluation,
        "evaluate",
        lambda pack_dir: {"report_cards": [{"competition": "UEFA Euro", "models": []}]},
    )

    assert server_retrospective._trust(Path("/unused")) is None
