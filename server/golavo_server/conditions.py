"""Deterministic, provenance-complete, display-only match context."""

from __future__ import annotations

import hashlib
import json
import math
import unicodedata
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any
from zoneinfo import TZPATH, ZoneInfo, ZoneInfoNotFoundError

from golavo_core import resources

from golavo_server import context_registry

SCHEMA_VERSION = "0.3.0"
LABEL = "Context, not a model input."
GEONAMES_ATTRIBUTION = "Data from GeoNames (geonames.org), CC BY 4.0."
NATURAL_EARTH_ATTRIBUTION = "Made with Natural Earth."
EARTH_RADIUS_KM = 6371.0088

PLACES_PATH = Path(resources.geonames_places_path())
WORLD_PATH = Path(resources.natural_earth_world_path())
_PLACES: dict[str, dict[str, Any]] | None = None
_WORLD: dict[str, Any] | None = None


def reset_cache() -> None:
    global _PLACES, _WORLD
    _PLACES = None
    _WORLD = None
    context_registry.reset_cache()


def _norm(value: Any) -> str:
    decomposed = unicodedata.normalize("NFKD", str(value))
    plain = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(plain.casefold().replace("’", "'").split())


def _stable_id(kind: str, source_key: str) -> str:
    return f"{kind}_{hashlib.sha256(source_key.encode()).hexdigest()[:16]}"


def _claim_id(entity_id: str, field: str) -> str:
    return f"ctxc_{hashlib.sha256(f'{entity_id}:{field}'.encode()).hexdigest()[:16]}"


def _load_places() -> dict[str, dict[str, Any]]:
    global _PLACES
    if _PLACES is None:
        try:
            payload = json.loads(PLACES_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            payload = {}
        _PLACES = payload if isinstance(payload, dict) else {}
    return _PLACES


def _place_source_ref(place: dict[str, Any], field: str) -> dict[str, Any] | None:
    digest = place.get("snapshot_sha256")
    record_id = place.get("geoname_id")
    revision = place.get("source_revision") or place.get("modified")
    if not digest or record_id is None or not revision:
        return None
    return {
        "source_id": "geonames",
        "source_record_id": str(record_id),
        "source_revision": str(revision),
        "snapshot_sha256": str(digest),
        "retrieved_at_utc": "2026-07-15T07:57:00Z",
        "field": field,
    }


def _location(city: Any, country: Any) -> dict[str, Any]:
    base = {
        "status": "unknown",
        "reason": "match-city-or-country-missing",
        "entity_id": None,
        "resolution_status": "unresolved",
        "city": None if city is None else str(city),
        "country": None if country is None else str(country),
        "latitude": None,
        "longitude": None,
        "elevation_m": None,
        "elevation_source": None,
        "timezone": None,
        "source_id": None,
        "provenance": {},
    }
    if city is None or country is None:
        return base
    key = f"{_norm(country)}|{_norm(city)}"
    place = _load_places().get(key)
    if place is None:
        return {
            **base,
            "reason": "city-not-resolved-in-reviewed-context-pack",
            "city": str(city),
            "country": str(country),
        }
    entity_id = str(place["entity_id"])
    provenance = {}
    for field in ("latitude", "longitude", "elevation_m", "timezone"):
        source_ref = _place_source_ref(place, field)
        if source_ref is not None and place.get(field) is not None:
            provenance[field] = {
                "claim_id": _claim_id(entity_id, field),
                "source_refs": [source_ref],
            }
    return {
        "status": "available",
        "reason": None,
        "entity_id": entity_id,
        "resolution_status": "resolved",
        "city": str(city),
        "country": str(country),
        "latitude": float(place["latitude"]),
        "longitude": float(place["longitude"]),
        "elevation_m": place.get("elevation_m"),
        "elevation_source": place.get("elevation_source"),
        "timezone": place.get("timezone"),
        "source_id": "geonames",
        "provenance": provenance,
    }


def _public_location(location: dict[str, Any]) -> dict[str, Any]:
    return {
        key: location[key]
        for key in (
            "status",
            "reason",
            "entity_id",
            "resolution_status",
            "city",
            "country",
            "latitude",
            "longitude",
            "elevation_m",
            "elevation_source",
            "timezone",
            "source_id",
            "provenance",
        )
    }


def _haversine_km(origin: dict[str, Any], destination: dict[str, Any]) -> float:
    lat1, lon1 = math.radians(origin["latitude"]), math.radians(origin["longitude"])
    lat2, lon2 = math.radians(destination["latitude"]), math.radians(destination["longitude"])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return round(EARTH_RADIUS_KM * 2 * math.asin(math.sqrt(a)), 1)


def _row_source_ref(
    row: Any, field_group: str, index_fingerprint: str
) -> dict[str, Any]:
    import pandas as pd

    column = f"{field_group}_source_id"
    value = row.get(column, row.get("source_id"))
    source_id = str(row.get("source_id")) if pd.isna(value) else str(value)
    upstream_key = row.get("upstream_fixture_key", row.get("match_id"))
    return {
        "source_id": source_id,
        "source_record_id": str(upstream_key),
        "source_revision": "active-index-generation",
        "snapshot_sha256": index_fingerprint,
        "retrieved_at_utc": None,
        "field": field_group,
    }


def _previous_match(frame: Any, target: Any, team: str) -> Any | None:
    import pandas as pd

    target_ko = pd.Timestamp(target["kickoff_utc"])
    target_ko = (
        target_ko.tz_localize("UTC") if target_ko.tzinfo is None else target_ko.tz_convert("UTC")
    )
    kickoff = pd.to_datetime(frame["kickoff_utc"], utc=True)
    same_kind = frame["source_kind"].astype("string") == str(target["source_kind"])
    normalized = _norm(team)
    involves = frame["home_team"].astype("string").map(_norm).eq(normalized) | frame[
        "away_team"
    ].astype("string").map(_norm).eq(normalized)
    completed = frame["is_complete"].astype("boolean").fillna(False).astype(bool)
    prior = frame.loc[same_kind & involves & completed & (kickoff < target_ko)].copy()
    if prior.empty:
        return None
    prior["_ko"] = pd.to_datetime(prior["kickoff_utc"], utc=True)
    return prior.sort_values(["_ko", "match_id"], ascending=[False, True], kind="mergesort").iloc[0]


def _derivation(algorithm_id: str, formula: str, input_claim_ids: list[str]) -> dict[str, Any]:
    return {
        "generator": "golavo-derived-context",
        "algorithm_id": algorithm_id,
        "algorithm_version": "1",
        "formula": formula,
        "input_claim_ids": input_claim_ids,
    }


def _kickoff_claim_id(row: Any) -> str:
    return _claim_id(str(row["match_id"]), "kickoff_utc")


def _gap(target: Any, previous: Any) -> dict[str, Any]:
    import pandas as pd

    target_time = pd.Timestamp(target["kickoff_utc"])
    previous_time = pd.Timestamp(previous["kickoff_utc"])
    target_precision = str(target.get("kickoff_precision") or "day")
    previous_precision = str(previous.get("kickoff_precision") or "day")
    inputs = [_kickoff_claim_id(previous), _kickoff_claim_id(target)]
    base = {
        "status": "available",
        "reason": None,
        "previous_match_id": str(previous["match_id"]),
        "previous_kickoff_utc": previous_time.isoformat().replace("+00:00", "Z"),
        "coverage_label": "Previous completed match found in Golavo's local core index.",
        "derivation": _derivation(
            "kickoff-gap",
            "target kickoff minus previous indexed kickoff",
            inputs,
        ),
    }
    if target_precision == "exact" and previous_precision == "exact":
        hours = (target_time - previous_time).total_seconds() / 3600
        return {
            **base,
            "precision": "exact",
            "elapsed_hours": round(hours, 1),
            "complete_days": math.floor(hours / 24),
            "calendar_gap_days": None,
        }
    return {
        **base,
        "precision": "calendar-day",
        "elapsed_hours": None,
        "complete_days": None,
        "calendar_gap_days": int((target_time.date() - previous_time.date()).days),
    }


def _unknown_gap(reason: str) -> dict[str, Any]:
    return {
        "status": "unknown",
        "reason": reason,
        "precision": "unknown",
        "elapsed_hours": None,
        "complete_days": None,
        "calendar_gap_days": None,
        "previous_match_id": None,
        "previous_kickoff_utc": None,
        "coverage_label": "Golavo does not claim complete schedule coverage.",
        "derivation": None,
    }


def _team_context(
    frame: Any, target: Any, side: str, destination: dict[str, Any]
) -> dict[str, Any]:
    import pandas as pd

    team = str(target[f"{side}_team"])
    team_entity_id = _stable_id("team", f"{target['source_kind']}:{_norm(team)}")
    previous = _previous_match(frame, target, team)
    if previous is None:
        gap = _unknown_gap("no-prior-indexed-match")
        return {
            "side": side,
            "team": team,
            "team_entity_id": team_entity_id,
            "kickoff_gap": gap,
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
                "measurement": "great-circle-between-indexed-match-locations",
                "distance_km": None,
                "origin": None,
                "destination": _public_location(destination),
                "derivation": None,
            },
        }
    gap = _gap(target, previous)
    previous_location = _location(
        None if pd.isna(previous.get("city")) else previous.get("city"),
        None if pd.isna(previous.get("country")) else previous.get("country"),
    )
    if previous_location["status"] != "available":
        reason = "previous-match-location-unknown"
        distance = None
    elif destination["status"] != "available":
        reason = "target-match-location-unknown"
        distance = None
    else:
        reason = None
        distance = _haversine_km(previous_location, destination)
    input_claims = []
    for location in (previous_location, destination):
        for field in ("latitude", "longitude"):
            claim = location.get("provenance", {}).get(field)
            if claim:
                input_claims.append(claim["claim_id"])
    travel = {
        "status": "available" if distance is not None else "unknown",
        "reason": reason,
        "measurement": "great-circle-between-indexed-match-locations",
        "distance_km": distance,
        "origin": _public_location(previous_location),
        "destination": _public_location(destination),
        "derivation": (
            _derivation(
                "great-circle-haversine",
                "2 * 6371.0088 * asin(sqrt(sin²(dlat/2) + cos(lat1)*cos(lat2)*sin²(dlon/2)))",
                input_claims,
            )
            if distance is not None
            else None
        ),
    }
    rest_available = gap["precision"] == "exact"
    rest = {
        "status": "available" if rest_available else "unknown",
        "reason": None if rest_available else "kickoff-precision-is-calendar-day",
        "days": gap["complete_days"] if rest_available else None,
        "previous_match_id": gap["previous_match_id"],
        "previous_kickoff_utc": gap["previous_kickoff_utc"],
    }
    return {
        "side": side,
        "team": team,
        "team_entity_id": team_entity_id,
        "kickoff_gap": gap,
        "rest": rest,
        "travel": travel,
    }


def _tzdb_fingerprint(timezone: str) -> str:
    safe = Path(timezone)
    if safe.is_absolute() or ".." in safe.parts:
        return "invalid-timezone-path"
    for root in TZPATH:
        candidate = Path(root) / safe
        try:
            return f"tzif-sha256:{hashlib.sha256(candidate.read_bytes()).hexdigest()}"
        except OSError:
            continue
    try:
        return f"tzdata-package:{version('tzdata')}"
    except PackageNotFoundError:
        return "tzdb-unidentified"


def _local_kickoff(target: Any, location: dict[str, Any], precision: str) -> dict[str, Any]:
    base = {
        "status": "unknown",
        "reason": "kickoff-is-day-only",
        "value": None,
        "timezone": location.get("timezone"),
        "utc_offset_minutes": None,
        "tzdb_fingerprint": None,
        "derivation": None,
    }
    if precision != "exact":
        return base
    timezone = location.get("timezone")
    if not timezone:
        return {**base, "reason": "timezone-unknown", "timezone": None}
    import pandas as pd

    try:
        local = pd.Timestamp(target["kickoff_utc"]).to_pydatetime().astimezone(
            ZoneInfo(str(timezone))
        )
    except (ZoneInfoNotFoundError, ValueError):
        return {**base, "reason": "timezone-unavailable", "timezone": str(timezone)}
    timezone_claim = location.get("provenance", {}).get("timezone")
    inputs = [_kickoff_claim_id(target)]
    if timezone_claim:
        inputs.append(timezone_claim["claim_id"])
    offset = local.utcoffset()
    return {
        "status": "available",
        "reason": None,
        "value": local.isoformat(),
        "timezone": str(timezone),
        "utc_offset_minutes": int(offset.total_seconds() / 60) if offset else 0,
        "tzdb_fingerprint": _tzdb_fingerprint(str(timezone)),
        "derivation": _derivation(
            "iana-local-kickoff",
            "convert exact UTC kickoff through resolved IANA timezone",
            inputs,
        ),
    }


def conditions_snapshot(
    match_id: str, frame: Any, *, index_fingerprint: str = "unknown"
) -> dict[str, Any] | None:
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
            "derivation": item["travel"]["derivation"],
        }
        for item in teams
        if item["travel"]["status"] == "available"
    ]
    map_status = "available" if len(routes) == 2 else "partial" if routes else "unknown"
    kickoff_utc = pd.Timestamp(target["kickoff_utc"]).isoformat().replace("+00:00", "Z")
    capability = context_registry.capabilities(index_fingerprint)
    venue = context_registry.venue_for_match(target)
    sources = context_registry.source_catalog()
    if not sources:
        sources = [
            {"source_id": "geonames", "attribution": GEONAMES_ATTRIBUTION},
            {"source_id": "natural-earth", "attribution": NATURAL_EARTH_ATTRIBUTION},
        ]
    return {
        "schema_version": SCHEMA_VERSION,
        "label": LABEL,
        "capability": capability,
        "match": {
            "match_id": str(target["match_id"]),
            "kickoff_utc": kickoff_utc,
            "kickoff_precision": precision,
            "source_refs": [
                _row_source_ref(target, "identity", index_fingerprint),
                _row_source_ref(target, "kickoff", index_fingerprint),
                _row_source_ref(target, "venue", index_fingerprint),
            ],
            "local_kickoff": _local_kickoff(target, destination, precision),
            "venue": venue,
            "location": _public_location(destination),
        },
        "teams": teams,
        "travel_map": {
            "status": map_status,
            "source_id": "natural-earth",
            "attribution": NATURAL_EARTH_ATTRIBUTION,
            "routes": routes,
        },
        "weather_context": {
            "status": "blocked",
            "reason_code": "no_leakage_safe_historical_forecast_source",
            "reason": (
                "Weather is context-only and unavailable until a licensed source preserves "
                "the forecast issued before kickoff. Observed weather is not substituted."
            ),
            "model_input": False,
            "source_id": None,
        },
        "sources": sources,
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
        try:
            manifest = json.loads(
                Path(resources.context_manifest_path()).read_text(encoding="utf-8")
            )
            entry = next(
                item
                for item in manifest["files"]
                if item["path"] == "data/enrichment/world_110m.geojson"
            )
            payload = {
                **payload,
                "context_pack_version": manifest["context_pack_version"],
                "sha256": entry["sha256"],
            }
        except (OSError, ValueError, TypeError, KeyError, StopIteration):
            pass
        _WORLD = payload
    return _WORLD
