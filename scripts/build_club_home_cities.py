#!/usr/bin/env python3
"""Build club home-city context from the already-pinned CC0 club files.

Why a city lane exists at all
-----------------------------
The stadium lane (``scripts/build_club_venue_context.py``) needs a ground, and
``openfootball/clubs`` states no ground for any Spanish or Italian club — 0 of
them, against 89 of England's clubs. La Liga and Serie A therefore had no venue
assignment, and because a club match row carries no city of its own, no city,
no local kickoff and no travel either: two of the five top-flight leagues had
no match context whatsoever.

A city needs no ground. The same pinned CC0 file states one for 94 of the 96
clubs in the five 2026-27 schedules, so reading it on its own gives those clubs
a place while the stadium stays honestly unknown wherever the two sources that
must agree about it do not. A club whose city upstream omits — Elversberg — and
one upstream keeps in a file this pack does not carry — Monaco, in ``mc.txt`` —
yield nothing rather than a guess.

Ownership
---------
This lane owns the ``place`` entities in the shared context registry and the
assignments that point at them; the stadium lane owns the ``venue`` entities and
theirs. Entity ids are kind-prefixed, so neither rewrites the other's records.
A club that already has a stadium assignment is skipped here: that assignment
already states its city, and two assignments scoped to one match would make the
registry read as a conflict.

Offline by construction: it reads bytes already vendored in the pinned pack and
verifies each against that pack's manifest, so it never contacts upstream.

Usage: python scripts/build_club_home_cities.py [--check]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))

from scripts.openfootball_clubs import ClubCity, parse_club_cities  # noqa: E402

SOURCE_ID = "openfootball-clubs"
REVIEW_METHOD = "pinned-openfootball-club-city-read-v1"
# When the pack bytes were retrieved, which is what a source ref cites, and
# separately when this lane last read them. Both are fixed constants: a build
# that stamped the wall clock could never be checked for drift.
RETRIEVED_AT = "2026-07-29T00:00:00Z"
REVIEWED_AT = "2026-08-21T00:00:00Z"
CONTEXT_PACK_VERSION = "2026.08.21.1"
ENTITIES_PATH = ROOT / "data/context/venue_entities.json"
ASSIGNMENTS_PATH = ROOT / "data/context/venue_assignments.json"
ALLOWLIST_PATH = ROOT / "data/context/club_home_city_allowlist.json"

# The season this home city is claimed for. Clubs move, so a city is asserted
# only for the window it was read for — the same window the stadium lane uses.
VALID_FROM = "2026-08-01"
VALID_TO = "2027-06-30"

# league code -> (file in the pinned pack, its upstream path, indexed competition, country)
LEAGUES: dict[str, tuple[str, str, str, str]] = {
    "en.1": ("eng.clubs.txt", "europe/england/eng.clubs.txt", "English Premier League", "England"),
    "de.1": ("de.clubs.txt", "europe/germany/de.clubs.txt", "Bundesliga", "Germany"),
    "es.1": ("es.clubs.txt", "europe/spain/es.clubs.txt", "La Liga", "Spain"),
    "it.1": ("it.clubs.txt", "europe/italy/it.clubs.txt", "Serie A", "Italy"),
    "fr.1": ("fr.clubs.txt", "europe/france/fr.clubs.txt", "Ligue 1", "France"),
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _stable_id(kind: str, source_key: str) -> str:
    return f"{kind}_{hashlib.sha256(source_key.encode('utf-8')).hexdigest()[:16]}"


def _claim_id(entity_id: str, field: str) -> str:
    return f"ctxc_{hashlib.sha256(f'{entity_id}:{field}'.encode()).hexdigest()[:16]}"


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _pinned_pack() -> tuple[Path, str, dict[str, tuple[str, str]]]:
    """The vendored clubs pack, hash-verified, as {league: (text, file sha256)}.

    Every byte read here is already declared in the pack manifest, so a file that
    drifted from the bytes the pack was pinned at stops the build instead of
    quietly entering the context registry.
    """
    packs = sorted((ROOT / "packs").glob("openfootball-clubs-*"))
    if len(packs) != 1:
        raise SystemExit(f"expected exactly one pinned clubs pack, found {len(packs)}")
    pack = packs[0]
    manifest = json.loads((pack / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("source_id") != SOURCE_ID or manifest.get("license") != "CC0-1.0":
        raise SystemExit(f"{pack}: not the pinned CC0 openfootball/clubs pack")
    declared = {str(item["name"]): str(item["sha256"]) for item in manifest["files"]}
    parsed: dict[str, tuple[str, str]] = {}
    for league_code, (name, *_rest) in LEAGUES.items():
        payload = (pack / name).read_bytes()
        digest = _sha(payload)
        if declared.get(name) != digest:
            raise SystemExit(f"{pack}/{name}: sha256 disagrees with the pack manifest")
        parsed[league_code] = (payload.decode("utf-8"), digest)
    return pack, str(manifest["upstream_ref"]), parsed


def _indexed_teams_by_competition() -> dict[str, set[str]]:
    """Each competition's clubs in the assignment window, from one index read.

    Read once rather than per league: the index is 100k rows and this needs three
    of its 27 columns.
    """
    import pandas as pd

    frame = pd.read_parquet(
        ROOT / "data/index/matches_index.parquet",
        columns=["competition", "kickoff_utc", "home_team"],
    )
    kickoff = pd.to_datetime(frame["kickoff_utc"], utc=True)
    season = frame.loc[
        (kickoff >= f"{VALID_FROM}T00:00:00Z") & (kickoff <= f"{VALID_TO}T23:59:59Z")
    ]
    return {
        str(competition): {str(team) for team in rows["home_team"].dropna().unique()}
        for competition, rows in season.groupby(season["competition"].astype("string"))
    }


def _by_team(clubs: list[ClubCity]) -> tuple[dict[str, ClubCity], set[str]]:
    """Index clubs by every name upstream gives them, and name the collisions.

    A club's headline name is often not the index's canonical one — "Atalanta"
    against "Atalanta Bergamo" — so the alias block upstream prints beneath each
    club is read as its own statement that those names denote one club. Any key
    two clubs claim with different cities is dropped rather than guessed at.
    """
    lookup: dict[str, ClubCity] = {}
    ambiguous: set[str] = set()
    for club in clubs:
        for key in (club.team, *club.alias_teams):
            existing = lookup.get(key)
            if existing is not None and existing.city != club.city:
                ambiguous.add(key)
                continue
            lookup.setdefault(key, club)
    return lookup, ambiguous


def _records(
    club: ClubCity,
    team: str,
    *,
    commit: str,
    source_path: str,
    source_sha: str,
    competition: str,
    country: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """One club's home-city entity and the assignment that scopes it to a match."""
    source_record_id = f"{source_path}:{club.name}"
    entity_id = _stable_id("place", f"{SOURCE_ID}:{commit}:{source_record_id}")

    def ref(field: str) -> dict[str, Any]:
        return {
            "source_id": SOURCE_ID,
            "source_record_id": source_record_id,
            "source_revision": commit,
            "snapshot_sha256": source_sha,
            "retrieved_at_utc": RETRIEVED_AT,
            "field": field,
        }

    def claim(field: str, value: Any) -> dict[str, Any]:
        return {
            "claim_id": _claim_id(entity_id, field),
            "field": field,
            "value": value,
            "language": "en" if isinstance(value, str) else None,
            "precision": None,
            "source_refs": [ref("city")],
        }

    entity = {
        "entity_id": entity_id,
        "entity_kind": "place",
        "canonical_label": club.city,
        "resolution_status": "resolved",
        "identifiers": [
            {
                "source_id": SOURCE_ID,
                "source_record_id": source_record_id,
                "source_revision": commit,
            }
        ],
        "claims": [claim("canonical_label", club.city), claim("source_city", club.city)],
        "supersedes": None,
    }
    assignment = {
        "source_id": SOURCE_ID,
        "source_revision": commit,
        "source_city": club.city,
        "match_home_team": team,
        "match_city": club.city,
        "match_country": country,
        "competition": competition,
        "valid_from": VALID_FROM,
        "valid_to": VALID_TO,
        "allowed_match_venue_source_ids": ["openfootball-football-json"],
        "venue_entity_id": entity_id,
        "source_record_id": source_record_id,
        # No stadium is claimed here and none was cross-checked, so the Wikidata
        # link this lane never made stays unknown rather than borrowing an
        # "accepted" it did not earn.
        "wikidata_link_status": "unknown",
        "wikidata_candidate_qid": None,
        "conflict_reason": None,
    }
    return entity, assignment


def build(check_only: bool = False) -> int:
    pack, commit, sources = _pinned_pack()
    existing_assignments = json.loads(ASSIGNMENTS_PATH.read_text(encoding="utf-8"))
    existing_entities = json.loads(ENTITIES_PATH.read_text(encoding="utf-8"))
    with_stadium = {
        (str(item["competition"]), str(item["match_home_team"]))
        for item in existing_assignments["assignments"]
        if item.get("match_home_team") and str(item["venue_entity_id"]).startswith("venue_")
    }

    indexed_by_competition = _indexed_teams_by_competition()
    verdicts: list[dict[str, Any]] = []
    entities: list[dict[str, Any]] = []
    assignments: list[dict[str, Any]] = []
    for league_code, (_name, source_path, competition, country) in LEAGUES.items():
        text, source_sha = sources[league_code]
        lookup, ambiguous = _by_team(parse_club_cities(text, league_code=league_code))
        for team in sorted(indexed_by_competition.get(competition, set())):
            verdict: dict[str, Any] = {
                "league_code": league_code,
                "competition": competition,
                "team": team,
                "source_club_name": None,
                "city": None,
                "status": "rejected",
                "reason": None,
            }
            if (competition, team) in with_stadium:
                verdict.update(
                    status="skipped",
                    reason="a cross-checked stadium assignment already states this club's city",
                )
                verdicts.append(verdict)
                continue
            if team in ambiguous:
                verdict["reason"] = "two clubs upstream claim this name with different cities"
                verdicts.append(verdict)
                continue
            club = lookup.get(team)
            if club is None:
                verdict["reason"] = "no pinned club line states a home city for this club"
                verdicts.append(verdict)
                continue
            verdict.update(status="accepted", source_club_name=club.name, city=club.city)
            verdicts.append(verdict)
            entity, assignment = _records(
                club,
                team,
                commit=commit,
                source_path=source_path,
                source_sha=source_sha,
                competition=competition,
                country=country,
            )
            entities.append(entity)
            assignments.append(assignment)

    accepted = [item for item in verdicts if item["status"] == "accepted"]
    for competition in sorted({str(item["competition"]) for item in verdicts}):
        got = sum(1 for item in accepted if item["competition"] == competition)
        total = sum(1 for item in verdicts if item["competition"] == competition)
        skipped = sum(
            1
            for item in verdicts
            if item["competition"] == competition and item["status"] == "skipped"
        )
        print(f"  {competition:<24} +{got:>2} city-only / {total} clubs ({skipped} already staged)")

    # Merge, never overwrite: the stadium lane and the World Cup lane own the
    # venue_ records in these same files, and must survive this write untouched.
    kept_entities = [
        item for item in existing_entities["entities"]
        if not str(item["entity_id"]).startswith("place_")
    ]
    kept_assignments = [
        item for item in existing_assignments["assignments"]
        if not str(item["venue_entity_id"]).startswith("place_")
    ]
    next_entities = {
        # Carry unknown top-level keys forward, exactly as the assignments write
        # below does — enumerating them would silently drop the first field the
        # registry grows.
        **{k: v for k, v in existing_entities.items() if k != "entities"},
        "context_pack_version": CONTEXT_PACK_VERSION,
        "entities": sorted([*kept_entities, *entities], key=lambda item: item["entity_id"]),
    }
    next_assignments = {
        **{k: v for k, v in existing_assignments.items() if k != "assignments"},
        "assignments": sorted(
            [*kept_assignments, *assignments],
            key=lambda item: (
                item["match_country"],
                item.get("match_home_team") or "",
                item["match_city"],
            ),
        ),
    }
    allowlist = {
        "schema_version": "0.1.0",
        "reviewed_by": REVIEW_METHOD,
        "reviewed_at_utc": REVIEWED_AT,
        "review_rule": (
            "The pinned CC0 club file states the club's home city. It is read for the "
            "2026-27 window only, and only for a club whose stadium lane produced no "
            "assignment. A club whose pinned line states no city yields nothing."
        ),
        "clubs_commit": commit,
        "clubs_pack": pack.relative_to(ROOT).as_posix(),
        "clubs": sorted(verdicts, key=lambda item: (item["competition"], item["team"])),
    }
    if check_only:
        drift = 0
        for path, value in (
            (ENTITIES_PATH, next_entities),
            (ASSIGNMENTS_PATH, next_assignments),
            (ALLOWLIST_PATH, allowlist),
        ):
            current = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
            if current != value:
                print(f"DRIFT {path.relative_to(ROOT)}")
                drift += 1
        return drift
    _write_json(ENTITIES_PATH, next_entities)
    _write_json(ASSIGNMENTS_PATH, next_assignments)
    _write_json(ALLOWLIST_PATH, allowlist)
    print(f"club home cities: {len(accepted)} accepted over {len(LEAGUES)} leagues")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="report drift without writing")
    args = parser.parse_args()
    return build(check_only=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
