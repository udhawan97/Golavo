#!/usr/bin/env python3
"""Build revision-pinned World Cup venue context and reviewed Wikidata links.

This is an explicit maintainer build command. The installed application never
contacts either upstream. Every venue assignment originates in the pinned
openfootball stadium file; Wikidata only supplies a reviewed stable entity link
and aliases, and conflicting country/coordinate claims fail the build closed.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import urllib.request
from functools import partial
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ALLOWLIST_PATH = ROOT / "data/context/venue_source_allowlist.json"
RETRIEVED_AT = "2026-07-15T18:00:00Z"
USER_AGENT = "Golavo-maintainer/phase4 (https://github.com/udhawan97/Golavo)"
COORD_RE = re.compile(
    r"(?P<deg>\d+(?:\.\d+)?)°"
    r"(?:(?P<min>\d+(?:\.\d+)?)['′])?"
    r"(?:(?P<sec>\d+(?:\.\d+)?)[\"″])?"
    r"(?P<direction>[NSEW])"
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _stable_id(kind: str, source_key: str) -> str:
    return f"{kind}_{hashlib.sha256(source_key.encode('utf-8')).hexdigest()[:16]}"


def _claim_id(entity_id: str, field: str) -> str:
    return f"ctxc_{hashlib.sha256(f'{entity_id}:{field}'.encode()).hexdigest()[:16]}"


def _norm(value: str) -> str:
    return " ".join(value.casefold().replace("’", "'").split())


def _fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
        return response.read()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _coordinate(text: str) -> tuple[float, float]:
    values: dict[str, float] = {}
    for match in COORD_RE.finditer(text):
        value = float(match.group("deg"))
        value += float(match.group("min") or 0) / 60
        value += float(match.group("sec") or 0) / 3600
        direction = match.group("direction")
        if direction in {"S", "W"}:
            value = -value
        values[direction] = value
    latitude = values.get("N", values.get("S"))
    longitude = values.get("E", values.get("W"))
    if latitude is None or longitude is None:
        raise ValueError(f"cannot parse stadium coordinate {text!r}")
    return latitude, longitude


def _wikidata_values(entity: dict[str, Any], property_id: str) -> list[Any]:
    values = []
    for statement in entity.get("claims", {}).get(property_id, []):
        snak = statement.get("mainsnak", {})
        if snak.get("snaktype") != "value":
            continue
        value = snak.get("datavalue", {}).get("value")
        if value is not None:
            values.append(value)
    return values


def _haversine_km(one: tuple[float, float], two: tuple[float, float]) -> float:
    lat1, lon1 = map(math.radians, one)
    lat2, lon2 = map(math.radians, two)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371.0088 * 2 * math.asin(math.sqrt(a))


def _source_ref(
    source_id: str, record_id: str, revision: str, digest: str, field: str
) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "source_record_id": record_id,
        "source_revision": revision,
        "snapshot_sha256": digest,
        "retrieved_at_utc": RETRIEVED_AT,
        "field": field,
    }


def _claim(
    entity_id: str,
    field: str,
    value: Any,
    source_ref: dict[str, Any],
    *,
    language: str | None = None,
) -> dict[str, Any]:
    return {
        "claim_id": _claim_id(entity_id, field),
        "field": field,
        "value": value,
        "language": language,
        "precision": None,
        "source_refs": [source_ref],
    }


def _register_pack(pack_dir: Path, manifest: dict[str, Any]) -> None:
    registry_path = ROOT / "packs/enrichment.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    relative = pack_dir.relative_to(ROOT).as_posix()
    entry = {
        "pack": relative,
        "source_id": manifest["source_id"],
        "upstream_ref": manifest["upstream_ref"],
        "retrieved_at_utc": manifest["retrieved_at_utc"],
        "manifest_sha256": _sha((pack_dir / "manifest.json").read_bytes()),
    }
    existing = [item for item in registry["snapshots"] if item["pack"] != relative]
    registry["snapshots"] = sorted([*existing, entry], key=lambda item: item["pack"])
    _write_json(registry_path, registry)


def main() -> None:
    allowlist = json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))
    commit = str(allowlist["worldcup_commit"])
    stadium_url = (
        "https://raw.githubusercontent.com/openfootball/worldcup.json/"
        f"{commit}/2026/worldcup.stadiums.json"
    )
    stadium_bytes = _fetch(stadium_url)
    actual = _sha(stadium_bytes)
    expected = str(allowlist["worldcup_stadiums_sha256"])
    if actual != expected:
        raise ValueError(f"worldcup.stadiums.json drift: expected {expected}, got {actual}")
    stadium_payload = json.loads(stadium_bytes)
    stadiums = {str(item["city"]): item for item in stadium_payload["stadiums"]}

    openfootball_pack = ROOT / "packs" / f"openfootball-worldcup-context-{commit[:12]}"
    openfootball_pack.mkdir(parents=True, exist_ok=True)
    (openfootball_pack / "worldcup.stadiums.json").write_bytes(stadium_bytes)
    openfootball_manifest = {
        "source_id": "openfootball-worldcup-json",
        "license": "CC0-1.0",
        "upstream_ref": commit,
        "retrieved_at_utc": RETRIEVED_AT,
        "url": "https://github.com/openfootball/worldcup.json",
        "files": [
            {"name": "worldcup.stadiums.json", "sha256": actual, "url": stadium_url}
        ],
    }
    _write_json(openfootball_pack / "manifest.json", openfootball_manifest)
    _register_pack(openfootball_pack, openfootball_manifest)

    wikidata_pack = ROOT / "packs" / "wikidata-context-2026-07-15"
    raw_dir = wikidata_pack / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    wikidata_files: list[dict[str, str]] = []
    venue_entities: list[dict[str, Any]] = []
    assignments: list[dict[str, Any]] = []

    for reviewed in allowlist["venues"]:
        city = str(reviewed["source_city"])
        source = stadiums.get(city)
        if source is None or source.get("name") != reviewed["source_name"]:
            raise ValueError(f"reviewed venue {city!r} no longer matches the pinned stadium source")
        qid = str(reviewed["wikidata_qid"])
        revision = str(reviewed["wikidata_revision"])
        url = f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json?revision={revision}"
        raw = _fetch(url)
        payload = json.loads(raw)
        entity = payload.get("entities", {}).get(qid)
        if not isinstance(entity, dict) or str(entity.get("lastrevid")) != revision:
            raise ValueError(f"{qid}: response does not match reviewed revision {revision}")
        english_label = entity.get("labels", {}).get("en")
        labels = (
            {str(english_label["value"])}
            if isinstance(english_label, dict) and english_label.get("value")
            else set()
        )
        aliases = {
            str(value["value"])
            for value in entity.get("aliases", {}).get("en", [])
            if isinstance(value, dict) and value.get("value")
        }
        expected_wikidata_label = str(reviewed.get("wikidata_expected_label", source["name"]))
        if _norm(expected_wikidata_label) not in {_norm(value) for value in labels | aliases}:
            raise ValueError(f"{qid}: reviewed stadium name is absent from labels/aliases")
        countries = {
            value.get("id") for value in _wikidata_values(entity, "P17") if isinstance(value, dict)
        }
        if reviewed["country_qid"] not in countries:
            raise ValueError(f"{qid}: reviewed country is absent from P17")
        source_coordinate = _coordinate(str(source["coords"]))
        coordinates = _wikidata_values(entity, "P625")
        if not coordinates:
            raise ValueError(f"{qid}: no Wikidata coordinate to corroborate the reviewed link")
        wikidata_coordinate = (
            float(coordinates[0]["latitude"]),
            float(coordinates[0]["longitude"]),
        )
        discrepancy_km = _haversine_km(source_coordinate, wikidata_coordinate)
        link_status = str(reviewed.get("wikidata_link_status", "accepted"))
        if link_status not in {"accepted", "conflicting"}:
            raise ValueError(f"{qid}: invalid reviewed link status {link_status!r}")
        if link_status == "accepted" and discrepancy_km > 0.25:
            raise ValueError(
                f"{qid}: source/Wikidata coordinates differ by {discrepancy_km:.3f} km (>0.25)"
            )
        if link_status == "conflicting" and discrepancy_km <= 0.25:
            raise ValueError(f"{qid}: reviewed coordinate conflict no longer exceeds 0.25 km")

        raw_path = raw_dir / f"{qid}.json"
        raw_path.write_bytes(raw)
        raw_sha = _sha(raw)
        wikidata_files.append({"name": f"raw/{qid}.json", "sha256": raw_sha, "url": url})

        source_record_id = f"2026/stadium:{city}"
        entity_id = _stable_id(
            "venue", f"openfootball-worldcup-json:{commit}:{source_record_id}"
        )
        of_ref = partial(
            _source_ref,
            "openfootball-worldcup-json",
            source_record_id,
            commit,
            actual,
        )
        wd_ref = partial(_source_ref, "wikidata", qid, revision, raw_sha)
        identifiers = [
            {
                "source_id": "openfootball-worldcup-json",
                "source_record_id": source_record_id,
                "source_revision": commit,
            }
        ]
        claims = [
            _claim(entity_id, "canonical_label", source["name"], of_ref("name"), language="en"),
            _claim(entity_id, "source_city", city, of_ref("city"), language="en"),
            _claim(entity_id, "latitude", source_coordinate[0], of_ref("coords")),
            _claim(entity_id, "longitude", source_coordinate[1], of_ref("coords")),
            _claim(entity_id, "capacity", int(source["capacity"]), of_ref("capacity")),
            _claim(entity_id, "source_timezone_offset", source["timezone"], of_ref("timezone")),
        ]
        if link_status == "accepted":
            identifiers.append(
                {"source_id": "wikidata", "source_record_id": qid, "source_revision": revision}
            )
            claims.extend(
                [
                    _claim(
                        entity_id,
                        "aliases",
                        sorted(labels | aliases),
                        wd_ref("labels-and-aliases"),
                    ),
                    _claim(
                        entity_id,
                        "wikidata_coordinate_discrepancy_km",
                        round(discrepancy_km, 3),
                        wd_ref("P625"),
                    ),
                ]
            )
        venue_entities.append(
            {
                "entity_id": entity_id,
                "entity_kind": "venue",
                "canonical_label": str(source["name"]),
                "resolution_status": "resolved",
                "identifiers": identifiers,
                "claims": claims,
                "supersedes": None,
            }
        )
        for match_city in reviewed["match_city_aliases"]:
            assignments.append(
                {
                    "source_id": "openfootball-worldcup-json",
                    "source_revision": commit,
                    "source_city": city,
                    "match_city": match_city,
                    "match_country": reviewed["match_country"],
                    "competition": "FIFA World Cup",
                    "valid_from": "2026-06-11",
                    "valid_to": "2026-07-19",
                    "allowed_match_venue_source_ids": [
                        "martj42-international-results",
                        "openfootball-worldcup-json"
                    ],
                    "venue_entity_id": entity_id,
                    "source_record_id": source_record_id,
                    "wikidata_link_status": link_status,
                    "wikidata_candidate_qid": qid,
                    "conflict_reason": (
                        reviewed.get("conflict_reason")
                        if link_status == "conflicting"
                        else None
                    ),
                }
            )

    wikidata_manifest = {
        "source_id": "wikidata",
        "license": "CC0-1.0",
        "upstream_ref": "entity-revisions:" + ",".join(
            f"{item['wikidata_qid']}@{item['wikidata_revision']}" for item in allowlist["venues"]
        ),
        "retrieved_at_utc": RETRIEVED_AT,
        "url": "https://www.wikidata.org/wiki/Special:EntityData",
        "files": sorted(wikidata_files, key=lambda item: item["name"]),
    }
    _write_json(wikidata_pack / "manifest.json", wikidata_manifest)
    _register_pack(wikidata_pack, wikidata_manifest)
    _write_json(
        ROOT / "data/context/venue_entities.json",
        {
            "schema_version": "0.1.0",
            "context_pack_version": "2026.07.15.1",
            "entities": sorted(venue_entities, key=lambda item: item["entity_id"]),
        },
    )
    _write_json(
        ROOT / "data/context/venue_assignments.json",
        {
            "schema_version": "0.1.0",
            "source_id": "openfootball-worldcup-json",
            "source_revision": commit,
            "assignments": sorted(
                assignments,
                key=lambda item: (item["match_country"], item["match_city"]),
            ),
        },
    )
    print(f"venue context: {len(venue_entities)} reviewed venues; source conflicts clean")


if __name__ == "__main__":
    main()
