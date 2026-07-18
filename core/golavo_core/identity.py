"""How Golavo identifies a team and a fixture across sources.

Two facts live here, and nowhere else:

* **the fold** — the diacritic-free, casefolded search key written into the
  index as ``home_norm``/``away_norm``; and
* **the fixture key** — ``(day, home, away)`` optionally scoped by a
  competition or tournament, in the three encodings callers need (a scalar
  tuple, a tuple Series, and a pipe-joined string Series for frame joins).

Both were copy-pasted before: the fold into the index builder, the search
reader, result settlement, the fixture check and the World Cup overlay; the key
into five places that each re-derived the day from a different expression.
Result settlement grades a sealed forecast only where two sources agree on a
fixture, so those copies agreeing was load-bearing and enforced by nothing
stronger than a docstring saying "matches ... exactly".

Not here, deliberately:

* :func:`golavo_core.ingest.openfootball.canonical_team` resolves club aliases
  (``TSV 1860 München`` -> ``1860 München``) against league-scoped tables. It is
  a different operation on a different input — the raw upstream spelling before
  it ever reaches the index — and it keeps its tables in the ingest layer.
* The AI and research modules fold with **NFKC** to catch obfuscated digits and
  secrets. That is a safety scan, not an identity, and must not be folded in.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from typing import Any

import pandas as pd

__all__ = [
    "fixture_date",
    "fixture_key",
    "fixture_key_strings",
    "fixture_keys",
    "normalize",
]

# The separator for the string encoding. Team names never contain it, so a
# joined key round-trips to its parts.
_SEP = "|"

_ISO_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}")


def normalize(value: Any) -> str:
    """Fold a team name to the index's search key.

    NFKD decompose -> drop combining marks -> casefold -> strip, so ``Atlético``
    and ``ATLETICO`` collapse and a later search need not reproduce diacritics.
    Idempotent, so an already-folded index column can be passed straight back in.
    """
    decomposed = unicodedata.normalize("NFKD", str(value))
    without_marks = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return without_marks.casefold().strip()


def fixture_date(value: Any) -> str:
    """Coerce any of the caller date shapes to the ``YYYY-MM-DD`` key part.

    A string already starting with an ISO day keeps that day verbatim — a
    ``kickoff_utc`` of ``2026-06-11T23:30:00Z`` keys to the 11th, and is never
    reinterpreted into another timezone's day. Anything else goes through
    pandas.
    """
    if isinstance(value, str) and _ISO_DAY.match(value):
        return value[:10]
    parsed = pd.Timestamp(value)
    if parsed is pd.NaT or pd.isna(parsed):
        raise ValueError(f"unparseable fixture date: {value!r}")
    return parsed.date().isoformat()


def fixture_key(date: Any, home: Any, away: Any, *scope: Any) -> tuple[str, ...]:
    """The identity of one fixture: day, folded home, folded away, folded scope.

    ``scope`` carries the competition or tournament where a caller keys within
    one competition (result settlement) rather than across all of them.
    """
    return (fixture_date(date), normalize(home), normalize(away), *(normalize(s) for s in scope))


def _key_columns(
    frame: pd.DataFrame,
    *,
    date: str,
    home: str,
    away: str,
    scope: Sequence[str],
) -> list[pd.Series]:
    days_column = frame[date]
    # The index build keys 100k rows; a datetime column formats vectorised, and
    # lands on the same day fixture_date would give it.
    if pd.api.types.is_datetime64_any_dtype(days_column):
        days = days_column.dt.strftime("%Y-%m-%d")
    else:
        days = days_column.map(fixture_date)
    folded = [frame[home].map(normalize), frame[away].map(normalize)]
    folded.extend(frame[name].map(normalize) for name in scope)
    return [days, *folded]


def fixture_keys(
    frame: pd.DataFrame,
    *,
    date: str = "date",
    home: str = "home_team",
    away: str = "away_team",
    scope: Sequence[str] = (),
) -> pd.Series:
    """:func:`fixture_key` over a frame, as a Series of tuples on the frame's index."""
    columns = _key_columns(frame, date=date, home=home, away=away, scope=scope)
    return pd.Series(
        list(zip(*(column for column in columns), strict=True)),
        index=frame.index,
        dtype="object",
    )


def fixture_key_strings(
    frame: pd.DataFrame,
    *,
    date: str = "date",
    home: str = "home_team",
    away: str = "away_team",
    scope: Sequence[str] = (),
) -> pd.Series:
    """:func:`fixture_keys` pipe-joined, for merging two frames on the key."""
    columns = _key_columns(frame, date=date, home=home, away=away, scope=scope)
    joined = columns[0].astype(str)
    for column in columns[1:]:
        joined = joined + _SEP + column.astype(str)
    return joined.rename(None)
