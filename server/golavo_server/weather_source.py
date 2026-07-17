"""The only module allowed to call Open-Meteo — a keyless, per-user weather fetch.

Weather is display-only context (``model_input: false``), never a forecast input.
The transport is injectable so the parser and guards are tested against recorded
bytes; the default transport is host-allowlisted to ``api.open-meteo.com``, sends
no key, caps the response size, and times out, failing closed on anything unusual.

Open-Meteo returns no model-issue timestamp (``generationtime_ms`` is compute
duration), so the caller records ``fetched_at_utc`` itself — that instant, not a
server field, is what the pre-kickoff display gate compares against kickoff.
"""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Callable
from datetime import datetime
from typing import Any
from urllib.parse import urlencode, urlsplit

_ENDPOINT = "https://api.open-meteo.com/v1/forecast"
_ALLOWED_HOST = "api.open-meteo.com"
_ATTRIBUTION_URL = "https://open-meteo.com/"
_HOURLY_VARS = (
    "temperature_2m",
    "precipitation",
    "precipitation_probability",
    "wind_speed_10m",
    "weather_code",
)
_MAX_BYTES = 2_000_000
_TIMEOUT_SECONDS = 15

Transport = Callable[[str], str]


class WeatherError(RuntimeError):
    """A weather fetch failed and must fail closed (no partial/guessed reading)."""


def _http_get(url: str) -> str:
    """The real transport: HTTPS GET to the one allowlisted host, size-capped."""
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname != _ALLOWED_HOST:
        raise WeatherError(f"weather fetch refused non-allowlisted URL: {url}")
    request = urllib.request.Request(url, method="GET")  # noqa: S310 (scheme checked above)
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:  # noqa: S310
            raw = response.read(_MAX_BYTES + 1)
    except (OSError, ValueError) as exc:
        raise WeatherError(f"weather fetch failed: {exc}") from exc
    if len(raw) > _MAX_BYTES:
        raise WeatherError("weather response exceeded the size cap")
    return raw.decode("utf-8", errors="replace")


def _to_hour_key(iso_utc: str) -> str:
    """Open-Meteo hourly labels are naive local-hour strings 'YYYY-MM-DDTHH:00'."""
    stamp = datetime.fromisoformat(iso_utc.replace("Z", "+00:00"))
    return stamp.strftime("%Y-%m-%dT%H:00")


def fetch_forecast(
    latitude: float,
    longitude: float,
    *,
    kickoff_utc: str,
    fetched_at_utc: str,
    transport: Transport | None = None,
) -> dict[str, Any]:
    """A context-only forecast reading for the hour of ``kickoff_utc`` at a venue.

    Raises ``WeatherError`` on any network, decode, schema, or missing-hour
    problem: a weather card is never shown from a partial or guessed reading.
    """
    fetch = transport or _http_get
    query = urlencode(
        {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": ",".join(_HOURLY_VARS),
            "timezone": "GMT",
            "forecast_days": 16,
        }
    )
    body = fetch(f"{_ENDPOINT}?{query}")
    try:
        payload = json.loads(body)
        hourly = payload["hourly"]
        times = list(hourly["time"])
    except (ValueError, KeyError, TypeError) as exc:
        raise WeatherError(f"unparseable weather response: {exc}") from exc

    target = _to_hour_key(kickoff_utc)
    if target not in times:
        raise WeatherError("kickoff hour is outside the returned forecast window")
    idx = times.index(target)

    try:
        return {
            "provider": "open-meteo",
            "fetched_at_utc": fetched_at_utc,
            "kickoff_utc": kickoff_utc,
            "temperature_2m_c": float(hourly["temperature_2m"][idx]),
            "precipitation_mm": float(hourly["precipitation"][idx]),
            "precipitation_probability_pct": int(hourly["precipitation_probability"][idx]),
            "wind_speed_10m_kmh": float(hourly["wind_speed_10m"][idx]),
            "weather_code": int(hourly["weather_code"][idx]),
            "attribution_url": _ATTRIBUTION_URL,
            "model_input": False,
        }
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise WeatherError(f"incomplete weather reading: {exc}") from exc
