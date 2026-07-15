#!/usr/bin/env python3
"""Build pinned GeoNames/Natural Earth packs and compact runtime side tables.

The network is only used by this explicit maintainer command. Runtime reads the
committed, derived JSON files and never calls a geocoding or map service. Every
download is pinned by an expected sha256 before it can enter a source pack.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import unicodedata
import urllib.request
from pathlib import Path
from typing import Any
from zipfile import ZipFile

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RETRIEVED_AT = "2026-07-15T07:57:00Z"

GEONAMES_DATE = "2026-07-15"
GEONAMES_FILES = {
    "cities15000.zip": (
        "https://download.geonames.org/export/dump/cities15000.zip",
        "14755b0a430501a5549c29c74d60c70834186be1cc13f4e46a74bee1b00aba38",
    ),
    "countryInfo.txt": (
        "https://download.geonames.org/export/dump/countryInfo.txt",
        "93bafc525813f22e4711ff9ed6d626343094ce48c26388dc7c49189b3d7d5512",
    ),
    "timeZones.txt": (
        "https://download.geonames.org/export/dump/timeZones.txt",
        "ea6f8bdcc259c21c562e8f7e7e0b0457cb89403bed60c76aac49ccee9a9ed18c",
    ),
    "readme.txt": (
        "https://download.geonames.org/export/dump/readme.txt",
        "b1957379b6c1242c700c98ac9a8aa0a09f56c3c0a50ee72175527005f48ef2c5",
    ),
}

NATURAL_EARTH_VERSION = "5.1.1"
NATURAL_EARTH_COMMIT = "9380cca83db5f9aef52d5e762765100745f84b27"
NATURAL_EARTH_FILES = {
    "ne_110m_admin_0_countries.geojson": (
        "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
        f"v{NATURAL_EARTH_VERSION}/geojson/ne_110m_admin_0_countries.geojson",
        "6866c877d39cba9c357620878839b336d569f8c662d3cfab4cb1dbe2d39c977f",
    ),
    "LICENSE.md": (
        "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
        f"v{NATURAL_EARTH_VERSION}/LICENSE.md",
        "2631b5b39b6d1acc56de75235109b5af2dbb4b0ac5a127b6f06185977247fd4b",
    ),
}

# Historical venue-country labels in martj42 are classification context, not
# team identity. Lists are used only when a former country spans successors;
# resolution still requires an exact normalized city name inside one candidate.
COUNTRY_CODE_ALIASES: dict[str, tuple[str, ...]] = {
    "alderney": ("GG",),
    "belgian congo": ("CD",),
    "bohemia": ("CZ",),
    "bohemia and moravia": ("CZ",),
    "bonaire": ("BQ",),
    "british guiana": ("GY",),
    "burma": ("MM",),
    "cape verde": ("CV",),
    "ceylon": ("LK",),
    "congo": ("CG",),
    "congo-kinshasa": ("CD",),
    "czech republic": ("CZ",),
    "czechoslovakia": ("CZ", "SK"),
    "dahomey": ("BJ",),
    "dr congo": ("CD",),
    "dutch guyana": ("SR",),
    "east timor": ("TL",),
    "eire": ("IE",),
    "england": ("GB",),
    "faroe islands": ("FO",),
    "fr yugoslavia": ("RS", "ME", "XK"),
    "french somaliland": ("DJ",),
    "german dr": ("DE",),
    "gold coast": ("GH",),
    "hong kong": ("HK",),
    "irish free state": ("IE",),
    "ivory coast": ("CI",),
    "kosovo": ("XK",),
    "macau": ("MO",),
    "macedonia": ("MK",),
    "malaya": ("MY",),
    "netherlands": ("NL",),
    "new hebrides": ("VU",),
    "north korea": ("KP",),
    "north vietnam": ("VN",),
    "northern cyprus": ("CY",),
    "northern ireland": ("GB",),
    "northern rhodesia": ("ZM",),
    "nyasaland": ("MW",),
    "portuguese guinea": ("GW",),
    "republic of ireland": ("IE",),
    "saarland": ("DE",),
    "scotland": ("GB",),
    "serbia and montenegro": ("RS", "ME"),
    "south korea": ("KR",),
    "southern rhodesia": ("ZW",),
    "soviet union": (
        "RU",
        "UA",
        "BY",
        "GE",
        "AM",
        "AZ",
        "KZ",
        "KG",
        "UZ",
        "TJ",
        "TM",
        "MD",
        "LV",
        "LT",
        "EE",
    ),
    "swaziland": ("SZ",),
    "syria": ("SY",),
    "tahiti": ("PF",),
    "taiwan": ("TW",),
    "tanganyika": ("TZ",),
    "tanzania": ("TZ",),
    "timor-leste": ("TL",),
    "turkey": ("TR",),
    "united states": ("US",),
    "united states virgin islands": ("VI",),
    "upper volta": ("BF",),
    "venezuela": ("VE",),
    "vietnam republic": ("VN",),
    "wales": ("GB",),
    "western samoa": ("WS",),
    "yemen ar": ("YE",),
    "yemen dpr": ("YE",),
    "yugoslavia": ("RS", "HR", "BA", "SI", "MK", "ME", "XK"),
    "zaire": ("CD",),
    "zanzibar": ("TZ",),
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _stable_id(kind: str, source_key: str) -> str:
    return f"{kind}_{hashlib.sha256(source_key.encode('utf-8')).hexdigest()[:16]}"


def _norm(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", str(value))
    plain = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(plain.casefold().replace("’", "'").split())


def _fetch(name: str, url: str, expected: str, cache_dir: Path | None) -> bytes:
    cached = cache_dir / name if cache_dir is not None else None
    data = (
        cached.read_bytes()
        if cached is not None and cached.is_file()
        else urllib.request.urlopen(url).read()
    )  # noqa: S310
    actual = _sha(data)
    if actual != expected:
        raise ValueError(f"{name}: sha256 drift; expected {expected}, got {actual}")
    return data


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _build_pack(
    *,
    directory: Path,
    files: dict[str, tuple[str, str]],
    source_id: str,
    license_id: str,
    upstream_ref: str,
    url: str,
    cache_dir: Path | None,
) -> dict[str, Any]:
    directory.mkdir(parents=True, exist_ok=True)
    entries = []
    for name, (source_url, expected) in files.items():
        data = _fetch(
            name
            if source_id == "geonames"
            else ("NATURAL_EARTH_LICENSE.md" if name == "LICENSE.md" else name),
            source_url,
            expected,
            cache_dir,
        )
        (directory / name).write_bytes(data)
        entries.append({"name": name, "sha256": expected, "url": source_url})
    manifest = {
        "source_id": source_id,
        "license": license_id,
        "upstream_ref": upstream_ref,
        "retrieved_at_utc": RETRIEVED_AT,
        "url": url,
        "files": entries,
    }
    _write_json(directory / "manifest.json", manifest)
    return manifest


def _country_codes(country_info: Path) -> dict[str, tuple[str, ...]]:
    result: dict[str, tuple[str, ...]] = dict(COUNTRY_CODE_ALIASES)
    for line in country_info.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        code, name = parts[0], parts[4].strip()
        result.setdefault(_norm(name), (code,))
    return result


def _city_candidates(zip_path: Path) -> dict[tuple[str, str], list[dict[str, Any]]]:
    by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}
    with ZipFile(zip_path) as archive:
        lines = archive.read("cities15000.txt").decode("utf-8").splitlines()
    for line in lines:
        parts = line.split("\t")
        names: dict[str, set[str]] = {}
        for name, kind in ((parts[1], "primary"), (parts[2], "ascii")):
            if name:
                names.setdefault(_norm(name), set()).add(kind)
        for name in parts[3].split(","):
            if name:
                names.setdefault(_norm(name), set()).add("alternate")
        record = {
            "geoname_id": int(parts[0]),
            "name": parts[1],
            "latitude": float(parts[4]),
            "longitude": float(parts[5]),
            "country_code": parts[8],
            "population": int(parts[14] or 0),
            "elevation_m": int(parts[15]) if parts[15] else (int(parts[16]) if parts[16] else None),
            "elevation_source": "survey" if parts[15] else ("dem" if parts[16] else None),
            "timezone": parts[17] or None,
            "modified": parts[18],
        }
        for name, match_kinds in names.items():
            by_key.setdefault((record["country_code"], name), []).append(
                {**record, "match_kinds": sorted(match_kinds)}
            )
    return by_key


def _review_lookup(path: Path) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    result: dict[str, dict[str, Any]] = {}
    for review in payload.get("resolutions", []):
        if review.get("decision") != "accepted":
            continue
        key = str(review.get("source_record_id", ""))
        if key in result:
            raise ValueError(f"{path}: duplicate accepted resolution for {key}")
        result[key] = review
    return result


def _derive_places(geonames_dir: Path, output_dir: Path) -> dict[str, Any]:
    index = pd.read_parquet(ROOT / "data/index/matches_index.parquet", columns=["city", "country"])
    pairs = (
        index[["city", "country"]]
        .dropna()
        .drop_duplicates()
        .sort_values(["country", "city"], kind="mergesort")
    )
    codes = _country_codes(geonames_dir / "countryInfo.txt")
    candidates = _city_candidates(geonames_dir / "cities15000.zip")
    places: dict[str, Any] = {}
    resolutions: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    ambiguous_pairs = 0
    alias_pending_pairs = 0
    reviews = _review_lookup(ROOT / "data/context/place_alias_reviews.json")
    raw_sha = GEONAMES_FILES["cities15000.zip"][1]
    for row in pairs.itertuples(index=False):
        city, country = str(row.city), str(row.country)
        options: dict[int, dict[str, Any]] = {}
        for code in codes.get(_norm(country), ()):
            for candidate in candidates.get((code, _norm(city)), []):
                options[candidate["geoname_id"]] = candidate
        key = f"{_norm(country)}|{_norm(city)}"
        lookup_id = f"lookup:{key}"
        candidate_ids = sorted(
            _stable_id("place", f"geonames:{item['geoname_id']}") for item in options.values()
        )
        review = reviews.get(lookup_id)
        selected: dict[str, Any] | None = None
        decision = "unresolved"
        rationale = "No exact GeoNames candidate in the audited country scope."
        if len(options) > 1:
            ambiguous_pairs += 1
            decision = "ambiguous"
            rationale = "Multiple exact GeoNames candidates require a checked-in review."
        elif len(options) == 1:
            candidate = next(iter(options.values()))
            candidate_id = _stable_id("place", f"geonames:{candidate['geoname_id']}")
            if "primary" in candidate["match_kinds"]:
                selected = candidate
                rationale = "Unique exact match to the GeoNames primary name."
            elif review is not None and review.get("resolved_entity_id") == candidate_id:
                selected = candidate
                decision = "accepted"
                rationale = str(review["rationale"])
            else:
                alias_pending_pairs += 1
                rationale = "Exact GeoNames alias/ascii match awaits a checked-in manual review."
        if review is not None and len(options) > 1:
            resolved_id = str(review.get("resolved_entity_id"))
            selected = next(
                (
                    item
                    for item in options.values()
                    if _stable_id("place", f"geonames:{item['geoname_id']}") == resolved_id
                ),
                None,
            )
            if selected is None:
                raise ValueError(f"review {lookup_id} selects an entity outside its candidates")
            decision = "accepted"
            rationale = str(review["rationale"])
        if selected is None:
            unresolved.append(
                {
                    "city": city,
                    "country": country,
                    "reason": decision,
                    "candidate_entity_ids": candidate_ids,
                }
            )
            resolutions.append(
                {
                    "resolution_id": _stable_id("ctxr", lookup_id).replace("ctxr_", "ctxr_"),
                    "source_id": "geonames",
                    "source_record_id": lookup_id,
                    "entity_kind": "place",
                    "observed_label": city,
                    "scope": {
                        "country": country,
                        "competition_id": None,
                        "valid_from": None,
                        "valid_to": None,
                    },
                    "candidate_entity_ids": candidate_ids,
                    "decision": decision,
                    "resolved_entity_id": None,
                    "reviewed_by": None,
                    "reviewed_at_utc": None,
                    "rationale": rationale,
                }
            )
            continue
        entity_id = _stable_id("place", f"geonames:{selected['geoname_id']}")
        places[key] = {
            "city": city,
            "country": country,
            "entity_id": entity_id,
            "resolution_status": "resolved",
            "source_id": "geonames",
            "source_revision": GEONAMES_DATE,
            "snapshot_sha256": raw_sha,
            **{
                field: selected[field]
                for field in (
                    "geoname_id",
                    "name",
                    "latitude",
                    "longitude",
                    "country_code",
                    "elevation_m",
                    "elevation_source",
                    "timezone",
                    "modified",
                )
            },
        }
    _write_json(output_dir / "places.json", places)
    context_dir = ROOT / "data/context"
    # Place identities and their field provenance live in the compact lookup
    # itself. Do not duplicate all claims into a second multi-megabyte runtime
    # registry; venue entities need richer cross-source records and remain
    # separate under data/context.
    (context_dir / "geo_entities.json").unlink(missing_ok=True)
    _write_json(
        context_dir / "place_resolutions.json",
        {"schema_version": "0.1.0", "resolutions": resolutions},
    )
    meta = {
        "schema_version": "0.1.0",
        "source_id": "geonames",
        "source_pack": geonames_dir.relative_to(ROOT).as_posix(),
        "source_dump_date": GEONAMES_DATE,
        "attribution": "Data from GeoNames (geonames.org), CC BY 4.0.",
        "matching": "unique exact GeoNames primary name, or an explicit checked-in resolution",
        "requested_pairs": int(len(pairs)),
        "resolved_pairs": len(places),
        "unresolved_pairs": len(unresolved),
        "ambiguous_pairs": ambiguous_pairs,
        "alias_pending_pairs": alias_pending_pairs,
        "manual_review_count": len(reviews),
        "unresolved": unresolved,
        "places_sha256": _sha((output_dir / "places.json").read_bytes()),
    }
    _write_json(output_dir / "places.meta.json", meta)
    return meta


def _derive_world(ne_dir: Path, output_dir: Path) -> dict[str, Any]:
    raw = json.loads((ne_dir / "ne_110m_admin_0_countries.geojson").read_text(encoding="utf-8"))
    features = []
    for feature in raw["features"]:
        props = feature.get("properties") or {}
        features.append(
            {
                "type": "Feature",
                "properties": {"name": props.get("NAME"), "iso_a2": props.get("ISO_A2")},
                "geometry": feature["geometry"],
            }
        )
    world = {
        "type": "FeatureCollection",
        "source_id": "natural-earth",
        "version": NATURAL_EARTH_VERSION,
        "attribution": "Made with Natural Earth.",
        "features": features,
    }
    _write_json(output_dir / "world_110m.geojson", world)
    return {
        "feature_count": len(features),
        "sha256": _sha((output_dir / "world_110m.geojson").read_bytes()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cache-dir", type=Path, help="optional directory containing pinned downloads"
    )
    parser.add_argument(
        "--derive-only",
        action="store_true",
        help="reuse the immutable on-disk source packs and rebuild only compact side tables",
    )
    args = parser.parse_args()
    geonames_dir = ROOT / "packs" / f"geonames-{GEONAMES_DATE}"
    ne_dir = ROOT / "packs" / f"natural-earth-{NATURAL_EARTH_VERSION}"
    if args.derive_only:
        geonames = json.loads((geonames_dir / "manifest.json").read_text(encoding="utf-8"))
        natural_earth = json.loads((ne_dir / "manifest.json").read_text(encoding="utf-8"))
    else:
        geonames = _build_pack(
            directory=geonames_dir,
            files=GEONAMES_FILES,
            source_id="geonames",
            license_id="CC-BY-4.0",
            upstream_ref=GEONAMES_DATE,
            url="https://download.geonames.org/export/dump/",
            cache_dir=args.cache_dir,
        )
        natural_earth = _build_pack(
            directory=ne_dir,
            files=NATURAL_EARTH_FILES,
            source_id="natural-earth",
            license_id="PUBLIC-DOMAIN",
            upstream_ref=f"v{NATURAL_EARTH_VERSION}@{NATURAL_EARTH_COMMIT}",
            url="https://github.com/nvkelso/natural-earth-vector",
            cache_dir=args.cache_dir,
        )
    registry_path = ROOT / "packs/enrichment.json"
    preserved = []
    if registry_path.is_file():
        current = json.loads(registry_path.read_text(encoding="utf-8"))
        preserved = [
            item
            for item in current.get("snapshots", [])
            if item.get("source_id") not in {"geonames", "natural-earth"}
        ]
    registry = {
        "schema_version": "0.1.0",
        "snapshots": sorted(
            [
            {
                "pack": geonames_dir.relative_to(ROOT).as_posix(),
                "source_id": geonames["source_id"],
                "upstream_ref": geonames["upstream_ref"],
                "retrieved_at_utc": RETRIEVED_AT,
                "manifest_sha256": _sha((geonames_dir / "manifest.json").read_bytes()),
            },
            {
                "pack": ne_dir.relative_to(ROOT).as_posix(),
                "source_id": natural_earth["source_id"],
                "upstream_ref": natural_earth["upstream_ref"],
                "retrieved_at_utc": RETRIEVED_AT,
                "manifest_sha256": _sha((ne_dir / "manifest.json").read_bytes()),
            },
            *preserved,
            ],
            key=lambda item: str(item["pack"]),
        ),
    }
    _write_json(registry_path, registry)
    output_dir = ROOT / "data/enrichment"
    places_meta = _derive_places(geonames_dir, output_dir)
    world_meta = _derive_world(ne_dir, output_dir)
    _write_json(
        output_dir / "manifest.json",
        {
            "schema_version": "0.1.0",
            "places": places_meta,
            "world": world_meta,
        },
    )
    coverage = f"{places_meta['resolved_pairs']}/{places_meta['requested_pairs']}"
    print(
        f"geo enrichment: {coverage} city-country pairs; "
        f"{world_meta['feature_count']} map features"
    )


if __name__ == "__main__":
    main()
