"""Consent-gated weather refresh: resolve a venue, fetch a pre-kickoff forecast, store it.

The one place that ties the fetch lane, the venue coordinate lookup and the
per-user store together. It refuses fixtures it cannot honestly serve — an
unknown match, a venue with no bundled coordinates, or a kickoff already passed —
and fails closed on any fetch error. Weather stays display-only context.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from golavo_server.weather_source import Transport


class WeatherRefreshError(RuntimeError):
    """A refresh could not proceed; carries an HTTP status and a typed reason."""

    def __init__(self, status: int, reason_code: str, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.reason_code = reason_code
        self.detail = detail


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def refresh(
    match_id: str,
    *,
    now_utc: datetime,
    transport: Transport | None = None,
) -> dict[str, Any]:
    """Fetch and store a pre-kickoff forecast for a match, returning its weather card.

    ``now_utc`` is the recorded ``fetched_at`` and the kickoff comparison instant.
    ``transport`` is injected in tests; production uses the allowlisted default.
    """
    from golavo_server import conditions, matches, runtime, weather_source, weather_store

    detail = matches.get_match(match_id)
    if detail is None:
        raise WeatherRefreshError(404, "match_not_found", "no indexed match with that id")
    match = detail["match"]

    kickoff_raw = str(match.get("kickoff_utc") or "")
    try:
        kickoff = datetime.fromisoformat(kickoff_raw.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError as exc:
        raise WeatherRefreshError(422, "kickoff_unknown", "fixture has no usable kickoff") from exc
    if now_utc.astimezone(UTC) >= kickoff:
        raise WeatherRefreshError(
            422, "kickoff_passed", "a pre-kickoff forecast can only be fetched before kickoff"
        )

    coords = conditions.resolve_coords(match.get("city"), match.get("country"))
    if coords is None:
        raise WeatherRefreshError(
            422, "location_unresolved", "no bundled coordinates for this fixture's venue"
        )

    try:
        reading = weather_source.fetch_forecast(
            coords[0],
            coords[1],
            kickoff_utc=_iso(kickoff),
            fetched_at_utc=_iso(now_utc),
            transport=transport,
        )
    except weather_source.WeatherError as exc:
        raise WeatherRefreshError(502, "fetch_failed", str(exc)) from exc

    weather_store.save_reading(runtime.weather_dir(), match_id, reading)
    return conditions._forecast_weather(reading)
