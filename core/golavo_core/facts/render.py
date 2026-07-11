"""Number rendering that keeps a fact's prose and its whitelist in lockstep.

Every number a fact states is created through a :class:`NumberBag`. The bag
returns the exact ``display`` string to interpolate into the fact text AND
records the machine-readable ``value``/``unit``/``display`` triple. When a fact
is later folded into an AI evidence bundle, those recorded numbers become the
whitelist entries — so the digits in the prose and the digits the model is
allowed to utter are, by construction, the same set.

Dates never go through here: they carry digits that are not claims, so facts put
calendar dates only in their structured ``date_range`` field, never in ``text``.
"""

from __future__ import annotations

import re

_KEY_RE = re.compile(r"[a-z][a-z0-9_]*\Z")
_UNITS = ("percent", "goals", "count")


class NumberBag:
    """Collects the numbers a single fact states, each keyed and display-exact."""

    def __init__(self) -> None:
        self._items: list[dict[str, object]] = []
        self._keys: set[str] = set()

    def _add(self, key: str, value: float, unit: str, display: str) -> str:
        if not _KEY_RE.match(key):
            raise ValueError(f"number key must match [a-z][a-z0-9_]*: {key!r}")
        if unit not in _UNITS:
            raise ValueError(f"unsupported number unit: {unit!r}")
        if key in self._keys:
            raise ValueError(f"duplicate number key within one fact: {key!r}")
        self._keys.add(key)
        self._items.append({"key": key, "value": value, "unit": unit, "display": display})
        return display

    def count(self, key: str, value: int) -> str:
        """A plain integer count (matches, goals, meetings). No thousands separator."""
        integer = int(value)
        return self._add(key, integer, "count", str(integer))

    def percent(self, key: str, fraction: float, *, decimals: int = 1) -> str:
        """A rate given as a fraction in [0, 1], rendered as a percentage string."""
        pct = round(float(fraction) * 100.0, 6)
        display = f"{float(fraction) * 100.0:.{decimals}f}%"
        return self._add(key, pct, "percent", display)

    def goals(self, key: str, value: float, *, decimals: int = 1) -> str:
        """A goals-per-something rate, rendered to fixed decimals."""
        display = f"{float(value):.{decimals}f}"
        return self._add(key, round(float(value), 6), "goals", display)

    def items(self) -> list[dict[str, object]]:
        """The recorded numbers, in insertion order."""
        return [dict(item) for item in self._items]
