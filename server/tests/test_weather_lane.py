"""The per-user Open-Meteo weather lane: fetch, store, and the pre-kickoff gate.

No live network runs here (or in CI): the fetch transport is injected, so the
parser and every guard are exercised against recorded bytes. The real keyless
call runs only on a user's own machine, behind consent.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from golavo_server import weather_source, weather_store
from jsonschema import Draft202012Validator, FormatChecker

_SCHEMA = json.loads(
    (Path(__file__).resolve().parents[2] / "docs/contracts/conditions_snapshot.schema.json")
    .read_text(encoding="utf-8")
)
_WEATHER_SCHEMA = {**_SCHEMA["$defs"]["weather"], "$defs": _SCHEMA["$defs"]}


def _validate_weather(weather_context: dict) -> None:
    Draft202012Validator(_WEATHER_SCHEMA, format_checker=FormatChecker()).validate(weather_context)

# A trimmed, real-shaped Open-Meteo /v1/forecast response (hourly arrays).
_OPEN_METEO = json.dumps(
    {
        "latitude": 40.4,
        "longitude": -3.7,
        "generationtime_ms": 0.8,
        "utc_offset_seconds": 0,
        "timezone": "GMT",
        "hourly_units": {
            "temperature_2m": "°C",
            "precipitation": "mm",
            "precipitation_probability": "%",
            "wind_speed_10m": "km/h",
            "weather_code": "wmo code",
        },
        "hourly": {
            "time": ["2026-08-16T18:00", "2026-08-16T19:00", "2026-08-16T20:00"],
            "temperature_2m": [28.1, 26.4, 24.0],
            "precipitation": [0.0, 0.2, 1.1],
            "precipitation_probability": [5, 20, 55],
            "wind_speed_10m": [11.0, 9.5, 8.0],
            "weather_code": [1, 61, 63],
        },
    }
)


def _transport(_url: str) -> str:
    return _OPEN_METEO


def test_fetch_picks_the_hour_nearest_kickoff_and_labels_context_only() -> None:
    reading = weather_source.fetch_forecast(
        40.4,
        -3.7,
        kickoff_utc="2026-08-16T19:00:00Z",
        fetched_at_utc="2026-08-01T09:00:00Z",
        transport=_transport,
    )
    assert reading["provider"] == "open-meteo"
    assert reading["model_input"] is False
    # 19:00 kickoff -> the 19:00 hourly slot.
    assert reading["temperature_2m_c"] == 26.4
    assert reading["precipitation_mm"] == 0.2
    assert reading["precipitation_probability_pct"] == 20
    assert reading["wind_speed_10m_kmh"] == 9.5
    assert reading["weather_code"] == 61
    assert reading["fetched_at_utc"] == "2026-08-01T09:00:00Z"
    assert reading["kickoff_utc"] == "2026-08-16T19:00:00Z"
    assert "open-meteo.com" in reading["attribution_url"]


def test_fetch_builds_a_keyless_allowlisted_url() -> None:
    seen: dict[str, str] = {}

    def capture(url: str) -> str:
        seen["url"] = url
        return _OPEN_METEO

    weather_source.fetch_forecast(
        40.4, -3.7, kickoff_utc="2026-08-16T19:00:00Z",
        fetched_at_utc="2026-08-01T09:00:00Z", transport=capture,
    )
    assert seen["url"].startswith("https://api.open-meteo.com/v1/forecast?")
    assert "apikey" not in seen["url"].lower() and "key=" not in seen["url"].lower()
    assert "latitude=40.4" in seen["url"] and "longitude=-3.7" in seen["url"]


def test_a_malformed_response_fails_closed() -> None:
    with pytest.raises(weather_source.WeatherError):
        weather_source.fetch_forecast(
            40.4, -3.7, kickoff_utc="2026-08-16T19:00:00Z",
            fetched_at_utc="2026-08-01T09:00:00Z", transport=lambda _u: "{not json",
        )


def test_kickoff_outside_the_forecast_window_fails_closed() -> None:
    # Open-Meteo returns ~16 days; a kickoff with no matching hour is not guessed.
    with pytest.raises(weather_source.WeatherError):
        weather_source.fetch_forecast(
            40.4, -3.7, kickoff_utc="2027-01-01T19:00:00Z",
            fetched_at_utc="2026-08-01T09:00:00Z", transport=_transport,
        )


def test_the_default_transport_refuses_a_non_allowlisted_host() -> None:
    # The real transport must only ever reach api.open-meteo.com.
    with pytest.raises(weather_source.WeatherError):
        weather_source._http_get("https://evil.example.com/v1/forecast?x=1")


def _seed(tmp_path, monkeypatch, *, fetched_at: str, kickoff: str = "2026-08-16T19:00:00Z"):
    from golavo_server import conditions, runtime

    reading = weather_source.fetch_forecast(
        40.4, -3.7, kickoff_utc=kickoff, fetched_at_utc=fetched_at, transport=_transport,
    )
    weather_store.save_reading(tmp_path, "m_x", reading)
    monkeypatch.setattr(runtime, "weather_dir", lambda: tmp_path)
    return conditions.weather_context_for("m_x")


def test_weather_context_is_blocked_without_a_capture(tmp_path, monkeypatch) -> None:
    from golavo_server import conditions, runtime

    monkeypatch.setattr(runtime, "weather_dir", lambda: tmp_path)
    ctx = conditions.weather_context_for("m_none")
    assert ctx["status"] == "blocked"
    assert ctx["reason_code"] == "no_leakage_safe_historical_forecast_source"
    assert ctx["model_input"] is False


def test_a_pre_kickoff_capture_becomes_a_forecast_card(tmp_path, monkeypatch) -> None:
    ctx = _seed(tmp_path, monkeypatch, fetched_at="2026-08-01T09:00:00Z")
    assert ctx["status"] == "forecast"
    assert ctx["source_id"] == "open-meteo"
    assert ctx["temperature_2m_c"] == 26.4
    assert ctx["model_input"] is False
    assert "open-meteo.com" in ctx["attribution_url"]
    # Both variants must satisfy the additive conditions-snapshot weather schema.
    _validate_weather(ctx)


def test_both_weather_variants_satisfy_the_contract(tmp_path, monkeypatch) -> None:
    from golavo_server import conditions, runtime

    monkeypatch.setattr(runtime, "weather_dir", lambda: tmp_path)
    _validate_weather(conditions.weather_context_for("m_absent"))  # blocked variant


def test_a_capture_fetched_after_kickoff_is_never_shown(tmp_path, monkeypatch) -> None:
    # A forecast fetched after the match started is not a pre-kickoff forecast.
    ctx = _seed(tmp_path, monkeypatch, fetched_at="2026-08-16T20:00:00Z")
    assert ctx["status"] == "blocked"
    assert ctx["reason_code"] == "no_pre_kickoff_capture"


def test_store_round_trips_and_returns_the_latest_pre_kickoff_capture(tmp_path) -> None:
    reading = weather_source.fetch_forecast(
        40.4, -3.7, kickoff_utc="2026-08-16T19:00:00Z",
        fetched_at_utc="2026-08-01T09:00:00Z", transport=_transport,
    )
    weather_store.save_reading(tmp_path, "m_celta_osasuna", reading)
    # A later capture, still before kickoff, supersedes the earlier one.
    later = {**reading, "fetched_at_utc": "2026-08-10T09:00:00Z", "temperature_2m_c": 25.0}
    weather_store.save_reading(tmp_path, "m_celta_osasuna", later)

    latest = weather_store.load_latest(tmp_path, "m_celta_osasuna")
    assert latest is not None
    assert latest["fetched_at_utc"] == "2026-08-10T09:00:00Z"
    assert latest["temperature_2m_c"] == 25.0
    assert weather_store.load_latest(tmp_path, "m_unknown") is None
