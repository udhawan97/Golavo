"""Exact-kickoff overlay: splice precise kickoff instants onto a pack's match table.

A pack may ship an optional ``kickoffs.csv`` (date, home_team, away_team, tournament,
kickoff_utc) built from a CC0 source that carries exact kickoff times (worldcup.json).
When present AND declared in the manifest (so validate_pack has hash-verified it), the
loader overrides ``kickoff_utc`` for the matching rows — nothing else. Because it only
sharpens a column the frame already has:

* a World Cup seal's window closes at the real kickoff, not the 00:00 UTC day proxy;
* ``is_complete`` is untouched, so an upcoming fixture stays out of every training frame;
* a pack with no kickoffs.csv is byte-for-byte unchanged (the committed index too).

An overlay file present but NOT declared in the manifest is a provenance gap and fails
closed — an unverified file must never be able to move a seal's window.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .match_index import normalize


def _keys(frame: pd.DataFrame) -> pd.Series:
    return (
        pd.to_datetime(frame["date"]).dt.strftime("%Y-%m-%d")
        + "|" + frame["home_team"].map(normalize)
        + "|" + frame["away_team"].map(normalize)
        + "|" + frame["tournament"].map(normalize)
    )


def apply_exact_kickoffs(
    frame: pd.DataFrame, pack_dir: Path, manifest: dict[str, Any]
) -> pd.DataFrame:
    """Return ``frame`` with kickoff_utc replaced by the pack's exact-kickoff overlay.

    A no-op (returns the frame unchanged) when the pack ships no kickoffs.csv. Raises
    when a kickoffs.csv exists but is absent from the manifest's declared files.
    """
    path = Path(pack_dir) / "kickoffs.csv"
    if not path.is_file():
        return frame
    declared = {str(entry.get("name")) for entry in manifest.get("files", [])}
    if "kickoffs.csv" not in declared:
        raise ValueError(
            f"{pack_dir}: kickoffs.csv is present but not declared in the manifest; "
            "an unverified overlay must never move a seal window"
        )
    overlay = pd.read_csv(
        path,
        dtype={"home_team": "string", "away_team": "string", "tournament": "string"},
        parse_dates=["date"],
    )
    if overlay.empty:
        return frame
    mapping = dict(
        zip(_keys(overlay), pd.to_datetime(overlay["kickoff_utc"], utc=True), strict=True)
    )
    if not mapping:
        return frame
    current = pd.to_datetime(frame["kickoff_utc"], utc=True)
    replaced = [
        mapping.get(key, existing)
        for key, existing in zip(_keys(frame), current, strict=True)
    ]
    result = frame.copy()
    result["kickoff_utc"] = pd.to_datetime(pd.Series(replaced, index=frame.index), utc=True)
    return result
