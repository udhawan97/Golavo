"""Pinned sourcepack ingestion and typed match-table construction."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

REQUIRED_RESULT_COLUMNS = {
    "date",
    "home_team",
    "away_team",
    "home_score",
    "away_score",
    "tournament",
    "city",
    "country",
    "neutral",
}


def validate_pack(pack_dir: Path) -> dict[str, Any]:
    """Validate declared pack bytes and return the parsed manifest."""
    manifest_path = pack_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for entry in manifest.get("files", []):
        path = pack_dir / entry["name"]
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != entry["sha256"]:
            raise ValueError(f"provenance hash mismatch for {path}")
    return manifest


def snapshot_descriptor(pack_dir: Path) -> dict[str, str]:
    """Return the canonical artifact descriptor for a validated sourcepack."""
    manifest = validate_pack(pack_dir)
    manifest_bytes = (pack_dir / "manifest.json").read_bytes()
    upstream_ref = str(manifest["upstream_ref"])
    descriptor = {
        "snapshot_id": f"sp_{upstream_ref[:12]}",
        "source_id": str(manifest["source_id"]),
        "url": str(manifest["url"]),
        "upstream_ref": upstream_ref,
        "retrieved_at_utc": str(manifest["retrieved_at_utc"]),
        "sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "license": str(manifest["license"]),
    }
    if manifest.get("upstream_committed_at_utc"):
        descriptor["upstream_committed_at_utc"] = str(manifest["upstream_committed_at_utc"])
    return descriptor


def snapshot_anchor_utc(descriptor: dict[str, Any]) -> str:
    """Return the time this snapshot's data state verifiably existed.

    The upstream commit time of the pinned ref is the honest anchor: the data
    state was public from that moment, independent of when we fetched it. Packs
    built before the anchor existed fall back to our own retrieval time, which
    is strictly later and therefore never overstates availability.
    """
    return str(descriptor.get("upstream_committed_at_utc") or descriptor["retrieved_at_utc"])


def _canonicalize_former_names(matches: pd.DataFrame, former_names_path: Path) -> pd.DataFrame:
    former = pd.read_csv(
        former_names_path,
        dtype={"current": "string", "former": "string"},
        parse_dates=["start_date", "end_date"],
    )
    result = matches.copy()
    for rename in former.sort_values(["start_date", "former"]).itertuples(index=False):
        active = result["date"].between(rename.start_date, rename.end_date, inclusive="both")
        for column in ("home_team", "away_team"):
            mask = active & result[column].eq(rename.former)
            result.loc[mask, column] = rename.current
    return result


def _match_identity(row: pd.Series) -> str:
    return "|".join(
        [
            row["date"].date().isoformat(),
            str(row["home_team"]),
            str(row["away_team"]),
            str(row["tournament"]),
            str(row["city"]),
            str(row["country"]),
            str(bool(row["neutral"])),
        ]
    )


def load_match_table(pack_dir: Path) -> pd.DataFrame:
    """Load the source snapshot into Golavo's deterministic typed match table."""
    validate_pack(pack_dir)
    matches = pd.read_csv(
        pack_dir / "results.csv",
        dtype={
            "home_team": "string",
            "away_team": "string",
            "home_score": "Int16",
            "away_score": "Int16",
            "tournament": "string",
            "city": "string",
            "country": "string",
            "neutral": "boolean",
        },
        parse_dates=["date"],
    )
    missing = REQUIRED_RESULT_COLUMNS - set(matches.columns)
    if missing:
        raise ValueError(f"results.csv is missing columns: {sorted(missing)}")
    required_non_score = REQUIRED_RESULT_COLUMNS - {"home_score", "away_score"}
    if matches[list(required_non_score)].isna().any().any():
        raise ValueError("results.csv contains nulls in required identity fields")
    if matches[["home_score", "away_score"]].isna().any(axis=1).ne(
        matches[["home_score", "away_score"]].isna().all(axis=1)
    ).any():
        raise ValueError("a fixture must have both scores or neither score")
    if (matches[["home_score", "away_score"]].dropna() < 0).any().any():
        raise ValueError("results.csv contains a negative score")

    matches = _canonicalize_former_names(matches, pack_dir / "former_names.csv")
    matches = matches.sort_values(
        ["date", "home_team", "away_team", "tournament"], kind="mergesort"
    ).reset_index(drop=True)
    identities = matches.apply(_match_identity, axis=1)
    occurrences = identities.groupby(identities, sort=False).cumcount()
    match_ids = [
        f"m_{hashlib.sha256(f'{identity}|{occurrence}'.encode()).hexdigest()[:16]}"
        for identity, occurrence in zip(identities, occurrences, strict=True)
    ]
    matches.insert(0, "match_id", match_ids)
    matches["kickoff_utc"] = pd.to_datetime(matches["date"], utc=True)
    matches["is_complete"] = matches[["home_score", "away_score"]].notna().all(axis=1)
    return matches


def assert_no_future_rows(matches: pd.DataFrame, cutoff_utc: str | pd.Timestamp) -> None:
    """Fail closed if a training frame contains even one row after its cutoff."""
    cutoff = pd.Timestamp(cutoff_utc)
    cutoff = cutoff.tz_localize("UTC") if cutoff.tzinfo is None else cutoff.tz_convert("UTC")
    dates = pd.to_datetime(matches["date"], utc=True)
    offenders = matches.loc[dates > cutoff]
    if not offenders.empty:
        first = offenders.sort_values("date").iloc[0]
        raise ValueError(
            "training leakage: row "
            f"{first.get('match_id', '<unknown>')} dated {first['date']} exceeds cutoff "
            f"{cutoff.isoformat()}"
        )


def training_rows(matches: pd.DataFrame, cutoff_utc: str | pd.Timestamp) -> pd.DataFrame:
    """Select a chronological training frame and assert the invariant."""
    cutoff = pd.Timestamp(cutoff_utc)
    cutoff = cutoff.tz_localize("UTC") if cutoff.tzinfo is None else cutoff.tz_convert("UTC")
    dates = pd.to_datetime(matches["date"], utc=True)
    selected = matches.loc[(dates <= cutoff) & matches["is_complete"]].copy()
    assert_no_future_rows(selected, cutoff)
    return selected


def write_parquet(pack_dir: Path, output_path: Path) -> Path:
    """Materialize the typed match table as deterministic Parquet."""
    table = load_match_table(pack_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    table.to_parquet(output_path, index=False, engine="pyarrow", compression="zstd")
    return output_path
