#!/usr/bin/env python3
"""Build club home-ground venue context, cross-checked against Wikidata.

An explicit maintainer build command; the installed application never contacts
either upstream. It extends the World Cup venue lane in
``scripts/build_venue_context.py`` to club fixtures, and keeps that lane's rule:
a pinned CC0 source states the fact and Wikidata only corroborates it.

* PRIMARY: ``openfootball/clubs`` (CC0) states a club's home ground and city.
* CORROBORATION: the club's Wikidata entity must independently name the same
  ground through P115 (home venue), and that ground must sit in the league's
  country. Capacity and coordinates are then read from the ground's entity,
  pinned to the exact revision fetched.

Disagreement fails closed. openfootball is not maintained in step with reality —
it still has Tottenham at White Hart Lane and West Ham at the Boleyn Ground —
so a club whose two sources disagree yields NO assignment and the venue stays
``unknown`` rather than displaying a ground the club left years ago. Every
outcome, accepted or rejected, is written to the review artifact so the rejects
are visible rather than silently missing.

The cross-check IS the review: ``reviewed_by`` names this method and its
version, not a person, and the resulting allowlist records the exact Wikidata
revision each decision was made against.

Usage: python scripts/build_club_venue_context.py
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))

from scripts.openfootball_clubs import ClubGround, parse_clubs_txt  # noqa: E402

REVIEW_METHOD = "automated-openfootball-wikidata-cross-check-v1"
RETRIEVED_AT = "2026-07-29T00:00:00Z"
USER_AGENT = "Golavo-maintainer/club-venues (https://github.com/udhawan97/Golavo)"
CLUBS_REPO = "https://github.com/openfootball/clubs"
CLUBS_REF = "master"
SOURCE_ID = "openfootball-clubs"
# The club lane owns its own Wikidata pack. build_venue_context.py rewrites
# wikidata-context-2026-07-15's manifest from its own allowlist on every run, so
# raw files written there by this builder would be orphaned — present on disk and
# declared by nobody — the next time the World Cup lane was rebuilt.
WIKIDATA_PACK = ROOT / "packs" / "wikidata-club-venues-2026-07-29"
ALLOWLIST_PATH = ROOT / "data/context/club_venue_allowlist.json"
ENTITIES_PATH = ROOT / "data/context/venue_entities.json"
ASSIGNMENTS_PATH = ROOT / "data/context/venue_assignments.json"
CONTEXT_PACK_VERSION = "2026.08.21.1"

# The season the assignment is verified for. A ground is only claimed for the
# window it was cross-checked in — clubs move, and a 2011 fixture must not
# inherit a 2026 ground.
VALID_FROM = "2026-08-01"
VALID_TO = "2027-06-30"

# league code -> (file in openfootball/clubs, indexed competition, match country,
#                 accepted Wikidata country QIDs for a ground in that league)
LEAGUES: dict[str, tuple[str, str, str, frozenset[str]]] = {
    "en.1": (
        "europe/england/eng.clubs.txt",
        "English Premier League",
        "England",
        # Grounds in England are tagged as the United Kingdom about as often as
        # England itself; both are the same claim about the same place.
        frozenset({"Q21", "Q145"}),
    ),
    "de.1": ("europe/germany/de.clubs.txt", "Bundesliga", "Germany", frozenset({"Q183"})),
    "es.1": ("europe/spain/es.clubs.txt", "La Liga", "Spain", frozenset({"Q29"})),
    "it.1": ("europe/italy/it.clubs.txt", "Serie A", "Italy", frozenset({"Q38"})),
    "fr.1": ("europe/france/fr.clubs.txt", "Ligue 1", "France", frozenset({"Q142"})),
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _stable_id(kind: str, source_key: str) -> str:
    return f"{kind}_{hashlib.sha256(source_key.encode('utf-8')).hexdigest()[:16]}"


def _claim_id(entity_id: str, field: str) -> str:
    return f"ctxc_{hashlib.sha256(f'{entity_id}:{field}'.encode()).hexdigest()[:16]}"


FOOTBALL_CLUB_QID = "Q476028"


def _norm(value: str) -> str:
    """Casefold and drop every non-alphanumeric character.

    Two names that differ only in typography are the same claim: upstream writes
    "Rheinenergiestadion" where Wikidata writes "RheinEnergie Stadion", and
    "Borussia-Park" against "Borussia Park". Squashing separators accepts those
    and nothing else — "White Hart Lane" still does not equal "Tottenham Hotspur
    Stadium", which is the disagreement this check exists to catch.
    """
    return "".join(
        character
        for character in str(value).casefold().replace("’", "'")
        if character.isalnum()
    )


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


def _current_home_venue(entity: dict[str, Any]) -> str | None:
    """The club's home venue TODAY, from P115's qualified statement history.

    P115 is not a single value: Bayern's entity lists the Grünwalder Stadion, the
    Olympiastadion and the Allianz Arena in that order, so reading the first
    statement reports a ground the club left in 1972. A statement carrying an end
    time (P582) is a former ground and is skipped; among the rest the latest
    start time (P580) wins, and a preferred-rank statement beats a normal one.
    """
    best: tuple[int, str, str] | None = None
    for statement in entity.get("claims", {}).get("P115", []):
        snak = statement.get("mainsnak", {})
        if snak.get("snaktype") != "value":
            continue
        qid = str(snak.get("datavalue", {}).get("value", {}).get("id") or "")
        if not qid:
            continue
        qualifiers = statement.get("qualifiers", {})
        if qualifiers.get("P582"):
            continue
        started = ""
        for qualifier in qualifiers.get("P580", []):
            value = qualifier.get("datavalue", {}).get("value", {})
            started = max(started, str(value.get("time") or ""))
        rank = 1 if statement.get("rank") == "preferred" else 0
        candidate = (rank, started, qid)
        if best is None or candidate[:2] > best[:2]:
            best = candidate
    return best[2] if best else None


def _labels_and_aliases(entity: dict[str, Any]) -> set[str]:
    english = entity.get("labels", {}).get("en")
    names = {str(english["value"])} if isinstance(english, dict) and english.get("value") else set()
    names |= {
        str(value["value"])
        for value in entity.get("aliases", {}).get("en", [])
        if isinstance(value, dict) and value.get("value")
    }
    return names


def _search(term: str, limit: int = 6) -> list[str]:
    query = urllib.parse.urlencode(
        {
            "action": "wbsearchentities",
            "search": term,
            "language": "en",
            "format": "json",
            "type": "item",
            "limit": limit,
        }
    )
    payload = json.loads(_fetch(f"https://www.wikidata.org/w/api.php?{query}"))
    return [str(item["id"]) for item in payload.get("search", [])]


_ENTITY_CACHE: dict[str, tuple[dict[str, Any], bytes]] = {}


def _entity(qid: str) -> tuple[dict[str, Any], bytes]:
    if qid in _ENTITY_CACHE:
        return _ENTITY_CACHE[qid]
    raw = _fetch(f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json")
    entity = json.loads(raw).get("entities", {}).get(qid) or {}
    _ENTITY_CACHE[qid] = (entity, raw)
    time.sleep(0.1)  # courtesy rate limit; this is a maintainer build, not a hot path
    return entity, raw


def _home_venue(club_name: str) -> tuple[str, dict[str, Any]] | None:
    """The searched club entity's home venue (P115), and the club entity itself.

    Candidates must be association football clubs, and one whose own name matches
    the pinned club exactly is preferred over a merely plausible hit. Without
    both rules a search for "Bayern München" resolves to the reserve side and
    reports its home as the Grünwalder Stadion.
    """
    target = _norm(club_name)
    fallback: tuple[str, dict[str, Any]] | None = None
    for qid in _search(club_name):
        entity, _ = _entity(qid)
        kinds = {
            str(value.get("id"))
            for value in _wikidata_values(entity, "P31")
            if isinstance(value, dict)
        }
        if FOOTBALL_CLUB_QID not in kinds:
            continue
        venue_qid = _current_home_venue(entity)
        if not venue_qid:
            continue
        if target in {_norm(name) for name in _labels_and_aliases(entity)}:
            return venue_qid, entity
        if fallback is None:
            fallback = (venue_qid, entity)
    return fallback


def _capacity(entity: dict[str, Any]) -> int | None:
    for value in _wikidata_values(entity, "P1083"):
        try:
            return int(float(str(value.get("amount", "")).lstrip("+")))
        except (TypeError, ValueError):
            continue
    return None


def _coordinate(entity: dict[str, Any]) -> tuple[float, float] | None:
    for value in _wikidata_values(entity, "P625"):
        try:
            return float(value["latitude"]), float(value["longitude"])
        except (KeyError, TypeError, ValueError):
            continue
    return None


def _review(club: ClubGround, league_code: str, countries: frozenset[str]) -> dict[str, Any]:
    """Cross-check one club's pinned ground against Wikidata. Never raises."""
    verdict: dict[str, Any] = {
        "league_code": league_code,
        "team": club.team,
        "source_club_name": club.name,
        "source_ground": club.ground,
        "source_city": club.city,
        "status": "rejected",
        "reason": None,
        "club_qid": None,
        "venue_qid": None,
        "venue_revision": None,
        "capacity": None,
        "latitude": None,
        "longitude": None,
    }
    try:
        found = _home_venue(club.name)
    except (OSError, ValueError) as exc:
        verdict["reason"] = f"wikidata-unreachable: {exc}"
        return verdict
    if found is None:
        verdict["reason"] = "no-wikidata-entity-declares-a-home-venue"
        return verdict
    venue_qid, club_entity = found
    verdict["club_qid"] = str(club_entity.get("id") or "")
    verdict["venue_qid"] = venue_qid
    venue_entity, _ = _entity(venue_qid)
    if not venue_entity:
        verdict["reason"] = "home-venue-entity-not-retrievable"
        return verdict
    verdict["venue_revision"] = str(venue_entity.get("lastrevid") or "")
    names = {_norm(name) for name in _labels_and_aliases(venue_entity)}
    if _norm(club.ground) not in names:
        verdict["reason"] = (
            f"pinned ground {club.ground!r} is absent from the Wikidata home venue's "
            f"labels and aliases ({venue_qid})"
        )
        return verdict
    venue_countries = {
        str(value.get("id"))
        for value in _wikidata_values(venue_entity, "P17")
        if isinstance(value, dict)
    }
    if not venue_countries & countries:
        verdict["reason"] = f"home venue country {sorted(venue_countries)} is not the league's"
        return verdict
    coordinate = _coordinate(venue_entity)
    if coordinate is None:
        verdict["reason"] = "home venue has no coordinate to corroborate the link"
        return verdict
    verdict.update(
        status="accepted",
        latitude=coordinate[0],
        longitude=coordinate[1],
        capacity=_capacity(venue_entity),
    )
    return verdict


def _pin_clubs_pack() -> tuple[Path, str, dict[str, tuple[str, str]]]:
    """Vendor the pinned club files and return (pack, commit, {league: (text, sha)})."""
    commit = json.loads(
        _fetch(f"https://api.github.com/repos/openfootball/clubs/commits/{CLUBS_REF}")
    )["sha"]
    pack = ROOT / "packs" / f"openfootball-clubs-{commit[:12]}"
    pack.mkdir(parents=True, exist_ok=True)
    files: list[dict[str, str]] = []
    parsed: dict[str, tuple[str, str]] = {}
    for league_code, (path, *_rest) in LEAGUES.items():
        payload = _fetch(f"https://raw.githubusercontent.com/openfootball/clubs/{commit}/{path}")
        name = path.rsplit("/", 1)[-1]
        (pack / name).write_bytes(payload)
        digest = _sha(payload)
        files.append({"name": name, "sha256": digest, "source_path": path})
        parsed[league_code] = (payload.decode("utf-8"), digest)
    licence = _fetch(f"https://raw.githubusercontent.com/openfootball/clubs/{commit}/LICENSE.md")
    if b"CC0 1.0 Universal" not in licence:
        raise RuntimeError("openfootball/clubs LICENSE.md is no longer the expected CC0 text")
    (pack / "CC0-1.0.txt").write_bytes(licence)
    files.append({"name": "CC0-1.0.txt", "sha256": _sha(licence)})
    manifest = {
        "source_id": SOURCE_ID,
        "license": "CC0-1.0",
        "upstream_ref": commit,
        "retrieved_at_utc": RETRIEVED_AT,
        "url": CLUBS_REPO,
        "files": sorted(files, key=lambda item: item["name"]),
    }
    _write_json(pack / "manifest.json", manifest)
    registry_path = ROOT / "packs/enrichment.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    relative = pack.relative_to(ROOT).as_posix()
    entry = {
        "pack": relative,
        "source_id": SOURCE_ID,
        "upstream_ref": commit,
        "retrieved_at_utc": RETRIEVED_AT,
        "manifest_sha256": _sha((pack / "manifest.json").read_bytes()),
    }
    registry["snapshots"] = sorted(
        [*(item for item in registry["snapshots"] if item["pack"] != relative), entry],
        key=lambda item: item["pack"],
    )
    _write_json(registry_path, registry)
    return pack, commit, parsed


def _register_wikidata_pack(revisions: list[tuple[str, str]]) -> None:
    """Declare every raw entity this build pinned, and register the pack."""
    files = [
        {
            "name": f"raw/{qid}.json",
            "sha256": _sha((WIKIDATA_PACK / "raw" / f"{qid}.json").read_bytes()),
        }
        for qid, _revision in revisions
    ]
    manifest = {
        "source_id": "wikidata",
        "license": "CC0-1.0",
        "upstream_ref": "entity-revisions:"
        + ",".join(f"{qid}@{revision}" for qid, revision in revisions),
        "retrieved_at_utc": RETRIEVED_AT,
        "url": "https://www.wikidata.org/wiki/Special:EntityData",
        "files": sorted(files, key=lambda item: item["name"]),
    }
    _write_json(WIKIDATA_PACK / "manifest.json", manifest)
    registry_path = ROOT / "packs/enrichment.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    relative = WIKIDATA_PACK.relative_to(ROOT).as_posix()
    entry = {
        "pack": relative,
        "source_id": "wikidata",
        "upstream_ref": manifest["upstream_ref"],
        "retrieved_at_utc": RETRIEVED_AT,
        "manifest_sha256": _sha((WIKIDATA_PACK / "manifest.json").read_bytes()),
    }
    registry["snapshots"] = sorted(
        [*(item for item in registry["snapshots"] if item["pack"] != relative), entry],
        key=lambda item: item["pack"],
    )
    _write_json(registry_path, registry)


def _indexed_teams(competition: str) -> set[str]:
    """The clubs actually playing this competition in the assignment's window."""
    import pandas as pd

    frame = pd.read_parquet(ROOT / "data/index/matches_index.parquet")
    kickoff = pd.to_datetime(frame["kickoff_utc"], utc=True)
    season = frame.loc[
        frame["competition"].astype("string").eq(competition)
        & (kickoff >= f"{VALID_FROM}T00:00:00Z")
        & (kickoff <= f"{VALID_TO}T23:59:59Z")
    ]
    return {str(value) for value in season["home_team"].dropna().unique()}


def _records(
    club: ClubGround,
    verdict: dict[str, Any],
    *,
    commit: str,
    source_path: str,
    source_sha: str,
    raw_sha: str,
    competition: str,
    country: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """One accepted club's venue entity and its match assignment.

    Every claim cites the source that actually states it: the ground and city come
    from the pinned CC0 club file, the coordinate and capacity from the Wikidata
    revision that corroborated the link. The UI reads those per-claim sources and
    badges them separately, so a mixed-source venue stays legible.
    """
    venue_qid = str(verdict["venue_qid"])
    source_record_id = f"{source_path}:{club.name}"
    entity_id = _stable_id("venue", f"{SOURCE_ID}:{commit}:{source_record_id}")

    def ref(field: str, *, wikidata: bool = False) -> dict[str, Any]:
        return {
            "source_id": "wikidata" if wikidata else SOURCE_ID,
            "source_record_id": venue_qid if wikidata else source_record_id,
            "source_revision": str(verdict["venue_revision"]) if wikidata else commit,
            "snapshot_sha256": raw_sha if wikidata else source_sha,
            "retrieved_at_utc": RETRIEVED_AT,
            "field": field,
        }

    def claim(field: str, value: Any, source_ref: dict[str, Any]) -> dict[str, Any]:
        return {
            "claim_id": _claim_id(entity_id, field),
            "field": field,
            "value": value,
            "language": "en" if isinstance(value, str) else None,
            "precision": None,
            "source_refs": [source_ref],
        }

    claims = [
        claim("canonical_label", club.ground, ref("ground")),
        claim("source_city", club.city, ref("city")),
        claim("latitude", verdict["latitude"], ref("P625", wikidata=True)),
        claim("longitude", verdict["longitude"], ref("P625", wikidata=True)),
    ]
    if verdict["capacity"] is not None:
        claims.append(claim("capacity", int(verdict["capacity"]), ref("P1083", wikidata=True)))
    entity = {
        "entity_id": entity_id,
        "entity_kind": "venue",
        "canonical_label": club.ground,
        "resolution_status": "resolved",
        "identifiers": [
            {
                "source_id": SOURCE_ID,
                "source_record_id": source_record_id,
                "source_revision": commit,
            },
            {
                "source_id": "wikidata",
                "source_record_id": venue_qid,
                "source_revision": str(verdict["venue_revision"]),
            },
        ],
        "claims": claims,
        "supersedes": None,
    }
    assignment = {
        "source_id": SOURCE_ID,
        "source_revision": commit,
        "source_city": club.city,
        "match_home_team": club.team,
        "match_city": club.city,
        "match_country": country,
        "competition": competition,
        "valid_from": VALID_FROM,
        "valid_to": VALID_TO,
        "allowed_match_venue_source_ids": ["openfootball-football-json"],
        "venue_entity_id": entity_id,
        "source_record_id": source_record_id,
        "wikidata_link_status": "accepted",
        "wikidata_candidate_qid": venue_qid,
        "conflict_reason": None,
    }
    return entity, assignment


def main() -> int:
    pack, commit, sources = _pin_clubs_pack()
    verdicts: list[dict[str, Any]] = []
    entities: list[dict[str, Any]] = []
    assignments: list[dict[str, Any]] = []
    raw_dir = WIKIDATA_PACK / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    for league_code, (path, competition, country, countries) in LEAGUES.items():
        text, source_sha = sources[league_code]
        indexed = _indexed_teams(competition)
        clubs = [club for club in parse_clubs_txt(text, league_code=league_code)
                 if club.team in indexed]
        for club in clubs:
            verdict = _review(club, league_code, countries)
            verdict["competition"] = competition
            verdicts.append(verdict)
            print(
                f"  {competition[:18]:18s} {club.team:24s} "
                f"{verdict['status']:8s} {verdict['reason'] or club.ground}"
            )
            if verdict["status"] != "accepted":
                continue
            venue_qid = str(verdict["venue_qid"])
            _, raw = _entity(venue_qid)
            (raw_dir / f"{venue_qid}.json").write_bytes(raw)
            entity, assignment = _records(
                club,
                verdict,
                commit=commit,
                source_path=path,
                source_sha=source_sha,
                raw_sha=_sha(raw),
                competition=competition,
                country=country,
            )
            entities.append(entity)
            assignments.append(assignment)

    _register_wikidata_pack(
        sorted(
            {
                item["venue_qid"]: str(item["venue_revision"])
                for item in verdicts
                if item["status"] == "accepted"
            }.items()
        )
    )

    # Merge, never overwrite: the World Cup lane owns its own records in these
    # files, and so does the club home-city lane (build_club_home_cities.py),
    # which reads the same pinned pack under the same source_id. Entity ids are
    # kind-prefixed, so ownership is decided by prefix rather than by source —
    # filtering on source_id alone would silently delete every place_ record.
    existing_entities = json.loads(ENTITIES_PATH.read_text(encoding="utf-8"))
    existing_assignments = json.loads(ASSIGNMENTS_PATH.read_text(encoding="utf-8"))
    kept_entities = [
        item
        for item in existing_entities["entities"]
        if not (
            str(item["entity_id"]).startswith("venue_")
            and any(i.get("source_id") == SOURCE_ID for i in item.get("identifiers", []))
        )
    ]
    kept_assignments = [
        item
        for item in existing_assignments["assignments"]
        if not (
            str(item["venue_entity_id"]).startswith("venue_")
            and item.get("source_id") == SOURCE_ID
        )
    ]
    _write_json(
        ENTITIES_PATH,
        {
            "schema_version": existing_entities["schema_version"],
            "context_pack_version": CONTEXT_PACK_VERSION,
            "entities": sorted([*kept_entities, *entities], key=lambda item: item["entity_id"]),
        },
    )
    _write_json(
        ASSIGNMENTS_PATH,
        {
            **{k: v for k, v in existing_assignments.items() if k != "assignments"},
            "assignments": sorted(
                [*kept_assignments, *assignments],
                key=lambda item: (
                    item["match_country"],
                    item.get("match_home_team") or "",
                    item["match_city"],
                ),
            ),
        },
    )
    accepted = [item for item in verdicts if item["status"] == "accepted"]
    _write_json(
        ALLOWLIST_PATH,
        {
            "schema_version": "0.1.0",
            "reviewed_by": REVIEW_METHOD,
            "reviewed_at_utc": RETRIEVED_AT,
            "review_rule": (
                "openfootball/clubs states the ground; the club's Wikidata entity must name the "
                "same ground through P115 and place it in the league's country. Any disagreement "
                "is rejected and the venue stays unknown."
            ),
            "clubs_commit": commit,
            "clubs": sorted(verdicts, key=lambda item: (item["league_code"], item["team"])),
        },
    )
    print(
        f"\nclub venue context: {len(accepted)} accepted, "
        f"{len(verdicts) - len(accepted)} rejected, from {pack.name}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
