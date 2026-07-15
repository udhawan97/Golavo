"""Leakage-safe, display-only match conditions from committed local resources."""

from __future__ import annotations

import json
import math
import unicodedata
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from golavo_core import resources

SCHEMA_VERSION = "0.1.0"
LABEL = "Context, not a model input."
GEONAMES_ATTRIBUTION = "Data from GeoNames (geonames.org), CC BY 4.0."
NATURAL_EARTH_ATTRIBUTION = "Made with Natural Earth."

PLACES_PATH = Path(resources.geonames_places_path())
WORLD_PATH = Path(resources.natural_earth_world_path())
_PLACES: dict[str, dict[str, Any]] | None = None
_WORLD: dict[str, Any] | None = None


def reset_cache() -> None:
    global _PLACES, _WORLD
    _PLACES = None
    _WORLD = None


def _norm(value: Any) -> str:
    decomposed = unicodedata.normalize("NFKD", str(value))
    plain = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(plain.casefold().replace("’", "'").split())


def _load_places() -> dict[str, dict[str, Any]]:
    global _PLACES
    if _PLACES is None:
        try:
            payload = json.loads(PLACES_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            payload = {}
        _PLACES = payload if isinstance(payload, dict) else {}
    return _PLACES


def _location(city: Any, country: Any) -> dict[str, Any]:
    if city is None or country is None:
        return {
            "status": "unknown",
            "reason": "match-city-or-country-missing",
            "city": None if city is None else str(city),
            "country": None if country is None else str(country),
            "latitude": None,
            "longitude": None,
            "elevation_m": None,
            "timezone": None,
            "source_id": None,
        }
    key = f"{_norm(country)}|{_norm(city)}"
    place = _load_places().get(key)
    if place is None:
        return {
            "status": "unknown",
            "reason": "city-not-resolved-in-pinned-dump",
            "city": str(city),
            "country": str(country),
            "latitude": None,
            "longitude": None,
            "elevation_m": None,
            "timezone": None,
            "source_id": None,
        }
    return {
        "status": "available",
        "reason": None,
        "city": str(city),
        "country": str(country),
        "latitude": float(place["latitude"]),
        "longitude": float(place["longitude"]),
        "elevation_m": place.get("elevation_m"),
        "timezone": place.get("timezone"),
        "source_id": "geonames",
    }


def _public_location(location: dict[str, Any]) -> dict[str, Any]:
    return {
        key: location[key]
        for key in (
            "status",
            "reason",
            "city",
            "country",
            "latitude",
            "longitude",
            "elevation_m",
            "timezone",
            "source_id",
        )
    }


def _haversine_km(origin: dict[str, Any], destination: dict[str, Any]) -> float:
    lat1, lon1 = math.radians(origin["latitude"]), math.radians(origin["longitude"])
    lat2, lon2 = math.radians(destination["latitude"]), math.radians(destination["longitude"])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return round(6371.0088 * 2 * math.asin(math.sqrt(a)), 1)


def _previous_match(frame: Any, target: Any, team: str) -> Any | None:
    import pandas as pd

    target_ko = pd.Timestamp(target["kickoff_utc"])
    target_ko = (
        target_ko.tz_localize("UTC") if target_ko.tzinfo is None else target_ko.tz_convert("UTC")
    )
    kickoff = pd.to_datetime(frame["kickoff_utc"], utc=True)
    same_kind = frame["source_kind"].astype("string") == str(target["source_kind"])
    involves = (frame["home_team"].astype("string") == team) | (
        frame["away_team"].astype("string") == team
    )
    completed = frame["is_complete"].astype("boolean").fillna(False).astype(bool)
    prior = frame.loc[same_kind & involves & completed & (kickoff < target_ko)].copy()
    if prior.empty:
        return None
    prior["_ko"] = pd.to_datetime(prior["kickoff_utc"], utc=True)
    return prior.sort_values(["_ko", "match_id"], ascending=[False, True], kind="mergesort").iloc[0]


def _team_context(
    frame: Any, target: Any, side: str, destination: dict[str, Any]
) -> dict[str, Any]:
    import pandas as pd

    team = str(target[f"{side}_team"])
    previous = _previous_match(frame, target, team)
    if previous is None:
        return {
            "side": side,
            "team": team,
            "rest": {
                "status": "unknown",
                "reason": "no-prior-indexed-match",
                "days": None,
                "previous_match_id": None,
                "previous_kickoff_utc": None,
            },
            "travel": {
                "status": "unknown",
                "reason": "no-prior-indexed-match",
                "distance_km": None,
                "origin": None,
                "destination": _public_location(destination),
            },
        }
    target_day = pd.Timestamp(target["kickoff_utc"]).date()
    previous_day = pd.Timestamp(previous["kickoff_utc"]).date()
    previous_location = _location(
        None if pd.isna(previous.get("city")) else previous.get("city"),
        None if pd.isna(previous.get("country")) else previous.get("country"),
    )
    rest = {
        "status": "available",
        "reason": None,
        "days": int((target_day - previous_day).days),
        "previous_match_id": str(previous["match_id"]),
        "previous_kickoff_utc": pd.Timestamp(previous["kickoff_utc"])
        .isoformat()
        .replace("+00:00", "Z"),
    }
    if previous_location["status"] != "available":
        reason = "previous-match-location-unknown"
        distance = None
    elif destination["status"] != "available":
        reason = "target-match-location-unknown"
        distance = None
    else:
        reason = None
        distance = _haversine_km(previous_location, destination)
    travel = {
        "status": "available" if distance is not None else "unknown",
        "reason": reason,
        "distance_km": distance,
        "origin": _public_location(previous_location),
        "destination": _public_location(destination),
    }
    return {"side": side, "team": team, "rest": rest, "travel": travel}


def _local_kickoff(target: Any, location: dict[str, Any], precision: str) -> dict[str, Any]:
    if precision != "exact":
        return {
            "status": "unknown",
            "reason": "kickoff-is-day-only",
            "value": None,
            "timezone": location.get("timezone"),
        }
    timezone = location.get("timezone")
    if not timezone:
        return {"status": "unknown", "reason": "timezone-unknown", "value": None, "timezone": None}
    import pandas as pd

    try:
        local = (
            pd.Timestamp(target["kickoff_utc"]).to_pydatetime().astimezone(ZoneInfo(str(timezone)))
        )
    except (ZoneInfoNotFoundError, ValueError):
        return {
            "status": "unknown",
            "reason": "timezone-unavailable",
            "value": None,
            "timezone": str(timezone),
        }
    return {
        "status": "available",
        "reason": None,
        "value": local.isoformat(),
        "timezone": str(timezone),
    }


def conditions_snapshot(match_id: str, frame: Any) -> dict[str, Any] | None:
    import pandas as pd

    selected = frame.loc[frame["match_id"].astype("string") == str(match_id)]
    if selected.empty:
        return None
    target = selected.iloc[0]
    city = None if pd.isna(target.get("city")) else str(target.get("city"))
    country = None if pd.isna(target.get("country")) else str(target.get("country"))
    destination = _location(city, country)
    precision = (
        str(target.get("kickoff_precision") or "day")
        if not pd.isna(target.get("kickoff_precision", "day"))
        else "day"
    )
    teams = [_team_context(frame, target, side, destination) for side in ("home", "away")]
    routes = [
        {
            "side": item["side"],
            "team": item["team"],
            "distance_km": item["travel"]["distance_km"],
            "origin": item["travel"]["origin"],
            "destination": item["travel"]["destination"],
        }
        for item in teams
        if item["travel"]["status"] == "available"
    ]
    map_status = "available" if len(routes) == 2 else "partial" if routes else "unknown"
    kickoff_utc = pd.Timestamp(target["kickoff_utc"]).isoformat().replace("+00:00", "Z")
    return {
        "schema_version": SCHEMA_VERSION,
        "label": LABEL,
        "match": {
            "match_id": str(target["match_id"]),
            "kickoff_utc": kickoff_utc,
            "kickoff_precision": precision,
            "local_kickoff": _local_kickoff(target, destination, precision),
            "venue": {"status": "unknown", "name": None, "reason": "no-stadium-level-source"},
            "location": _public_location(destination),
        },
        "teams": teams,
        "travel_map": {
            "status": map_status,
            "source_id": "natural-earth",
            "attribution": NATURAL_EARTH_ATTRIBUTION,
            "routes": routes,
        },
        "sources": [
            {"source_id": "geonames", "attribution": GEONAMES_ATTRIBUTION},
            {"source_id": "natural-earth", "attribution": NATURAL_EARTH_ATTRIBUTION},
        ],
    }


def world_map() -> dict[str, Any]:
    global _WORLD
    if _WORLD is None:
        try:
            payload = json.loads(WORLD_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError) as exc:
            raise OSError("Natural Earth basemap unavailable") from exc
        if not isinstance(payload, dict) or payload.get("type") != "FeatureCollection":
            raise OSError("Natural Earth basemap invalid")
        _WORLD = payload
    return _WORLD
