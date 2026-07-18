"""Turning parsed rows into the canonical match table.

Every source loader ends the same way: sort for determinism, mint a stable
``match_id``, then declare the kickoff precision the source can actually
support. Only the *identity fields* differ, and they must — martj42 needs the
venue to separate two same-day meetings of the same pair, footballcsv scopes its
identity by source id, and football.txt adds the season. Re-hashing a merged
frame with one shared field list would silently corrupt every id, which is why
:func:`golavo_core.ingest.match_index.build_match_index` keeps each pack's own.

So the fields stay with the loader and the mechanism lives here: the join, the
occurrence numbering that keeps a genuine repeat fixture from collapsing into
one row, and the hash. Before this module the mechanism was copy-pasted into
four loaders, and any change to it had to land in all four at once or the
committed index would move.

This is a *within-source row id*, not the cross-source fixture key in
:mod:`golavo_core.identity`. Names are joined verbatim here — folding them would
merge two distinct clubs whose names differ only by diacritics.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

import pandas as pd

__all__ = ["match_identities", "mint_match_ids", "with_day_precision_kickoff"]

_SEP = "|"


def _as_identity_text(column: pd.Series) -> pd.Series:
    """One identity field as text, formatted by what it is.

    A date contributes its calendar day (the identity is day-precision by
    design, so a later exact-kickoff overlay cannot change an id). A boolean
    contributes Python's ``True``/``False`` text. Everything else is ``str``.
    """
    if pd.api.types.is_datetime64_any_dtype(column):
        return column.dt.date.map(lambda day: day.isoformat())
    if pd.api.types.is_bool_dtype(column):
        return column.map(lambda value: str(bool(value)))
    return column.map(str)


def match_identities(
    frame: pd.DataFrame, columns: Sequence[str], *, prefix: str | None = None
) -> pd.Series:
    """The identity string for each row: the named fields, pipe-joined.

    Raises ``KeyError`` if a named column is absent — an identity silently
    missing a field would mint ids that collide across genuinely different
    fixtures.
    """
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise KeyError(f"identity columns absent from frame: {missing}")

    parts = [_as_identity_text(frame[column]) for column in columns]
    if prefix is not None:
        parts.insert(0, pd.Series(prefix, index=frame.index, dtype="object"))
    joined = parts[0]
    for part in parts[1:]:
        joined = joined + _SEP + part
    return joined


def mint_match_ids(
    frame: pd.DataFrame, columns: Sequence[str], *, prefix: str | None = None
) -> pd.DataFrame:
    """Return ``frame`` with a stable ``match_id`` inserted as its first column.

    Two rows sharing an identity are a genuine repeat fixture, not a duplicate,
    so each occurrence is numbered in frame order and the number enters the
    hash. Callers therefore sort before minting: the order decides which repeat
    is occurrence 0, and the committed index depends on it.
    """
    identities = match_identities(frame, columns, prefix=prefix)
    occurrences = identities.groupby(identities, sort=False).cumcount()
    result = frame.copy()
    result.insert(
        0,
        "match_id",
        [
            f"m_{hashlib.sha256(f'{identity}|{occurrence}'.encode()).hexdigest()[:16]}"
            for identity, occurrence in zip(identities, occurrences, strict=True)
        ],
    )
    return result


def with_day_precision_kickoff(frame: pd.DataFrame) -> pd.DataFrame:
    """Declare a day-precision kickoff and derive completeness.

    Upstream clocks in these sources are venue-local and the packs carry no
    venue timezone, so the date's midnight UTC is the only honest instant:
    labelling a naive local clock as UTC would be a false instant and could move
    a pre-kickoff cutoff by hours. A pack shipping a real kickoff overlay
    sharpens this afterwards via :func:`golavo_core.ingest.apply_exact_kickoffs`.
    """
    result = frame.copy()
    result["kickoff_utc"] = pd.to_datetime(result["date"], utc=True)
    result["kickoff_precision"] = pd.Series("day", index=result.index, dtype="string")
    result["is_complete"] = result[["home_score", "away_score"]].notna().all(axis=1)
    return result
