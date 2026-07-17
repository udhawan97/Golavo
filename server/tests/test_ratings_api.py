"""The Golavo Ratings route over the real bundled index."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from golavo_server import main as server_main
from golavo_server import ratings


@pytest.fixture(autouse=True)
def _fresh_cache() -> None:
    ratings.reset_cache()


def _client() -> TestClient:
    return TestClient(server_main.app)


def test_international_ratings_are_ranked_and_labelled() -> None:
    response = _client().get(
        "/api/v1/ratings/international", params={"as_of_utc": "2026-07-20T00:00:00Z", "top_n": 10}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["scope"] == "internationals"
    assert body["method"].startswith("elo")
    assert "not the FIFA" in body["label"].lower() or "not the fifa" in body["label"].lower()
    assert len(body["teams"]) == 10
    ratings_desc = [team["rating"] for team in body["teams"]]
    assert ratings_desc == sorted(ratings_desc, reverse=True)
    assert [team["rank"] for team in body["teams"]] == list(range(1, 11))
    # Each team carries a checkpoint history for the trend sparkline.
    assert all(len(team["history"]) >= 1 for team in body["teams"])


def test_rewinding_the_cutoff_yields_the_teams_of_that_era() -> None:
    early = _client().get(
        "/api/v1/ratings/international", params={"as_of_utc": "2018-01-01T00:00:00Z", "top_n": 5}
    ).json()
    names = {team["team"] for team in early["teams"]}
    # The pre-2018-World-Cup elite; none of this depends on any later result.
    assert {"Brazil", "Germany", "Spain"} & names
    assert early["data_through_utc"] <= "2018-01-01T00:00:00Z"


def test_a_later_cutoff_never_changes_an_earlier_rating() -> None:
    early = _client().get(
        "/api/v1/ratings/international", params={"as_of_utc": "2018-01-01T00:00:00Z", "top_n": 20}
    ).json()
    late = _client().get(
        "/api/v1/ratings/international", params={"as_of_utc": "2026-07-20T00:00:00Z", "top_n": 20}
    ).json()
    early_brazil = next(t["rating"] for t in early["teams"] if t["team"] == "Brazil")
    # Recompute the same 2018 cutoff after the later request cached a newer one:
    early_again = _client().get(
        "/api/v1/ratings/international", params={"as_of_utc": "2018-01-01T00:00:00Z", "top_n": 20}
    ).json()
    brazil_again = next(t["rating"] for t in early_again["teams"] if t["team"] == "Brazil")
    assert early_brazil == brazil_again
    assert late["data_through_utc"] > early["data_through_utc"]
