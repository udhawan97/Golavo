"""The consent-gated weather refresh orchestration (resolve coords -> fetch -> store).

No live network: a fake transport supplies recorded bytes. Exercises the honest
failure modes — an unknown match, an unresolved venue, a passed kickoff.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from golavo_server import weather

_OPEN_METEO = (
    '{"hourly":{"time":["2026-08-16T19:00"],"temperature_2m":[26.4],'
    '"precipitation":[0.2],"precipitation_probability":[20],'
    '"wind_speed_10m":[9.5],"weather_code":[61]}}'
)


def _match(**over):
    base = {
        "match_id": "m_x",
        "kickoff_utc": "2026-08-16T19:00:00Z",
        "city": "Madrid",
        "country": "Spain",
    }
    return {"match": {**base, **over}}


@pytest.fixture
def wired(tmp_path, monkeypatch):
    from golavo_server import conditions, matches, runtime

    monkeypatch.setattr(runtime, "weather_dir", lambda: tmp_path)
    monkeypatch.setattr(conditions, "resolve_coords", lambda city, country: (40.4, -3.7))
    monkeypatch.setattr(matches, "get_match", lambda mid, **_: _match(match_id=mid))
    return tmp_path


def test_refresh_fetches_stores_and_returns_a_forecast_card(wired, monkeypatch) -> None:
    ctx = weather.refresh(
        "m_x",
        now_utc=datetime(2026, 8, 1, 9, tzinfo=UTC),
        transport=lambda _url: _OPEN_METEO,
    )
    assert ctx["status"] == "forecast"
    assert ctx["temperature_2m_c"] == 26.4
    assert ctx["source_id"] == "open-meteo"

    # It was persisted: a fresh conditions read now shows the forecast.
    from golavo_server import conditions

    assert conditions.weather_context_for("m_x")["status"] == "forecast"


def test_refresh_of_an_unknown_match_is_a_typed_404(wired, monkeypatch) -> None:
    from golavo_server import matches

    monkeypatch.setattr(matches, "get_match", lambda mid, **_: None)
    with pytest.raises(weather.WeatherRefreshError) as exc:
        weather.refresh("m_missing", now_utc=datetime(2026, 8, 1, tzinfo=UTC))
    assert exc.value.status == 404


def test_refresh_without_resolved_coordinates_fails_closed(wired, monkeypatch) -> None:
    from golavo_server import conditions

    monkeypatch.setattr(conditions, "resolve_coords", lambda city, country: None)
    with pytest.raises(weather.WeatherRefreshError) as exc:
        weather.refresh(
            "m_x", now_utc=datetime(2026, 8, 1, tzinfo=UTC), transport=lambda _u: _OPEN_METEO
        )
    assert exc.value.status == 422
    assert exc.value.reason_code == "location_unresolved"


def test_refresh_after_kickoff_is_refused(wired) -> None:
    with pytest.raises(weather.WeatherRefreshError) as exc:
        weather.refresh(
            "m_x",
            now_utc=datetime(2026, 8, 17, tzinfo=UTC),  # after the 08-16 kickoff
            transport=lambda _u: _OPEN_METEO,
        )
    assert exc.value.status == 422
    assert exc.value.reason_code == "kickoff_passed"
