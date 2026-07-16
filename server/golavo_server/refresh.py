"""Pure builders for approved-source refresh candidates.

The runtime transport captures pinned martj42, World Cup, and genuinely
published current-season OpenFootball bytes. This module validates and combines
those snapshots into deterministic packs and a whole candidate index, then
rejects completed-evidence or sealed-fixture conflicts before activation.

It performs no network access and owns no process state: identical pinned input
bytes produce identical index bytes, so every parser, merge and safety rule stays
network-free testable. ``refresh_jobs`` owns orchestration and ``refresh_state``
owns immutable installation, atomic activation and rollback.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

from golavo_core.ingest.match_index import (
    INDEX_COLUMNS,
    MATCH_INDEX_SCHEMA_VERSION,
    build_match_index,
)

_CLUB_KIND = "club"
_INTERNATIONAL_KIND = "international"


class RefreshError(Exception):
    """A refresh could not produce a complete, consistent index."""


class RefreshConflict(RefreshError):
    """A valid candidate would rewrite or remove already-observed evidence."""

    def __init__(self, message: str, *, details: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message)
        self.details = details or []


def merge_refreshed_index(
    fresh_intl_pack: Path, bundled_index_path: Path, target_dir: Path
) -> Path:
    """Write a complete refreshed match index into ``target_dir``.

    Rebuilds the internationals index (rows + goalscorers/shootouts + aliases)
    from ``fresh_intl_pack`` straight into ``target_dir``, then splices in the
    club rows carried over verbatim from the bundled complete index at
    ``bundled_index_path``. The result is a single Parquet honouring the exact
    ``INDEX_COLUMNS`` contract, its match ids still unique across sources, and a
    meta sidecar whose digest matches the merged bytes. Deterministic: identical
    inputs yield byte-identical output.

    Raises ``RefreshError`` if the fresh pack is not an internationals source or
    if the merge would collide two sources' ids.
    """
    import pandas as pd

    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_index = target_dir / "matches_index.parquet"

    # 1. Fresh internationals index + its side tables/aliases, straight into
    #    target_dir. This is the only side that gains new fixtures upstream.
    build_match_index([Path(fresh_intl_pack)], target_index)
    intl = pd.read_parquet(target_index)
    if not (intl["source_kind"] == _INTERNATIONAL_KIND).all():
        raise RefreshError("fresh pack is not a pure internationals source; refusing to refresh")

    # 2. Carry the club history over from the bundled index, untouched — the
    #    frozen app bundles no club packs, so this is how it stays complete.
    bundled = pd.read_parquet(Path(bundled_index_path))
    club = bundled[bundled["source_kind"] == _CLUB_KIND]

    merged = (
        pd.concat([intl, club[INDEX_COLUMNS]], ignore_index=True)
        .sort_values(["kickoff_utc", "match_id"], kind="mergesort")
        .reset_index(drop=True)[INDEX_COLUMNS]
    )
    dups = merged["match_id"][merged["match_id"].duplicated(keep=False)]
    if not dups.empty:
        raise RefreshError(
            "match_id collision merging refreshed internationals with club "
            f"history: {sorted(dups.unique())[:10]}"
        )

    # 3. Overwrite the intl-only Parquet with the merged whole + honest meta.
    #    build_match_index already left the fresh internationals side tables and
    #    alias map in target_dir; those are intl-only, so the fresh copies stand.
    merged.to_parquet(target_index, index=False, engine="pyarrow", compression="zstd")
    meta = {
        "schema_version": MATCH_INDEX_SCHEMA_VERSION,
        "row_count": int(len(merged)),
        "parquet_sha256": hashlib.sha256(target_index.read_bytes()).hexdigest(),
        "refreshed": True,
        "internationals_pack": Path(fresh_intl_pack).name,
        "club_rows_from": Path(bundled_index_path).name,
    }
    (target_dir / "matches_index.meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return target_index


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_entry(path: Path, name: str | None = None) -> dict[str, str]:
    return {"name": name or path.name, "sha256": _sha256(path)}


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _copy_raw(raw_root: Path, source_id: str, ref: str, relative: str, target: Path) -> Path:
    source = Path(raw_root) / source_id / ref / relative
    if not source.is_file():
        raise RefreshError(f"raw snapshot is missing {source_id}/{ref}/{relative}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return target


def _drop_unresolved_identity_rows(results_path: Path) -> int:
    """Exclude only scoreless placeholders whose teams are not known yet.

    The immutable raw snapshot remains untouched. A missing date/tournament or
    any scored row with a missing team is malformed evidence and fails closed.
    """
    with Path(results_path).open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "date",
            "home_team",
            "away_team",
            "home_score",
            "away_score",
            "tournament",
        }
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise RefreshError("martj42 results.csv is missing required columns")
        rows = list(reader)

    kept: list[dict[str, str | None]] = []
    omitted = 0
    missing_tokens = {"", "NA"}
    for row in rows:
        date = (row.get("date") or "").strip()
        tournament = (row.get("tournament") or "").strip()
        home = (row.get("home_team") or "").strip()
        away = (row.get("away_team") or "").strip()
        scores = {
            (row.get("home_score") or "").strip(),
            (row.get("away_score") or "").strip(),
        }
        if not date or not tournament:
            raise RefreshError("martj42 results.csv has a row without date or tournament")
        if not home or not away or home == "NA" or away == "NA":
            if not scores.issubset(missing_tokens):
                raise RefreshConflict("martj42 has a scored row with unresolved team identity")
            omitted += 1
            continue
        kept.append(row)

    if omitted:
        temporary = Path(results_path).with_name(Path(results_path).name + ".filtered")
        with temporary.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=reader.fieldnames, lineterminator="\n")
            writer.writeheader()
            writer.writerows(kept)
        os.replace(temporary, results_path)
    return omitted


def build_international_runtime_pack(
    raw_root: Path,
    *,
    martj_ref: str,
    martj_committed_at: str,
    worldcup_ref: str,
    worldcup_committed_at: str,
    retrieved_at_utc: str,
    output_dir: Path,
) -> dict[str, Any]:
    """Build the martj42 training pack with World Cup fixture provenance."""
    import pandas as pd
    from golavo_core.ingest.match_index import normalize
    from golavo_core.ingest.worldcup import (
        crosscheck_completed,
        is_placeholder,
        kickoff_overlay,
        missing_fixtures,
        parse_worldcup,
    )

    from golavo_server.refresh_sources import MARTJ42, WORLDCUP

    output_dir = Path(output_dir)
    if output_dir.exists():
        raise FileExistsError(output_dir)
    output_dir.mkdir(parents=True)
    martj_files = ("results.csv", "goalscorers.csv", "shootouts.csv", "former_names.csv")
    for name in martj_files:
        _copy_raw(raw_root, MARTJ42, martj_ref, name, output_dir / name)
    omitted_unresolved = _drop_unresolved_identity_rows(output_dir / "results.csv")
    license_path = _copy_raw(raw_root, MARTJ42, martj_ref, "LICENSE", output_dir / "CC0-1.0.txt")
    if b"CC0 1.0 Universal" not in license_path.read_bytes():
        raise RefreshError("martj42 license is no longer the approved CC0-1.0 text")

    worldcup_path = Path(raw_root) / WORLDCUP / worldcup_ref / "2026/worldcup.json"
    stadium_path = Path(raw_root) / WORLDCUP / worldcup_ref / "2026/worldcup.stadiums.json"
    worldcup_license = Path(raw_root) / WORLDCUP / worldcup_ref / "LICENSE.md"
    if b"CC0 1.0 Universal" not in worldcup_license.read_bytes():
        raise RefreshError("worldcup.json license is no longer the approved CC0-1.0 text")
    try:
        worldcup_data = json.loads(worldcup_path.read_text(encoding="utf-8"))
        stadium_data = json.loads(stadium_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        raise RefreshError("World Cup raw snapshot is invalid JSON") from exc
    stadiums = stadium_data.get("stadiums") if isinstance(stadium_data, dict) else stadium_data
    if not isinstance(stadiums, list):
        raise RefreshError("World Cup stadium snapshot has an invalid schema")
    country_names = {"us": "United States", "ca": "Canada", "mx": "Mexico"}
    try:
        city_country = {
            str(row["city"]): country_names.get(str(row["cc"]).lower(), str(row["cc"]))
            for row in stadiums
        }
    except (KeyError, TypeError) as exc:
        raise RefreshError("World Cup stadium snapshot is missing city/country fields") from exc

    reference = pd.read_csv(output_dir / "results.csv", parse_dates=["date"])
    reference["is_complete"] = reference[["home_score", "away_score"]].notna().all(axis=1)
    parsed = parse_worldcup(worldcup_data)
    disagreements = crosscheck_completed(parsed, reference)
    if disagreements:
        raise RefreshConflict(
            "World Cup result conflicts with martj42: "
            + json.dumps(disagreements[:5], sort_keys=True)
        )
    added = missing_fixtures(parsed, reference, city_country)
    with (output_dir / "results.csv").open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        for row in added.itertuples(index=False):
            writer.writerow(
                [
                    row.date,
                    row.home_team,
                    row.away_team,
                    "NA",
                    "NA",
                    row.tournament,
                    row.city,
                    row.country,
                    "TRUE",
                ]
            )

    overlay = kickoff_overlay(parsed).copy()
    if not overlay.empty:
        overlay["date"] = overlay["date"].dt.strftime("%Y-%m-%d")
    overlay.to_csv(output_dir / "kickoffs.csv", index=False, lineterminator="\n")

    ref_keys = {
        (
            pd.Timestamp(row.date).strftime("%Y-%m-%d"),
            normalize(row.home_team),
            normalize(row.away_team),
        ): bool(row.is_complete)
        for row in reference.itertuples(index=False)
    }
    upstream_keys: dict[tuple[str, str, str], str] = {}
    for match in worldcup_data.get("matches", []):
        home, away, date = match.get("team1"), match.get("team2"), match.get("date")
        if not home or not away or not date or is_placeholder(home) or is_placeholder(away):
            continue
        upstream_keys[(str(date), normalize(home), normalize(away))] = (
            f"{WORLDCUP}:2026:{match.get('num', 'unknown')}"
        )
    provenance_rows: list[dict[str, Any]] = []
    for row in parsed.itertuples(index=False):
        key = (
            pd.Timestamp(row.date).strftime("%Y-%m-%d"),
            normalize(row.home_team),
            normalize(row.away_team),
        )
        in_martj = key in ref_keys
        complete = bool(ref_keys.get(key, False))
        provenance_rows.append(
            {
                "date": key[0],
                "home_team": row.home_team,
                "away_team": row.away_team,
                "identity_source_id": MARTJ42 if in_martj else WORLDCUP,
                "result_source_id": MARTJ42 if complete else "",
                "kickoff_source_id": WORLDCUP,
                "venue_source_id": WORLDCUP,
                "training_source_id": MARTJ42 if complete else "",
                "upstream_fixture_key": upstream_keys.get(key, f"{WORLDCUP}:2026:unknown"),
                "training_eligible": "true" if complete else "false",
            }
        )
    pd.DataFrame(
        provenance_rows,
        columns=[
            "date",
            "home_team",
            "away_team",
            "identity_source_id",
            "result_source_id",
            "kickoff_source_id",
            "venue_source_id",
            "training_source_id",
            "upstream_fixture_key",
            "training_eligible",
        ],
    ).to_csv(output_dir / "field_provenance.csv", index=False, lineterminator="\n")

    file_names = sorted((*martj_files, "CC0-1.0.txt", "kickoffs.csv", "field_provenance.csv"))
    manifest = {
        "source_id": MARTJ42,
        "url": "https://github.com/martj42/international_results",
        "upstream_ref": martj_ref,
        "upstream_committed_at_utc": martj_committed_at,
        "retrieved_at_utc": retrieved_at_utc,
        "files": [_manifest_entry(output_dir / name) for name in file_names],
        "license": "CC0-1.0",
        "omitted_unresolved_fixtures": omitted_unresolved,
        "co_sources": [
            {
                "source_id": WORLDCUP,
                "url": "https://github.com/openfootball/worldcup.json",
                "upstream_ref": worldcup_ref,
                "upstream_committed_at_utc": worldcup_committed_at,
                "retrieved_at_utc": retrieved_at_utc,
                "license": "CC0-1.0",
                "sha256_file": "kickoffs.csv",
                "raw_sha256": {
                    "2026/worldcup.json": _sha256(worldcup_path),
                    "2026/worldcup.stadiums.json": _sha256(stadium_path),
                },
            }
        ],
    }
    _write_json(output_dir / "manifest.json", manifest)
    return {
        "manifest": manifest,
        "added_worldcup_fixtures": int(len(added)),
        "omitted_unresolved_fixtures": omitted_unresolved,
    }


def build_club_runtime_packs(
    raw_root: Path,
    *,
    football_ref: str,
    football_committed_at: str,
    season: str,
    current_paths: tuple[str, ...],
    retrieved_at_utc: str,
    output_root: Path,
    as_of_utc: str,
) -> tuple[list[Path], list[dict[str, Any]]]:
    """Build only genuinely published current-season club packs."""
    from golavo_core.ingest.openfootball import LEAGUES, load_openfootball_table
    from golavo_core.season_outlook import certify_schedule

    from golavo_server.refresh_sources import FOOTBALL

    expected_teams = {"de.1": 18, "fr.1": 18, "en.1": 20, "es.1": 20, "it.1": 20}
    output_root.mkdir(parents=True, exist_ok=True)
    packs: list[Path] = []
    capabilities: list[dict[str, Any]] = []
    license_source = Path(raw_root) / FOOTBALL / football_ref / "LICENSE.md"
    if current_paths and b"CC0 1.0 Universal" not in license_source.read_bytes():
        raise RefreshError("football.json license is no longer the approved CC0-1.0 text")
    for relative in current_paths:
        code = Path(relative).stem
        if code not in LEAGUES or relative != f"{season}/{code}.json":
            raise RefreshError(f"unexpected football.json current-season path: {relative}")
        competition, _country = LEAGUES[code]
        pack = output_root / code
        pack.mkdir(parents=True, exist_ok=False)
        json_name = f"{season}.{code}.json"
        _copy_raw(raw_root, FOOTBALL, football_ref, relative, pack / json_name)
        shutil.copyfile(license_source, pack / "CC0-1.0.txt")
        manifest = {
            "source_id": FOOTBALL,
            "url": "https://github.com/openfootball/football.json",
            "upstream_ref": football_ref,
            "upstream_committed_at_utc": football_committed_at,
            "retrieved_at_utc": retrieved_at_utc,
            "competition": competition,
            "season": season,
            "files": [
                {**_manifest_entry(pack / json_name), "season": season},
                _manifest_entry(pack / "CC0-1.0.txt"),
            ],
            "license": "CC0-1.0",
        }
        _write_json(pack / "manifest.json", manifest)
        frame = load_openfootball_table(pack)
        certificate = certify_schedule(
            frame, expected_teams=expected_teams[code], as_of_utc=as_of_utc
        )
        capability = (
            "complete"
            if certificate["complete_fixture_list"] and certificate["past_result_gaps"] == 0
            else "partial"
        )
        packs.append(pack)
        capabilities.append(
            {
                "source_id": FOOTBALL,
                "competition": competition,
                "league_code": code,
                "season": season,
                "upstream_ref": football_ref,
                "checked_at_utc": retrieved_at_utc,
                "capability": capability,
                "certificate": certificate,
            }
        )
    return packs, capabilities


def _upgrade_legacy_columns(frame: Any) -> Any:
    """Add v0.5 provenance defaults when carrying rows from a v0.4 bundle."""
    import pandas as pd

    result = frame.copy()
    source = result["source_id"].astype("string")
    complete = result["is_complete"].astype("boolean").fillna(False)
    defaults: dict[str, Any] = {
        "identity_source_id": source,
        "result_source_id": source.where(complete, pd.NA),
        "kickoff_source_id": source,
        "venue_source_id": source.where(result["city"].notna() | result["country"].notna(), pd.NA),
        "training_source_id": source.where(complete, pd.NA),
        "upstream_fixture_key": source + ":" + result["match_id"].astype("string"),
        "training_eligible": complete.astype(bool),
    }
    for column, values in defaults.items():
        if column not in result.columns:
            result[column] = values
    return result


def merge_refresh_generation(
    fresh_intl_pack: Path,
    club_packs: list[Path],
    base_index_path: Path,
    target_dir: Path,
    *,
    season_start: str,
) -> Path:
    """Build a whole candidate, replacing only refresh-owned source slices."""
    import pandas as pd

    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_index = target_dir / "matches_index.parquet"
    build_match_index([Path(fresh_intl_pack), *map(Path, club_packs)], target_index)
    fresh = pd.read_parquet(target_index)
    base = _upgrade_legacy_columns(pd.read_parquet(base_index_path))
    carry = base[base["source_kind"] != _INTERNATIONAL_KIND].copy()
    for pack in club_packs:
        manifest = json.loads((Path(pack) / "manifest.json").read_text(encoding="utf-8"))
        competition = str(manifest["competition"])
        current_slice = carry["competition"].astype("string").eq(competition) & (
            pd.to_datetime(carry["date"]) >= pd.Timestamp(season_start)
        )
        carry = carry.loc[~current_slice]
    merged = (
        pd.concat([fresh[INDEX_COLUMNS], carry[INDEX_COLUMNS]], ignore_index=True)
        .sort_values(["kickoff_utc", "match_id"], kind="mergesort")
        .reset_index(drop=True)[INDEX_COLUMNS]
    )
    duplicate = merged["match_id"].duplicated(keep=False)
    if duplicate.any():
        collisions = sorted(merged.loc[duplicate, "match_id"].unique())[:10]
        raise RefreshError(f"match_id collision in refresh candidate: {collisions}")
    merged.to_parquet(target_index, index=False, engine="pyarrow", compression="zstd")
    meta = {
        "schema_version": MATCH_INDEX_SCHEMA_VERSION,
        "row_count": int(len(merged)),
        "parquet_sha256": _sha256(target_index),
        "refreshed": True,
        "sources": sorted(set(str(value) for value in merged["source_id"].dropna().unique())),
    }
    _write_json(target_dir / "matches_index.meta.json", meta)
    return target_index


def assert_safe_change(
    base_index_path: Path, candidate_index_path: Path, ledger_dir: Path
) -> dict[str, int]:
    """Reject completed-evidence rewrites and any sealed-fixture mutation."""
    import pandas as pd

    base = pd.read_parquet(base_index_path)
    candidate = pd.read_parquet(candidate_index_path)
    current = candidate.set_index("match_id", drop=False)
    completed = base[base["is_complete"].astype("boolean").fillna(False)]
    removed_completed: list[str] = []
    changed_scores: list[str] = []
    for row in completed.itertuples(index=False):
        match_id = str(row.match_id)
        if match_id not in current.index:
            removed_completed.append(match_id)
            continue
        after = current.loc[match_id]
        if isinstance(after, pd.DataFrame):
            raise RefreshConflict(
                f"candidate duplicates completed match {match_id}",
                details=[{"kind": "duplicate_completed", "match_id": match_id}],
            )
        if (int(row.home_score), int(row.away_score)) != (
            int(after["home_score"]),
            int(after["away_score"]),
        ):
            changed_scores.append(match_id)
    if removed_completed or changed_scores:
        raise RefreshConflict(
            "candidate rewrites completed evidence "
            f"(removed={removed_completed[:5]}, scores={changed_scores[:5]})",
            details=[
                *(
                    {"kind": "removed_completed", "match_id": match_id}
                    for match_id in removed_completed
                ),
                *(
                    {"kind": "changed_score", "match_id": match_id}
                    for match_id in changed_scores
                ),
            ],
        )
    sealed_matches: dict[str, dict[str, Any]] = {}
    for artifact in sorted(Path(ledger_dir).glob("fa_*.json")):
        try:
            obj = json.loads(artifact.read_text(encoding="utf-8"))
            sealed_match = obj.get("match", {})
            match_id = sealed_match.get("match_id")
        except (OSError, ValueError, TypeError, AttributeError):
            continue
        if match_id and isinstance(sealed_match, dict):
            sealed_matches[str(match_id)] = sealed_match
    missing_sealed = sorted(set(sealed_matches) - set(candidate["match_id"].astype(str)))
    if missing_sealed:
        raise RefreshConflict(
            f"candidate removes sealed fixtures: {missing_sealed[:5]}",
            details=[
                {"kind": "removed_sealed_fixture", "match_id": match_id}
                for match_id in missing_sealed
            ],
        )

    sealed_field_map = {
        "home_team": "home_team",
        "away_team": "away_team",
        "kickoff_utc": "kickoff_utc",
        "competition": "competition",
        "city": "city",
        "country": "country",
        "neutral_venue": "neutral",
    }
    changed_seals: list[dict[str, Any]] = []
    for match_id, sealed_match in sealed_matches.items():
        if match_id not in current.index:
            continue
        row = current.loc[match_id]
        if isinstance(row, pd.DataFrame):
            raise RefreshConflict(
                f"candidate duplicates sealed fixture {match_id}",
                details=[{"kind": "duplicate_sealed_fixture", "match_id": match_id}],
            )
        for artifact_field, index_field in sealed_field_map.items():
            if artifact_field not in sealed_match:
                continue
            expected = sealed_match[artifact_field]
            observed = row[index_field]
            if artifact_field == "kickoff_utc":
                same = pd.Timestamp(expected) == pd.Timestamp(observed)
            elif artifact_field == "neutral_venue":
                same = bool(expected) == bool(observed)
            else:
                expected_value = None if pd.isna(expected) else str(expected)
                observed_value = None if pd.isna(observed) else str(observed)
                same = expected_value == observed_value
            if not same:
                changed_seals.append(
                    {
                        "kind": "changed_sealed_fixture",
                        "match_id": match_id,
                        "field": artifact_field,
                        "before": str(expected) if expected is not None else None,
                        "candidate": str(observed) if not pd.isna(observed) else None,
                    }
                )
                break
    if changed_seals:
        labels = [f"{item['match_id']}:{item['field']}" for item in changed_seals[:5]]
        raise RefreshConflict(
            f"candidate changes sealed fixture fields: {labels}", details=changed_seals
        )

    base_ids = set(base["match_id"].astype(str))
    candidate_ids = set(candidate["match_id"].astype(str))
    return {
        "added_matches": len(candidate_ids - base_ids),
        "removed_incomplete_matches": len(base_ids - candidate_ids),
        "new_results": int(
            candidate.set_index("match_id")["is_complete"].reindex(base_ids).fillna(False).sum()
            - base.set_index("match_id")["is_complete"].fillna(False).sum()
        ),
    }


def write_generation_manifest(
    staging: Path,
    *,
    source_snapshots: list[dict[str, Any]],
    capabilities: list[dict[str, Any]],
    change_summary: dict[str, int],
    created_at_utc: str,
) -> dict[str, Any]:
    """Seal all candidate bytes into a deterministic generation identity."""
    staging = Path(staging)
    artifacts = [
        {
            "path": path.relative_to(staging).as_posix(),
            "sha256": _sha256(path),
            "bytes": path.stat().st_size,
        }
        for path in sorted(staging.rglob("*"))
        if path.is_file() and path.name != "generation.json"
    ]
    index_hash = next(
        entry["sha256"] for entry in artifacts if entry["path"] == "index/matches_index.parquet"
    )
    identity = {
        "source_refs": sorted(
            (str(snapshot["source_id"]), str(snapshot["upstream_ref"]))
            for snapshot in source_snapshots
        ),
        "index_sha256": index_hash,
        "capabilities": capabilities,
    }
    generation_id = (
        "g_"
        + hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
    )
    manifest = {
        "schema_version": "0.1.0",
        "generation_id": generation_id,
        "created_at_utc": created_at_utc,
        "source_snapshots": source_snapshots,
        "capabilities": capabilities,
        "change_summary": change_summary,
        "artifacts": artifacts,
    }
    _write_json(staging / "generation.json", manifest)
    with (staging / "generation.json").open("rb") as handle:
        os.fsync(handle.fileno())
    return manifest
