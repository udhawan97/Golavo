"""Per-match World Cup 2026 backtest — never a ledger artifact, never a record.

Each match is replayed at its own ``kickoff - 1s`` cutoff, the same conservative
information boundary the seal and the Match Cockpit replay use, so a row here is
exactly what the app would have said had it been asked that moment. That is the
whole claim: nothing here was called in advance by anyone, and nothing here is
persisted or scored as a seal.

The module is pure — no I/O, no clock, no writes.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

import pandas as pd

from golavo_core.evaluation import FOLDS
from golavo_core.ingest import training_rows
from golavo_core.ingest.snapshot import _order_instants
from golavo_core.models import fit_model

RETROSPECTIVE_SCHEMA_VERSION = "0.1.0"

# Four voices, not five: bivariate_poisson is numerically identical to
# poisson_independent on every recorded fold, so offering both would imply two
# independent opinions where there is one.
RETROSPECTIVE_FAMILIES: tuple[str, ...] = (
    "climatological",
    "elo_ordlogit",
    "poisson_independent",
    "dixon_coles",
)

# The app's own DEFAULT_FAMILY (server/golavo_server/seal.py). The ranking must
# follow the family the app would actually have sealed with; a cross-family
# average would describe a forecast the app never makes.
RANKING_FAMILY = "dixon_coles"

RETROSPECTIVE_LABEL = (
    "Tournament retrospective — every match backtested at its own pre-kickoff cutoff. "
    "A backtest, not a sealed record."
)

_WC2026 = next(fold for fold in FOLDS if fold["fold_id"] == "WC2026")


class RetrospectiveUnavailable(ValueError):
    """The committed snapshot cannot support an honest tournament retrospective."""


class RetrospectiveCancelled(Exception):
    """The caller asked for the run to stop."""


def _utc(value: str | pd.Timestamp) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    return (
        timestamp.tz_localize("UTC")
        if timestamp.tzinfo is None
        else timestamp.tz_convert("UTC")
    )


def _iso(value: pd.Timestamp) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _str_or_none(value: Any) -> str | None:
    return None if value is None or pd.isna(value) else str(value)


def _same_day_proxy_count(train: pd.DataFrame, kickoff: pd.Timestamp) -> int:
    """Training rows that share ``kickoff``'s UTC calendar day via a day-only proxy.

    A ``kickoff_precision`` other than ``"exact"`` — including a missing/``NA``
    precision, which discloses nothing about accuracy and so cannot be assumed
    exact — is a 00:00 UTC stand-in for an unknown real kickoff time, not a
    verified instant. Sharing a calendar day with such a row means this match's
    own ``kickoff - 1s`` cutoff cannot prove the proxy row actually happened
    first — it may have kicked off later the same day. Same-day membership is
    decided by ``_order_instants``, the identical fallback ``training_rows``
    used to admit the row (kickoff_utc, falling back to ``date`` on NaT), so a
    NaT-kickoff row admitted via its date is not silently missed here.
    """
    if train.empty:
        return 0
    precision = (
        train["kickoff_precision"].astype("string")
        if "kickoff_precision" in train.columns
        else pd.Series("day", index=train.index, dtype="string")
    )
    is_proxy_precision = precision.ne("exact").fillna(True)
    same_day = _order_instants(train).dt.date.eq(kickoff.date())
    return int((is_proxy_precision & same_day).sum())


def _outcome(home_score: Any, away_score: Any) -> int:
    """0 = home win, 1 = draw, 2 = away win — matching Prediction.probs order."""
    home, away = int(home_score), int(away_score)
    if home > away:
        return 0
    return 1 if home == away else 2


def _tournament_rows(frame: pd.DataFrame) -> pd.DataFrame:
    kickoff = pd.to_datetime(frame["kickoff_utc"], utc=True)
    start = _utc(_WC2026["window_start"])
    end = _utc(_WC2026["window_end"]) + pd.Timedelta(days=1)
    selected = frame.loc[
        frame["competition"].astype("string").eq(_WC2026["competition"])
        & (kickoff >= start)
        & (kickoff < end)
    ].copy()
    selected["_kickoff"] = pd.to_datetime(selected["kickoff_utc"], utc=True)
    return selected.sort_values(["_kickoff", "match_id"], kind="mergesort")


def world_cup_2026_retrospective(
    frame: pd.DataFrame,
    *,
    progress: Callable[[int, int], None] | None = None,
    is_cancelled: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    """Replay every completed 2026 World Cup match at its own pre-kickoff cutoff."""
    tournament = _tournament_rows(frame)
    complete = tournament.loc[tournament["is_complete"].astype("boolean").fillna(False)]
    pending = int(len(tournament) - len(complete))

    if complete.empty:
        raise RetrospectiveUnavailable(
            "This snapshot has no completed 2026 World Cup matches to look back on."
        )

    total = int(len(complete))
    rows: list[dict[str, Any]] = []
    for done, (_, match) in enumerate(complete.iterrows(), start=1):
        if is_cancelled is not None and is_cancelled():
            raise RetrospectiveCancelled()

        kickoff = _utc(match["kickoff_utc"])
        cutoff = kickoff - pd.Timedelta(seconds=1)
        cutoff_iso = _iso(cutoff)
        match_id = str(match["match_id"])

        # Scope by the fixture's own source_id, exactly as the app's own on-demand
        # path does (server/golavo_server/analysis.py) — never by source_kind,
        # which would silently merge a second international source in were one
        # ever added.
        source_id = _str_or_none(match.get("source_id"))
        source_kind = _str_or_none(match.get("source_kind"))
        competition = _str_or_none(match.get("competition"))
        scoped = frame
        if source_id is not None:
            scoped = frame.loc[frame["source_id"].astype("string").eq(source_id)]
        if source_kind == "club" and competition is not None:
            scoped = scoped.loc[scoped["competition"].astype("string").eq(competition)]

        train = training_rows(scoped, cutoff_iso)
        # Belt-and-braces: never let the fixture's own row train its own forecast,
        # even if a malformed snapshot dated it before the cutoff.
        train = train.loc[~train["match_id"].astype("string").eq(match_id)].copy()
        # This cutoff is the app's own kickoff-1s boundary and stays exactly as
        # inherited from training_rows() — never tightened here. A day-precision
        # (00:00 UTC) row sharing this match's calendar day cannot be proven to
        # have kicked off first, so the exposure is disclosed below rather than
        # hidden by a stricter, non-app cutoff.
        same_day_proxy_rows = _same_day_proxy_count(train, kickoff)

        home = str(match["home_team"])
        away = str(match["away_team"])
        neutral = bool(match.get("neutral") or False)
        outcome = _outcome(match["home_score"], match["away_score"])

        families: dict[str, Any] = {}
        for family in RETROSPECTIVE_FAMILIES:
            fitted = fit_model(family, train, cutoff_iso)
            probs = fitted.predict(home, away, neutral).probs
            assigned = min(max(float(probs[outcome]), 1e-12), 1.0)
            families[family] = {
                "probs": {
                    "home": round(float(probs[0]), 9),
                    "draw": round(float(probs[1]), 9),
                    "away": round(float(probs[2]), 9),
                },
                "log_loss": round(-math.log(assigned), 9),
            }

        rows.append(
            {
                "match_id": match_id,
                "kickoff_utc": _iso(kickoff),
                "kickoff_precision": str(match.get("kickoff_precision") or "day"),
                "information_cutoff_utc": cutoff_iso,
                "home_team": home,
                "away_team": away,
                "home_score": int(match["home_score"]),
                "away_score": int(match["away_score"]),
                "outcome": ("home", "draw", "away")[outcome],
                "families": families,
                "log_loss": families[RANKING_FAMILY]["log_loss"],
                "training_same_day_proxy_rows": same_day_proxy_rows,
            }
        )
        if progress is not None:
            progress(done, total)

    ranked = sorted(rows, key=lambda row: (-row["log_loss"], row["match_id"]))
    status = "complete" if pending == 0 else "partial"
    note = (
        "Every 2026 World Cup match in this snapshot has been played and backtested."
        if pending == 0
        else f"{pending} match(es) in this snapshot are not yet played and are not scored here."
    )
    rows_with_same_day_proxies = sum(
        1 for row in rows if row["training_same_day_proxy_rows"] > 0
    )

    return {
        "schema_version": RETROSPECTIVE_SCHEMA_VERSION,
        "status": "available",
        "label": RETROSPECTIVE_LABEL,
        "tournament_id": "worldcup-2026",
        "tournament_name": "2026 FIFA World Cup",
        "ledger_status": "never_persisted_or_scored_as_a_seal",
        "ranking_family": RANKING_FAMILY,
        "ranking_metric": "log_loss",
        "families": list(RETROSPECTIVE_FAMILIES),
        "window_start": _WC2026["window_start"],
        "window_end": _WC2026["window_end"],
        "coverage": {
            "status": status,
            "scored": total,
            "pending": pending,
            "note": note,
        },
        "exposure": {
            "rows_with_same_day_proxies": rows_with_same_day_proxies,
            "note": (
                "A day-precision kickoff is a 00:00 UTC calendar-day stand-in, not a "
                "verified kickoff time. This backtest still cuts off at kickoff - 1s "
                "for every match, exactly as the app does, so it cannot prove a "
                "same-day proxy row actually happened first — a flagged match's "
                "forecast may rest on a result that was really played later that day."
            ),
        },
        "matches": rows,
        "biggest_surprises": ranked,
    }
