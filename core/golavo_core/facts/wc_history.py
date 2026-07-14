"""Validated, read-only access to the isolated Fjelstul World Cup pack."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from golavo_core import resources

SOURCE_ID = "fjelstul-worldcup"
SOURCE_LICENSE = "CC-BY-SA-4.0"
PACK_NAME = "fjelstul-worldcup-f942c6b"


@dataclass(frozen=True)
class WorldCupHistory:
    standings: pd.DataFrame
    appearances: pd.DataFrame
    awards: pd.DataFrame
    source_id: str = SOURCE_ID
    license: str = SOURCE_LICENSE


def _validate_manifest(pack_dir: Path) -> dict:
    manifest = json.loads((pack_dir / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("source_id") != SOURCE_ID or manifest.get("license") != SOURCE_LICENSE:
        raise ValueError(f"{pack_dir}: unexpected Fjelstul source or license")
    for entry in manifest.get("files", []):
        path = pack_dir / str(entry["name"])
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != entry.get("sha256"):
            raise ValueError(f"{path}: sha256 mismatch")
    return manifest


def _strings(frame: pd.DataFrame, columns: tuple[str, ...]) -> pd.DataFrame:
    for column in columns:
        frame[column] = frame[column].astype("string")
    return frame


def load_wc_history(pack_dir: Path | None = None) -> WorldCupHistory | None:
    """Load typed men's World Cup frames, or ``None`` when the pack is absent."""
    pack = Path(pack_dir) if pack_dir is not None else resources.resource("packs", PACK_NAME)
    if not pack.is_dir():
        return None
    _validate_manifest(pack)

    tournaments = pd.read_csv(pack / "tournaments.csv")
    tournaments = tournaments.loc[
        tournaments["tournament_name"].astype("string").str.contains("Men's World Cup", regex=False)
    ].copy()
    tournaments = _strings(tournaments, ("tournament_id", "tournament_name"))
    tournaments["year"] = tournaments["year"].astype("Int16")
    tournaments["end_date"] = pd.to_datetime(tournaments["end_date"], utc=True)
    tournament_dates = tournaments[["tournament_id", "year", "end_date"]]
    mens_ids = set(tournaments["tournament_id"].astype(str))

    standings = pd.read_csv(pack / "tournament_standings.csv")
    standings = standings.loc[
        standings["tournament_id"].astype("string").isin(mens_ids)
    ].copy()
    standings = _strings(
        standings, ("tournament_id", "tournament_name", "team_id", "team_name", "team_code")
    )
    standings["position"] = standings["position"].astype("Int8")
    standings = standings.merge(
        tournament_dates, on="tournament_id", how="left", validate="many_to_one"
    )

    appearances = pd.read_csv(pack / "team_appearances.csv")
    appearances = appearances.loc[
        appearances["tournament_id"].astype("string").isin(mens_ids)
    ].copy()
    appearances = _strings(
        appearances, ("tournament_id", "tournament_name", "team_id", "team_name", "team_code")
    )
    appearances = appearances[
        ["tournament_id", "tournament_name", "team_id", "team_name", "team_code"]
    ].drop_duplicates()
    appearances = appearances.merge(
        tournament_dates, on="tournament_id", how="left", validate="many_to_one"
    )

    awards = pd.read_csv(pack / "award_winners.csv")
    awards = awards.loc[awards["tournament_id"].astype("string").isin(mens_ids)].copy()
    awards = _strings(
        awards,
        (
            "tournament_id",
            "tournament_name",
            "award_id",
            "award_name",
            "player_id",
            "family_name",
            "given_name",
            "team_id",
            "team_name",
            "team_code",
        ),
    )
    awards["player"] = (
        awards["given_name"].fillna("").str.strip()
        + " "
        + awards["family_name"].fillna("").str.strip()
    ).str.strip()
    awards = awards.merge(tournament_dates, on="tournament_id", how="left", validate="many_to_one")

    return WorldCupHistory(
        standings=standings.sort_values(
            ["year", "position", "team_name"], kind="mergesort"
        ).reset_index(drop=True),
        appearances=appearances.sort_values(
            ["year", "team_name"], kind="mergesort"
        ).reset_index(drop=True),
        awards=awards.sort_values(
            ["year", "award_name", "player"], kind="mergesort"
        ).reset_index(drop=True),
    )
