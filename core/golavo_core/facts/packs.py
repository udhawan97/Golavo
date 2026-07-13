"""Read the internationals-only side tables (goalscorers, shootouts) from a pack.

These are the ONLY packs that ship scorer and shootout data (martj42). Club
packs have neither, so this returns ``None`` for a pack that lacks the file —
the scorer/shootout templates then simply do not run. No club scorer or lineup
data is ever invented.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def _read_bool(series: pd.Series) -> pd.Series:
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


def load_side_tables(pack_dir: Path) -> tuple[pd.DataFrame | None, pd.DataFrame | None]:
    """Return (goalscorers, shootouts) for an internationals pack, else (None, None)."""
    pack_dir = Path(pack_dir)
    goalscorers: pd.DataFrame | None = None
    shootouts: pd.DataFrame | None = None

    gs_path = pack_dir / "goalscorers.csv"
    if gs_path.is_file():
        goalscorers = pd.read_csv(
            gs_path,
            dtype={"home_team": "string", "away_team": "string", "team": "string",
                   "scorer": "string", "minute": "string"},
            parse_dates=["date"],
        )
        goalscorers["own_goal"] = _read_bool(goalscorers["own_goal"])
        goalscorers["penalty"] = _read_bool(goalscorers["penalty"])

    so_path = pack_dir / "shootouts.csv"
    if so_path.is_file():
        shootouts = pd.read_csv(
            so_path,
            dtype={"home_team": "string", "away_team": "string", "winner": "string",
                   "first_shooter": "string"},
            parse_dates=["date"],
        )

    return goalscorers, shootouts
