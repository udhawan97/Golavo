"""The numeric whitelist — Golavo's core AI guard.

Every number the AI is allowed to utter is enumerated in a MatchEvidenceBundle's
``allowed_numbers`` list. This module scans model-produced text and reports any
numeric value that does NOT resolve to one of those allowed values, in either
digit or spelled-out form. A single unsupported number is fatal: the caller
rejects the whole narration and falls back to local-only. The engine owns the
numbers; the guard's job is to guarantee the AI never adds one.

Design notes
------------
* Served narration is stricter than the low-level numeric helpers: every digit
  token must exactly equal the trusted ``display`` of a number referenced by
  that same claim. This binds value, unit, and citation together.
* A tiny set of fixed domain tokens ("1X2", the horizon labels) are constant
  terminology, not numeric claims, and are removed before scanning. They are
  exact string literals, so this cannot smuggle an arbitrary number.
* Narration rejects spelled-out numeric language and fraction notation outright;
  the fixed prompt requires exact digit-form displays instead. The legacy
  ``extract_numbers`` helper retains its bounded prose-oriented parsing for
  quote grounding, but it is not the served-narration gate.
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
    # "edge" deliberately omitted: "have the edge", "an edge in midfield" is core
    # sports-analysis vocabulary, not wagering. (Betting is a per-claim soft drop
    # now, but a word this common should not be flagged at all.)
    "tip",
    "tips",
    "tipster",
)
_BETTING_RE = re.compile(r"(?i)(?<![a-z])(" + "|".join(_BETTING_TERMS) + r")(?![a-z])")

# Digit-form numbers: an optional sign, at least one digit, optional thousands
# groups, optional decimal fraction, optional trailing percent. The lookbehind
# stops mid-token matches and splits scorelines like "2-0" into 2 and 0.
_NUMBER_RE = re.compile(
    r"(?<![\w.])[-+]?(?:\d[\d,]*(?:\.\d+)?|\.\d+)(?:[eE][-+]?\d+)?%?"
)
_FRACTION_RE = re.compile(r"\d+\s*[⁄/]\s*\d+")

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
_NARRATION_NUMBER_WORDS = (
    *tuple(_WORD_UNITS),
    "zero",
    "one",
    "two",
    "first",
    "second",
    "half",
    "halves",
    "quarter",
    "quarters",
    "couple",
    "pair",
    # "both" is deliberately NOT here: "both teams scored" is idiomatic football
    # prose, not a numeric claim — treating it as the number 2 was a false positive
    # that dropped otherwise-verified claims. (Same spirit as one/two being prose.)
)
_NARRATION_WORD_ALTERNATION = "|".join(
    sorted(_NARRATION_NUMBER_WORDS, key=len, reverse=True)
)
_NARRATION_WORD_RE = re.compile(
    r"(?i)(?<![a-z])(" + _NARRATION_WORD_ALTERNATION + r")(?![a-z])"
)


def _strip_terminology(text: str) -> str:
    stripped = text
    for token in _TERMINOLOGY:
        stripped = re.sub(re.escape(token), " ", stripped, flags=re.IGNORECASE)
    return stripped


def _strip_literals(text: str, literals: Iterable[str]) -> str:
    stripped = text
    # Longest first so "Schalke 04" is removed before a bare "04" would be.
    # A pure numeric literal (for example a stage named "2026") must never
    # become a laundering primitive. Trusted identifiers are stripped only when
    # they contain an alphabetic component, as real team/source labels do.
    unique = {
        str(item)
        for item in literals
        if str(item).strip() and any(char.isalpha() for char in str(item))
    }
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


def unsupported_number_tokens(
    text: str,
    allowed_numbers: list[dict[str, object]],
    number_refs: Iterable[str],
    safe_literals: Iterable[str] = (),
) -> list[str]:
    """Return numeric tokens that are not exact displays of referenced numbers.

    Model text is less trustworthy than the structured ``number_refs`` field.
    A token therefore passes only when it exactly equals the trusted ``display``
    string of a number referenced by that same claim. This binds value, unit,
    and citation together: ``1.2%`` cannot borrow an allowed ``1.2`` goals value,
    and ``45.0`` cannot borrow an allowed ``45.0%`` probability.

    Spelled-out numbers and fraction notation are rejected outright. The fixed
    prompt already requires exact digit-form displays, and failing closed avoids
    ambiguous compound forms such as ``twenty-five`` or ``three hundred``.
    """
    normalized = unicodedata.normalize("NFKC", text)
    cleaned = _strip_literals(_strip_terminology(normalized), safe_literals)
    refs = set(number_refs)
    allowed_displays = {
        unicodedata.normalize("NFKC", str(item["display"]))
        for item in allowed_numbers
        if str(item.get("id")) in refs
    }

    unsupported = [match.group(0) for match in _FRACTION_RE.finditer(cleaned)]
    unsupported.extend(match.group(0) for match in _NARRATION_WORD_RE.finditer(cleaned))
    for match in _NUMBER_RE.finditer(cleaned):
        token = match.group(0)
        # Numbers inside a fraction are already rejected as one semantic token.
        if any(start <= match.start() < end for start, end in (
            fraction.span() for fraction in _FRACTION_RE.finditer(cleaned)
        )):
            continue
        if token not in allowed_displays:
            unsupported.append(token)
    return unsupported


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


# Zero-width and formatting characters an attacker could splice inside a word to
# dodge a whole-word scan ("u<zwsp>nits"). Removed before the betting/secret
# scans, alongside NFKC folding, so obfuscated forms are caught like plain ones.
# Soft hyphen, the U+200B–U+200F zero-width/bidi set, word joiner, and BOM.
_INVISIBLE_RE = re.compile("[­​-‏⁠﻿]")


def _normalize_for_scan(text: str) -> str:
    """NFKC-fold and strip invisible characters before a lexical scan.

    Mirrors the numeric scanner's NFKC step so the betting and secret gates cannot
    be bypassed with fullwidth glyphs or zero-width splices.
    """
    return _INVISIBLE_RE.sub("", unicodedata.normalize("NFKC", text))


def contains_betting_lexicon(text: str) -> list[str]:
    """Betting/gambling terms found in ``text`` (empty == clean)."""
    return [match.group().lower() for match in _BETTING_RE.finditer(_normalize_for_scan(text))]


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
    scanned = _normalize_for_scan(text)
    found: list[str] = []
    for pattern in _SECRET_PATTERNS:
        found.extend(match.group(0) for match in pattern.finditer(scanned))
    return found
