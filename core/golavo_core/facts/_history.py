"""Read-only views over the canonical match table for the fact templates.

Everything here is a pure function of a match-table slice. Nothing writes, and
nothing here (or anywhere in this package) may import the forecast, model, or
calibration code — that isolation is what the machine-checked no-write invariant
in ``golavo_core.facts.invariant`` verifies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class TemplateContext:
    """The as-of snapshot a template computes against.

    ``matches`` is already restricted to completed fixtures whose kickoff is at
    or before ``as_of`` — the same information horizon the sealed forecast used —
    so a template can never read a result the forecast could not.
    """

    matches: pd.DataFrame
    home_team: str
    away_team: str
    competition: str
    neutral: bool
    as_of: pd.Timestamp
    kickoff: pd.Timestamp
    source_ids: tuple[str, ...]
    goalscorers: pd.DataFrame | None = None
    shootouts: pd.DataFrame | None = None


@dataclass
class Candidate:
    """A template's proposed fact, before the guardrails accept or suppress it."""

    subject: str
    text: str
    values: dict[str, Any]
    numbers: list[dict[str, Any]]
    sample_n: int
    denominator: int
    first_date: pd.Timestamp
    last_date: pd.Timestamp
    specificity: float
    base_rate: float | None = None
    extra: dict[str, Any] = field(default_factory=dict)


_PERSPECTIVE_COLUMNS = [
    "date",
    "kickoff_utc",
    "opponent",
    "is_home",
    "gf",
    "ga",
    "ht_gf",
    "ht_ga",
    "result",
    "neutral",
    "tournament",
]


def team_perspective(matches: pd.DataFrame, team: str) -> pd.DataFrame:
    """Return ``team``'s completed matches from its own perspective, oldest first.

    Columns: date, kickoff_utc, opponent, is_home, gf (goals for), ga (goals
    against), ht_gf / ht_ga (nullable half-time scores), result (W/D/L),
    neutral, tournament.
    """
    home_mask = matches["home_team"].eq(team)
    away_mask = matches["away_team"].eq(team)
    sel = matches.loc[home_mask | away_mask]
    if sel.empty:
        return pd.DataFrame(columns=_PERSPECTIVE_COLUMNS)
    is_home = sel["home_team"].eq(team).to_numpy()
    gf = np.where(is_home, sel["home_score"], sel["away_score"]).astype(int)
    ga = np.where(is_home, sel["away_score"], sel["home_score"]).astype(int)
    opponent = np.where(is_home, sel["away_team"], sel["home_team"])
    result = np.select([gf > ga, gf == ga], ["W", "D"], default="L")
    if {"ht_home_score", "ht_away_score"} <= set(sel.columns):
        home = sel["ht_home_score"].astype("Int16")
        away = sel["ht_away_score"].astype("Int16")
        orientation = pd.Series(is_home, index=sel.index)
        ht_gf = home.where(orientation, away).reset_index(drop=True)
        ht_ga = away.where(orientation, home).reset_index(drop=True)
    else:
        ht_gf = pd.Series(pd.NA, index=range(len(sel)), dtype="Int16")
        ht_ga = pd.Series(pd.NA, index=range(len(sel)), dtype="Int16")
    out = pd.DataFrame(
        {
            "date": sel["date"].to_numpy(),
            "kickoff_utc": sel["kickoff_utc"].to_numpy(),
            "opponent": opponent,
            "is_home": is_home,
            "gf": gf,
            "ga": ga,
            "ht_gf": ht_gf,
            "ht_ga": ht_ga,
            "result": result,
            "neutral": sel["neutral"].astype("boolean").fillna(False).astype(bool).to_numpy(),
            "tournament": sel["tournament"].to_numpy(),
        }
    )
    return out.sort_values("date", kind="mergesort").reset_index(drop=True)


def head_to_head(matches: pd.DataFrame, home_team: str, away_team: str) -> pd.DataFrame:
    """Completed meetings between the two teams in either orientation, oldest first."""
    pair = (
        matches["home_team"].eq(home_team) & matches["away_team"].eq(away_team)
    ) | (matches["home_team"].eq(away_team) & matches["away_team"].eq(home_team))
    return matches.loc[pair].sort_values("date", kind="mergesort").reset_index(drop=True)


def trailing_run(flags: list[bool]) -> int:
    """Length of the run of ``True`` values at the end of ``flags``."""
    run = 0
    for flag in reversed(flags):
        if flag:
            run += 1
        else:
            break
    return run


def as_date_iso(value: Any) -> str:
    """Render a pandas/py datetime as a bare ``YYYY-MM-DD`` calendar date."""
    return pd.Timestamp(value).date().isoformat()


def as_utc_iso(value: Any) -> str:
    """Render a timestamp as a Z-suffixed UTC instant."""
    ts = pd.Timestamp(value)
    ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
    return ts.isoformat().replace("+00:00", "Z")


def clamp_unit(value: float) -> float:
    """Clamp a score into the documented [0, 1] specificity range."""
    return float(min(1.0, max(0.0, value)))
