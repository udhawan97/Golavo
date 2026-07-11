"""The numeric whitelist — Golavo's core AI guard.

Every number the AI is allowed to utter is enumerated in a MatchEvidenceBundle's
``allowed_numbers`` list. This module scans model-produced text and reports any
numeric value that does NOT resolve to one of those allowed values, in either
digit or spelled-out form. A single unsupported number is fatal: the caller
rejects the whole narration and falls back to local-only. The engine owns the
numbers; the guard's job is to guarantee the AI never adds one.

Design notes
------------
* Formatting tolerance is one-directional and safe: a token matches an allowed
  value only if it equals that value rounded to 0–6 decimals. The model may
  round DOWN in precision ("45.2%" for 45.234) but can never invent precision or
  a different value. There is no additive slop, so "46%" never matches "45%".
* A tiny set of fixed domain tokens ("1X2", the horizon labels) are constant
  terminology, not numeric claims, and are removed before scanning. They are
  exact string literals, so this cannot smuggle an arbitrary number.
* Spelled-out numbers from "three" upward (plus multipliers and large-unit
  words) are also checked. "one"/"two"/"first"/"second"/"half" are deliberately
  NOT treated as numeric claims — they are ordinary prose — but their digit
  forms ("1", "2") are still scanned. This bound is documented, not hidden.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

# Constant terminology that contains digits but is not a numeric claim. Removed
# (case-insensitively) before number extraction. Exact literals only.
_TERMINOLOGY = ("1x2_regulation", "1x2", "t-72h", "t-24h", "t-60m")

# Betting / gambling lexicon. Presence of any of these (whole word) rejects the
# narration outright — Golavo forecasts, it does not tip. The first five are the
# contract's named terms; the rest close obvious synonyms. Conservative by
# design: a false positive only costs the optional AI narration, never a number.
_BETTING_TERMS = (
    "odds",
    "lock",
    "locks",
    "value",
    "unit",
    "units",
    "pick",
    "picks",
    "bet",
    "bets",
    "betting",
    "bettor",
    "wager",
    "wagers",
    "stake",
    "stakes",
    "parlay",
    "accumulator",
    "acca",
    "moneyline",
    "spread",
    "handicap",
    "bookmaker",
    "bookie",
    "vig",
    "juice",
    "bankroll",
    "punt",
    "punter",
    "ev",
    "edge",
    "tip",
    "tips",
    "tipster",
)
_BETTING_RE = re.compile(r"(?i)(?<![a-z])(" + "|".join(_BETTING_TERMS) + r")(?![a-z])")

# Digit-form numbers: an optional sign, at least one digit, optional thousands
# groups, optional decimal fraction, optional trailing percent. The lookbehind
# stops mid-token matches and splits scorelines like "2-0" into 2 and 0.
_NUMBER_RE = re.compile(r"(?<![\w.])[-+]?\d[\d,]*(?:\.\d+)?%?")

_WORD_UNITS = {
    "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19,
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
    "seventy": 70, "eighty": 80, "ninety": 90,
    "hundred": 100, "thousand": 1000, "million": 1_000_000,
    "billion": 1_000_000_000,
    "dozen": 12,
    "twice": 2, "double": 2, "triple": 3, "treble": 3, "quadruple": 4,
    "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7,
    "eighth": 8, "ninth": 9, "tenth": 10, "eleventh": 11, "twelfth": 12,
    "thrice": 3,
}
_WORD_ALTERNATION = "|".join(sorted(_WORD_UNITS, key=len, reverse=True))
_WORD_RE = re.compile(r"(?i)(?<![a-z])(" + _WORD_ALTERNATION + r")(?![a-z])")


def _strip_terminology(text: str) -> str:
    stripped = text
    for token in _TERMINOLOGY:
        stripped = re.sub(re.escape(token), " ", stripped, flags=re.IGNORECASE)
    return stripped


def _strip_literals(text: str, literals: Iterable[str]) -> str:
    stripped = text
    # Longest first so "Schalke 04" is removed before a bare "04" would be.
    unique = {str(item) for item in literals if str(item).strip()}
    for literal in sorted(unique, key=len, reverse=True):
        stripped = re.sub(re.escape(literal), " ", stripped, flags=re.IGNORECASE)
    return stripped


def extract_numbers(text: str, safe_literals: Iterable[str] = ()) -> list[float]:
    """Return every numeric value in ``text``, digit and spelled-out forms.

    Percent signs and thousands separators are stripped to a bare magnitude;
    "45.2%" and "45.2" both yield 45.2. Fixed terminology and any ``safe_literals``
    (exact identifier strings from the trusted bundle — team names like
    "Schalke 04", competition names, source ids — that the model may echo
    verbatim) are removed first so their embedded digits are not misread as
    numeric claims. Only exact-string literals are removed, so this can never
    launder an arbitrary fabricated number.
    """
    # NFKC folds fullwidth/superscript/other Unicode digit forms to ASCII so a
    # fabricated number cannot slip past the scanner disguised as "５０" or "⁷".
    normalized = unicodedata.normalize("NFKC", text)
    cleaned = _strip_literals(_strip_terminology(normalized), safe_literals)
    values: list[float] = []
    for match in _NUMBER_RE.finditer(cleaned):
        token = match.group().rstrip("%").replace(",", "")
        try:
            values.append(float(token))
        except ValueError:  # pragma: no cover - regex guarantees parseability
            continue
    for match in _WORD_RE.finditer(cleaned):
        values.append(float(_WORD_UNITS[match.group().lower()]))
    return values


def number_matches(token: float, allowed: float) -> bool:
    """True if ``token`` equals ``allowed`` at some rounding to 0–6 decimals.

    One-directional: the model may present ``allowed`` with equal or lower
    precision, never a different value and never invented precision.
    """
    for places in range(7):
        if abs(token - round(allowed, places)) < 1e-9:
            return True
    return abs(token - allowed) < 1e-9


def unsupported_numbers(
    text: str, allowed_values: list[float], safe_literals: Iterable[str] = ()
) -> list[float]:
    """Numbers in ``text`` that resolve to no allowed value (empty == clean)."""
    allowed = [float(value) for value in allowed_values]
    unsupported: list[float] = []
    for token in extract_numbers(text, safe_literals):
        if not any(number_matches(token, value) for value in allowed):
            unsupported.append(token)
    return unsupported


def contains_betting_lexicon(text: str) -> list[str]:
    """Betting/gambling terms found in ``text`` (empty == clean)."""
    return [match.group().lower() for match in _BETTING_RE.finditer(text)]


# Secret / credential shapes. The model never receives any key (the gateway
# never puts one in the prompt), so this is defence-in-depth: if a narration
# ever contains something key-shaped — whether hallucinated or coaxed by an
# injection — it is rejected outright rather than shown to the user.
_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{12,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{8,}"),
    re.compile(r"(?i)-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)\b(api[_-]?key|secret[_-]?key|access[_-]?token|bearer)\b\s*[:=]"),
    re.compile(r"(?i)\b(OPENAI|ANTHROPIC|AWS|GOLAVO)[_A-Z]*(KEY|TOKEN|SECRET)\b"),
)


def contains_secret_pattern(text: str) -> list[str]:
    """Credential-shaped substrings found in ``text`` (empty == clean)."""
    found: list[str] = []
    for pattern in _SECRET_PATTERNS:
        found.extend(match.group(0) for match in pattern.finditer(text))
    return found
