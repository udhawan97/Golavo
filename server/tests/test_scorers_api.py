"""The competition scorers route over the real bundled index."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from golavo_server import main as server_main
from golavo_server import matches, scorers


@pytest.fixture(autouse=True)
def _fresh_cache():
    # Reset the shared index cache so a sibling test's fixture index cannot bleed
    # into these real-index assertions.
    matches.reset_cache()
    scorers.reset_cache()
    yield
    matches.reset_cache()
    scorers.reset_cache()


def _client() -> TestClient:
    return TestClient(server_main.app)


def test_world_cup_golden_boot_is_leak_safe_and_ranked() -> None:
    response = _client().get(
        "/api/v1/competitions/fifa-world-cup/scorers",
        params={"as_of_utc": "2022-12-01T00:00:00Z", "min_goals": 10},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["competition_id"] == "fifa-world-cup"
    assert body["scope"] == "internationals"
    assert body["matches_counted"] > 0
    # As of before the 2022 final, Klose (16) is the all-time leader; no later
    # tournament's goals can appear.
    leader = body["scorers"][0]
    assert leader["scorer"] == "Miroslav Klose"
    assert leader["goals"] == 16
    assert body["scorers"] == sorted(body["scorers"], key=lambda row: row["rank"])


def test_later_cutoff_can_only_add_goals_never_remove_them() -> None:
    early = _client().get(
        "/api/v1/competitions/fifa-world-cup/scorers",
        params={"as_of_utc": "2022-12-01T00:00:00Z", "min_goals": 10},
    ).json()
    late = _client().get(
        "/api/v1/competitions/fifa-world-cup/scorers",
        params={"as_of_utc": "2026-07-19T00:00:00Z", "min_goals": 10},
    ).json()
    early_klose = next(r["goals"] for r in early["scorers"] if r["scorer"] == "Miroslav Klose")
    late_klose = next(r["goals"] for r in late["scorers"] if r["scorer"] == "Miroslav Klose")
    # A retired player's tally is fixed; a later cutoff never changes it.
    assert early_klose == late_klose == 16
    assert late["matches_counted"] >= early["matches_counted"]


def test_world_cup_shootout_ledger_is_present() -> None:
    body = _client().get(
        "/api/v1/competitions/fifa-world-cup/scorers",
        params={"as_of_utc": "2026-07-19T00:00:00Z"},
    ).json()
    assert body["shootouts_counted"] > 0
    teams = {row["team"]: row for row in body["teams"]}
    # England's historic shootout woe: more losses than wins at the World Cup.
    assert teams["England"]["lost"] >= teams["England"]["won"]


def test_a_club_competition_is_a_typed_unavailable_board_not_an_error() -> None:
    response = _client().get("/api/v1/competitions/england-premier-league/scorers")
    assert response.status_code == 200
    body = response.json()
    assert body["scope"] == "unavailable"
    assert body["scorers"] == []
    assert "international" in body["reason"]


def test_unknown_competition_is_404() -> None:
    response = _client().get("/api/v1/competitions/not-a-real-competition/scorers")
    assert response.status_code == 404
