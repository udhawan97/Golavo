"""Build the committed, deterministic match search index and its side tables.

The index is a single frozen Parquet over every bundled CC0 pack (martj42
internationals + the five openfootball club leagues). It exists so the desktop
sidecar can search matches and precompute Commentator's Notebooks on demand
without re-reading raw packs. Three invariants make the committed bytes
trustworthy:

* only CC0-cleared packs are folded in (a fail-closed license gate);
* each pack keeps its OWN match ids — the identity function differs per source,
  so re-hashing the merged frame would silently corrupt them;
* the build is pure — no wall clock, sorted keys, mergesort — so two builds of
  the same packs produce byte-identical Parquet and an identical meta digest.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from pathlib import Path

import pandas as pd

from .snapshot import snapshot_anchor_utc

MATCH_INDEX_SCHEMA_VERSION = "0.3.0"

# The verbatim column order of matches_index.parquet. Fixed so the committed
# bytes never depend on per-pack insertion order, and so downstream readers
# (the server search workstream) can bind to a stable schema.
INDEX_COLUMNS = [
    "match_id",
    "date",
    "kickoff_utc",
    "home_team",
    "away_team",
    "home_norm",
    "away_norm",
    "home_score",
    "away_score",
    "is_complete",
    "tournament",
    "competition",
    "city",
    "country",
    "neutral",
    "source_id",
    "source_kind",
    "ht_home_score",
    "ht_away_score",
]

# Licenses cleared for redistribution inside the committed index.
_CLEARED_LICENSES = frozenset({"CC0-1.0"})


def normalize(s: str) -> str:
    """Fold a team name to a diacritic-free, casefolded search key.

    NFKD decompose -> drop combining marks -> casefold -> strip, so 'Atletico'
    and 'Atletico' collapse and a later search need not reproduce diacritics.
    """
    decomposed = unicodedata.normalize("NFKD", str(s))
    without_marks = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return without_marks.casefold().strip()


def default_index_packs(repo_root: Path) -> list[Path]:
    """Select one pack per (source, competition): the greatest snapshot anchor.

    Entries in packs/snapshots.json are grouped by manifest source_id and, for
    club packs, competition; the entry whose data state is anchored latest wins
    its group (ties broken by pack path). This keeps a single internationals
    pack and exactly one pack per club league. Returns absolute pack directories
    in a stable, path-sorted build order.
    """
    repo_root = Path(repo_root)
    registry = json.loads(
        (repo_root / "packs" / "snapshots.json").read_text(encoding="utf-8")
    )
    best: dict[tuple[str, str], dict] = {}
    for entry in registry["snapshots"]:
        pack_dir = repo_root / entry["pack"]
        manifest = json.loads((pack_dir / "manifest.json").read_text(encoding="utf-8"))
        key = (str(entry["source_id"]), str(manifest.get("competition") or ""))
        rank = (snapshot_anchor_utc(entry), str(entry["pack"]))
        incumbent = best.get(key)
        if incumbent is None or rank > incumbent["_rank"]:
            best[key] = {**entry, "_rank": rank}
    return [
        (repo_root / entry["pack"]).resolve()
        for entry in sorted(best.values(), key=lambda e: e["pack"])
    ]


def _read_bool(series: pd.Series) -> pd.Series:
    """Parse martj42's TRUE/FALSE text flags into a plain bool column."""
    if series.dtype == bool:
        return series
    return (
        series.astype("string")
        .str.strip()
        .str.upper()
        .map({"TRUE": True, "FALSE": False})
        .astype("boolean")
        .fillna(False)
        .astype(bool)
    )


def _write_side_tables(pack_dir: Path, out_dir: Path) -> None:
    """Materialize martj42's goalscorers and shootouts as Parquet, when present.

    Typed to match golavo_core.facts.packs.load_side_tables so a later consumer
    reads identical dtypes. Club packs ship neither file — nothing is written.
    """
    gs_path = pack_dir / "goalscorers.csv"
    if gs_path.is_file():
        goalscorers = pd.read_csv(
            gs_path,
            dtype={
                "home_team": "string",
                "away_team": "string",
                "team": "string",
                "scorer": "string",
            },
            parse_dates=["date"],
        )
        goalscorers["own_goal"] = _read_bool(goalscorers["own_goal"])
        goalscorers["penalty"] = _read_bool(goalscorers["penalty"])
        goalscorers.to_parquet(
            out_dir / "goalscorers.parquet",
            index=False,
            engine="pyarrow",
            compression="zstd",
        )

    so_path = pack_dir / "shootouts.csv"
    if so_path.is_file():
        shootouts = pd.read_csv(
            so_path,
            dtype={
                "home_team": "string",
                "away_team": "string",
                "winner": "string",
                "first_shooter": "string",
            },
            parse_dates=["date"],
        )
        shootouts.to_parquet(
            out_dir / "shootouts.parquet",
            index=False,
            engine="pyarrow",
            compression="zstd",
        )


def _write_aliases(pack_dir: Path, index: pd.DataFrame, out_dir: Path) -> None:
    """Emit a best-effort {normalized_alias: [present team, ...]} search map.

    martj42's former_names.csv renames historical sides to their current name at
    load time, so the merged index carries only the surviving spelling. This map
    lets a later search for a former spelling ('soviet union') resolve to the
    team strings that actually appear in the index. Both former and current
    spellings are indexed; keys and value lists are sorted for a stable file.
    """
    fn_path = pack_dir / "former_names.csv"
    if not fn_path.is_file():
        return
    former = pd.read_csv(fn_path, dtype={"current": "string", "former": "string"})
    present = set(
        pd.concat([index["home_team"], index["away_team"]]).dropna().astype(str).unique()
    )
    aliases: dict[str, set[str]] = {}
    for row in former.itertuples(index=False):
        current, former_name = str(row.current), str(row.former)
        targets = sorted(name for name in {current, former_name} if name in present)
        if not targets:  # neither spelling survived into the index
            targets = [current]
        for spelling in (current, former_name):
            key = normalize(spelling)
            if key:
                aliases.setdefault(key, set()).update(targets)
    serializable = {key: sorted(values) for key, values in sorted(aliases.items())}
    (out_dir / "aliases.json").write_text(
        json.dumps(serializable, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def build_match_index(pack_dirs: list[Path], output_path: Path) -> Path:
    """Fold the given packs into the committed match index at ``output_path``.

    Writes the index Parquet, its ``matches_index.meta.json`` digest sidecar,
    and (martj42 only) the goalscorers/shootouts Parquets and the alias map.
    Every pack is license-gated and hash-validated before a single row is read.
    """
    from golavo_core.ingest import load_matches  # lazy: breaks the package cycle

    output_path = Path(output_path)
    out_dir = output_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    frames: list[pd.DataFrame] = []
    provenance: list[dict[str, str]] = []
    side_source: Path | None = None
    for pack_dir in pack_dirs:
        pack_dir = Path(pack_dir)
        manifest = json.loads((pack_dir / "manifest.json").read_text(encoding="utf-8"))
        lic = manifest.get("license")
        if lic not in _CLEARED_LICENSES:
            raise ValueError(
                f"{pack_dir}: license {lic!r} not cleared for the bundled match index"
            )
        source_id = str(manifest["source_id"])
        df = load_matches(pack_dir).copy()  # re-validates the pack's byte hashes
        df["competition"] = df["tournament"].astype("string")
        df["source_id"] = pd.Series(source_id, index=df.index, dtype="string")
        kind = "international" if source_id.startswith("martj42") else "club"
        df["source_kind"] = pd.Series(kind, index=df.index, dtype="string")
        df["home_norm"] = df["home_team"].map(normalize).astype("string")
        df["away_norm"] = df["away_team"].map(normalize).astype("string")
        frames.append(df[INDEX_COLUMNS])
        provenance.append(
            {
                "source_id": source_id,
                "pack": pack_dir.name,
                "license": str(lic),
                "manifest_sha256": hashlib.sha256(
                    (pack_dir / "manifest.json").read_bytes()
                ).hexdigest(),
            }
        )
        if source_id.startswith("martj42"):
            side_source = pack_dir  # only martj42 ships scorer/shootout side tables

    index = pd.concat(frames, ignore_index=True)
    collisions = index["match_id"][index["match_id"].duplicated(keep=False)]
    if not collisions.empty:
        raise ValueError(
            "match_id collision across packs (packs must dedupe upstream): "
            f"{sorted(collisions.unique())[:10]}"
        )
    index = index.sort_values(
        ["kickoff_utc", "match_id"], kind="mergesort"
    ).reset_index(drop=True)
    index = index[INDEX_COLUMNS]
    index.to_parquet(output_path, index=False, engine="pyarrow", compression="zstd")

    meta = {
        "schema_version": MATCH_INDEX_SCHEMA_VERSION,
        "row_count": int(len(index)),
        "parquet_sha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
        "built_from": sorted(provenance, key=lambda p: (p["source_id"], p["pack"])),
    }
    (out_dir / "matches_index.meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    if side_source is not None:
        _write_side_tables(side_source, out_dir)
        _write_aliases(side_source, index, out_dir)

    return output_path
