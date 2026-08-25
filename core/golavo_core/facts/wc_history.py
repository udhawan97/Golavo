"""Validated, read-only access to the isolated Fjelstul World Cup pack."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pandas as pd

from golavo_core import resources
from golavo_core.ingest.snapshot import validate_pack, validate_registered_pack

SOURCE_ID = "fjelstul-worldcup"
SOURCE_LICENSE = "CC-BY-SA-4.0"
PACK_NAME = "fjelstul-worldcup-f942c6b"
WorldCupCategory = Literal["men", "women"]
_CATEGORY_MARKERS: dict[WorldCupCategory, str] = {
    "men": "Men's World Cup",
    "women": "Women's World Cup",
}


@dataclass(frozen=True)
class WorldCupHistory:
    standings: pd.DataFrame
    appearances: pd.DataFrame
    awards: pd.DataFrame
    category: WorldCupCategory = "men"
    source_id: str = SOURCE_ID
    license: str = SOURCE_LICENSE
    source_url: str = ""
    upstream_ref: str = ""
    retrieved_at_utc: str = ""


def _validate_manifest(pack_dir: Path, *, declared: bool) -> dict:
    manifest = (
        validate_registered_pack(
            pack_dir,
            resources.resource("packs", "isolated.json"),
            expected_source_id=SOURCE_ID,
        )
        if declared
        else validate_pack(pack_dir)
    )
    if manifest.get("source_id") != SOURCE_ID or manifest.get("license") != SOURCE_LICENSE:
        raise ValueError(f"{pack_dir}: unexpected Fjelstul source or license")
    return manifest


def _strings(frame: pd.DataFrame, columns: tuple[str, ...]) -> pd.DataFrame:
    for column in columns:
        frame[column] = frame[column].astype("string")
    return frame


def load_wc_history(
    pack_dir: Path | None = None, *, category: WorldCupCategory = "men"
) -> WorldCupHistory | None:
    """Load one typed World Cup history lane from the isolated pack.

    The default remains the men's lane used by the match-notebook fact engine.
    Callers must opt into the women's lane explicitly, which prevents a men's
    match from silently receiving facts from a different competition category.
    """
    if category not in _CATEGORY_MARKERS:
        raise ValueError(f"unsupported World Cup category: {category}")
    declared = pack_dir is None
    pack = Path(pack_dir) if pack_dir is not None else resources.resource("packs", PACK_NAME)
    if not pack.is_dir():
        return None
    manifest = _validate_manifest(pack, declared=declared)

    tournaments = pd.read_csv(pack / "tournaments.csv")
    tournaments = tournaments.loc[
        tournaments["tournament_name"]
        .astype("string")
        .str.contains(_CATEGORY_MARKERS[category], regex=False)
    ].copy()
    tournaments = _strings(tournaments, ("tournament_id", "tournament_name"))
    tournaments["year"] = tournaments["year"].astype("Int16")
    tournaments["end_date"] = pd.to_datetime(tournaments["end_date"], utc=True)
    tournament_dates = tournaments[["tournament_id", "year", "end_date"]]
    tournament_ids = set(tournaments["tournament_id"].astype(str))

    standings = pd.read_csv(pack / "tournament_standings.csv")
    standings = standings.loc[
        standings["tournament_id"].astype("string").isin(tournament_ids)
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
        appearances["tournament_id"].astype("string").isin(tournament_ids)
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
    awards = awards.loc[
        awards["tournament_id"].astype("string").isin(tournament_ids)
    ].copy()
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
    given_names = awards["given_name"].fillna("").str.strip()
    # The pinned source uses this sentinel for mononymous players such as Pelé
    # and Sissi. It is missing data, not part of the displayed name.
    given_names = given_names.mask(given_names.str.casefold() == "not applicable", "")
    awards["player"] = (
        given_names
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
        category=category,
        source_url=str(manifest.get("url") or ""),
        upstream_ref=str(manifest.get("upstream_ref") or ""),
        retrieved_at_utc=str(manifest.get("retrieved_at") or ""),
    )
