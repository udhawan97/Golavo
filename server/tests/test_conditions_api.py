from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from golavo_server import conditions, main, matches
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]


def _row(
    match_id: str,
    kickoff: str,
    home: str,
    away: str,
    city: str | None,
    country: str | None,
    *,
    precision: str = "day",
    complete: bool = True,
    source_kind: str = "international",
) -> dict:
    day = kickoff[:10]
    return {
        "match_id": match_id,
        "date": day,
        "kickoff_utc": kickoff,
        "kickoff_precision": precision,
        "home_team": home,
        "away_team": away,
        "home_norm": home.casefold(),
        "away_norm": away.casefold(),
        "home_score": 1 if complete else None,
        "away_score": 0 if complete else None,
        "is_complete": complete,
        "tournament": "Friendly",
        "competition": "Friendly",
        "city": city,
        "country": country,
        "neutral": False,
        "source_id": "martj42-international-results",
        "source_kind": source_kind,
    }


ROWS = [
    _row(
        "m_bra_prev",
        "2024-05-20T00:00:00Z",
        "Brazil",
        "Chile",
        "London",
        "England",
        precision="exact",
    ),
    _row(
        "m_arg_prev",
        "2024-05-25T00:00:00Z",
        "Spain",
        "Argentina",
        "Madrid",
        "Spain",
        precision="exact",
    ),
    _row(
        "m_target",
        "2024-06-01T18:00:00Z",
        "Brazil",
        "Argentina",
        "Paris",
        "France",
        precision="exact",
    ),
    {
        **_row(
            "m_wc_venue",
            "2026-06-12T19:00:00Z",
            "Example One",
            "Example Two",
            "Inglewood",
            "United States",
            precision="exact",
            complete=False,
        ),
        "tournament": "FIFA World Cup",
        "competition": "FIFA World Cup",
    },
]


def _place(city: str, country: str, lat: float, lon: float, timezone: str) -> dict:
    entity_id = f"place_{city.casefold().encode().hex()[:16]:0<16}"
    return {
        "city": city,
        "country": country,
        "source_id": "geonames",
        "entity_id": entity_id,
        "resolution_status": "resolved",
        "source_revision": "2026-01-01",
        "snapshot_sha256": "0" * 64,
        "geoname_id": 1,
        "name": city,
        "latitude": lat,
        "longitude": lon,
        "country_code": "XX",
        "elevation_m": 10,
        "elevation_source": "dem",
        "timezone": timezone,
        "modified": "2026-01-01",
    }


def _write_index(path: Path, rows: list[dict]) -> None:
    frame = pd.DataFrame(rows)
    frame["date"] = pd.to_datetime(frame["date"])
    frame["kickoff_utc"] = pd.to_datetime(frame["kickoff_utc"], utc=True)
    frame["home_score"] = pd.array(frame["home_score"], dtype="Int16")
    frame["away_score"] = pd.array(frame["away_score"], dtype="Int16")
    frame["is_complete"] = frame["is_complete"].astype(bool)
    frame["neutral"] = pd.array(frame["neutral"], dtype="boolean")
    for column in (
        "match_id",
        "kickoff_precision",
        "home_team",
        "away_team",
        "home_norm",
        "away_norm",
        "tournament",
        "competition",
        "city",
        "country",
        "source_id",
        "source_kind",
    ):
        frame[column] = frame[column].astype("string")
    frame.to_parquet(path, index=False)


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    index_path = tmp_path / "matches.parquet"
    _write_index(index_path, ROWS)
    places_path = tmp_path / "places.json"
    places_path.write_text(
        json.dumps(
            {
                "england|london": _place("London", "England", 51.5074, -0.1278, "Europe/London"),
                "spain|madrid": _place("Madrid", "Spain", 40.4168, -3.7038, "Europe/Madrid"),
                "france|paris": _place("Paris", "France", 48.8566, 2.3522, "Europe/Paris"),
            }
        ),
        encoding="utf-8",
    )
    world_path = tmp_path / "world.geojson"
    world_path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "source_id": "natural-earth",
                "version": "5.1.1",
                "attribution": "Made with Natural Earth.",
                "features": [],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(matches, "INDEX_PATH", index_path)
    monkeypatch.setattr(conditions, "PLACES_PATH", places_path)
    monkeypatch.setattr(conditions, "WORLD_PATH", world_path)
    matches.reset_cache()
    conditions.reset_cache()
    yield TestClient(main.app)
    matches.reset_cache()
    conditions.reset_cache()


def test_conditions_contract_rest_travel_and_local_time(client: TestClient) -> None:
    response = client.get("/api/v1/matches/m_target/conditions")
    assert response.status_code == 200
    body = response.json()
    schema = json.loads(
        (ROOT / "docs/contracts/conditions_snapshot.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(body)
    assert body["label"] == "Context, not a model input."
    local = body["match"]["local_kickoff"]
    assert local["status"] == "available"
    assert local["reason"] is None
    assert local["value"] == "2024-06-01T20:00:00+02:00"
    assert local["timezone"] == "Europe/Paris"
    assert local["utc_offset_minutes"] == 120
    assert local["tzdb_fingerprint"].startswith(("tzif-sha256:", "tzdata-package:"))
    assert local["derivation"]["algorithm_id"] == "iana-local-kickoff"
    assert body["match"]["venue"]["status"] == "unknown"
    assert [team["rest"]["days"] for team in body["teams"]] == [12, 7]
    assert [team["kickoff_gap"]["precision"] for team in body["teams"]] == ["exact", "exact"]
    assert all(team["travel"]["distance_km"] > 0 for team in body["teams"])
    assert body["travel_map"]["status"] == "available"
    assert len(body["travel_map"]["routes"]) == 2
    assert body["weather_context"] == {
        "status": "blocked",
        "reason_code": "no_leakage_safe_historical_forecast_source",
        "reason": (
            "Weather is context-only and unavailable until a licensed source preserves "
            "the forecast issued before kickoff. Observed weather is not substituted."
        ),
        "model_input": False,
        "source_id": None,
    }
    assert {source["source_id"] for source in body["sources"]} == {
        "geonames",
        "natural-earth",
        "openfootball-worldcup-json",
        "wikidata",
    }


def test_conditions_ignore_future_rows(client: TestClient) -> None:
    baseline = client.get("/api/v1/matches/m_target/conditions").json()
    frame = matches._load_index().copy()
    future = pd.DataFrame(
        [
            _row(
                "m_future",
                "2030-01-01T12:00:00Z",
                "Brazil",
                "Argentina",
                "Tokyo",
                "Japan",
                precision="exact",
            )
        ]
    )
    future["date"] = pd.to_datetime(future["date"])
    future["kickoff_utc"] = pd.to_datetime(future["kickoff_utc"], utc=True)
    combined = pd.concat([frame, future], ignore_index=True)
    assert (
        conditions.conditions_snapshot(
            "m_target", combined, index_fingerprint=matches.index_fingerprint()
        )
        == baseline
    )


def test_day_precision_and_missing_location_stay_unknown(client: TestClient) -> None:
    frame = matches._load_index().copy()
    frame.loc[frame["match_id"] == "m_target", "kickoff_precision"] = "day"
    body = conditions.conditions_snapshot(
        "m_target", frame, index_fingerprint=matches.index_fingerprint()
    )
    assert body is not None
    assert body["match"]["local_kickoff"]["status"] == "unknown"
    assert body["match"]["local_kickoff"]["reason"] == "kickoff-is-day-only"
    assert body["teams"][0]["rest"]["status"] == "unknown"
    assert body["teams"][0]["kickoff_gap"]["precision"] == "calendar-day"
    assert body["teams"][0]["kickoff_gap"]["calendar_gap_days"] == 12


def test_conditions_and_world_fail_honestly(client: TestClient) -> None:
    assert client.get("/api/v1/matches/does-not-exist/conditions").status_code == 404
    world = client.get("/api/v1/maps/world")
    assert world.status_code == 200
    assert world.json()["attribution"] == "Made with Natural Earth."


def test_reviewed_world_cup_venue_and_conflicting_qid_fail_closed(
    client: TestClient,
) -> None:
    body = client.get("/api/v1/matches/m_wc_venue/conditions").json()
    venue = body["match"]["venue"]
    assert venue["status"] == "available"
    assert venue["name"] == "SoFi Stadium"
    assert venue["identity_link_status"] == "conflicting"
    assert "250 metres" in venue["identity_conflict_reason"]
    assert venue["provenance"]["canonical_label"]["source_refs"][0]["source_id"] == (
        "openfootball-worldcup-json"
    )
    assert all(
        ref["source_id"] != "wikidata"
        for item in venue["provenance"].values()
        for ref in item["source_refs"]
    )


def test_context_capability_and_derived_provenance(client: TestClient) -> None:
    capability = client.get("/api/v1/context/capabilities")
    assert capability.status_code == 200
    assert capability.json()["display_only"] is True
    assert capability.json()["model_input"] is False
    body = client.get("/api/v1/matches/m_target/conditions").json()
    location = body["match"]["location"]
    assert {"latitude", "longitude", "elevation_m", "timezone"}.issubset(
        location["provenance"]
    )
    for team in body["teams"]:
        assert team["kickoff_gap"]["derivation"]["input_claim_ids"]
        assert team["travel"]["derivation"]["algorithm_id"] == "great-circle-haversine"
        assert team["travel"]["derivation"]["input_claim_ids"]
