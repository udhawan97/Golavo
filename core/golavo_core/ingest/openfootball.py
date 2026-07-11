"""openfootball (football.json) ingestion into Golavo's canonical match table.

Produces exactly the same typed frame as the martj42 loader so every downstream
model, evaluation, and seal path is source-agnostic. Only a well-formed
``score.ft`` two-integer object counts as a completed result; openfootball's
divergent ``[0, 0]`` list encoding (seen only in the partial 2025-26 capture) is
treated as INCOMPLETE, never fabricated as a real 0-0. See
docs/handoff/openfootball-audit.md.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pandas as pd

from .snapshot import validate_pack

COMPETITION = "English Premier League"
COUNTRY = "England"
_SUFFIX = re.compile(r"\s+(?:FC|AFC)$")
_PREFIX = re.compile(r"^AFC\s+")


def canonical_team(name: str) -> str:
    """Collapse openfootball's cross-season naming drift ('Arsenal FC' -> 'Arsenal')."""
    collapsed = _PREFIX.sub("", str(name).strip())
    return _SUFFIX.sub("", collapsed).strip()


def _extract_ft(match: dict) -> tuple[int, int] | None:
    score = match.get("score")
    if isinstance(score, dict):
        ft = score.get("ft")
        if isinstance(ft, list) and len(ft) == 2 and all(isinstance(x, int) for x in ft):
            return ft[0], ft[1]
    return None


def load_openfootball_table(pack_dir: Path) -> pd.DataFrame:
    """Load a validated openfootball pack into Golavo's deterministic match table."""
    manifest = validate_pack(pack_dir)
    rows: list[dict] = []
    for entry in sorted(manifest["files"], key=lambda e: e["name"]):
        name = entry["name"]
        if not name.endswith(".en.1.json"):
            continue
        data = json.loads((pack_dir / name).read_text(encoding="utf-8"))
        for match in data.get("matches", []):
            ft = _extract_ft(match)
            rows.append(
                {
                    "date": match.get("date"),
                    "time": match.get("time"),
                    "home_team": canonical_team(match.get("team1")),
                    "away_team": canonical_team(match.get("team2")),
                    "home_score": ft[0] if ft is not None else pd.NA,
                    "away_score": ft[1] if ft is not None else pd.NA,
                    "tournament": COMPETITION,
                    "city": pd.NA,
                    "country": COUNTRY,
                    "neutral": False,
                }
            )
    frame = pd.DataFrame(rows)
    frame["date"] = pd.to_datetime(frame["date"])
    frame["home_score"] = frame["home_score"].astype("Int16")
    frame["away_score"] = frame["away_score"].astype("Int16")
    for column in ("home_team", "away_team", "tournament", "city", "country"):
        frame[column] = frame[column].astype("string")
    frame["neutral"] = frame["neutral"].astype("boolean")
    if (frame[["home_score", "away_score"]].dropna() < 0).any().any():
        raise ValueError("openfootball pack contains a negative score")

    frame = frame.sort_values(
        ["date", "home_team", "away_team"], kind="mergesort"
    ).reset_index(drop=True)
    identities = frame.apply(
        lambda r: "|".join(
            [r["date"].date().isoformat(), str(r["home_team"]), str(r["away_team"]), COMPETITION]
        ),
        axis=1,
    )
    occurrences = identities.groupby(identities, sort=False).cumcount()
    frame.insert(
        0,
        "match_id",
        [
            f"m_{hashlib.sha256(f'{identity}|{occurrence}'.encode()).hexdigest()[:16]}"
            for identity, occurrence in zip(identities, occurrences, strict=True)
        ],
    )

    def _kickoff(row: pd.Series) -> pd.Timestamp:
        # openfootball 'time' is venue-local; used as-is for this historical pack.
        clock = row["time"] if isinstance(row["time"], str) and row["time"] else "00:00"
        return pd.Timestamp(f"{row['date'].date().isoformat()}T{clock}:00", tz="UTC")

    frame["kickoff_utc"] = frame.apply(_kickoff, axis=1)
    frame["is_complete"] = frame[["home_score", "away_score"]].notna().all(axis=1)
    return frame.drop(columns=["time"])
