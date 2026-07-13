"""Validate and defang a raw model narration against its evidence bundle.

``review_narration`` is the deterministic gate between an LLM's output and the
user. It never trusts the model. It:

  * strips chain-of-thought before anything else, so hidden reasoning can never
    surface;
  * validates the structure against the AiNarration JSON schema;
  * HARD-REJECTS the whole narration on any unsupported number or betting term
    (the caller then retries once and falls back to local-only);
  * DROPS individual claims that cite no known source or leak reasoning;
  * gates optional candidate_facts on quote-grounding, and drops them entirely
    unless explicitly enabled.

A hard reject yields ``accepted=False`` with reasons; the gateway turns that into
the local-only fallback. Zero unsupported numbers can reach an accepted result.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from typing import Any

from golavo_core.ai.whitelist import (
    contains_betting_lexicon,
    contains_secret_pattern,
    extract_numbers,
    number_matches,
    unsupported_number_tokens,
)

NARRATION_SCHEMA_VERSION = "0.2.0"

# Keys that may carry model reasoning. Removed everywhere before validation so a
# model that volunteers a scratchpad still yields a clean, schema-valid result
# rather than leaking it. The schema's additionalProperties:false would reject
# them, but stripping is more robust than failing the whole call.
_COT_KEYS = frozenset(
    {
        "reasoning", "reason", "thoughts", "thought", "chain_of_thought", "cot",
        "analysis", "scratchpad", "reflection", "deliberation", "internal",
        "rationale", "thinking", "plan", "planning", "notes", "explanation",
        "explanation_of_reasoning", "steps", "work",
    }
)
_COT_MARKER_RE = re.compile(r"(?i)</?think|<\|.*?\|>|chain[-_ ]of[-_ ]thought")

# The wire schema (ai_narration.schema.json) is additionalProperties:false at every
# level. Small local models routinely decorate items with harmless extras — an
# ``id``, a ``kind``, a ``confidence`` — which would hard-reject an otherwise good
# narration. We prune to these known keys before validation, exactly as _strip_cot
# strips reasoning keys. Safety is untouched: every served field is rebuilt from
# known keys in the reviewers below, so a pruned extra could never reach the user.
_TOP_KEYS = frozenset({"claims", "scenarios", "candidate_facts", "background"})
_ITEM_KEYS = {
    "claims": frozenset({"text", "source_ids", "number_refs"}),
    "scenarios": frozenset({"text", "source_ids", "number_refs"}),
    "candidate_facts": frozenset({"text", "quote", "source_url"}),
    "background": frozenset({"text", "about"}),
}


def _prune_unknown(narration: Any) -> Any:
    """Drop keys the wire schema does not define, at every object level."""
    if not isinstance(narration, dict):
        return narration
    out = {key: value for key, value in narration.items() if key in _TOP_KEYS}
    for key, allowed in _ITEM_KEYS.items():
        items = out.get(key)
        if isinstance(items, list):
            out[key] = [
                {k: v for k, v in item.items() if k in allowed}
                if isinstance(item, dict)
                else item
                for item in items
            ]
    return out


# Wire-schema string bounds, mirrored so a per-item conform can drop an item that
# would hard-reject the whole narration at the schema gate. Keep in sync with
# ai_narration.schema.json.
_TEXT_MAX = {"claim": 600, "fact_text": 400, "fact_quote": 600, "fact_url": 400}


def _clean_str_list(value: Any) -> list[str]:
    """Non-empty string items only (the wire schema forbids empty ref/source ids)."""
    if not isinstance(value, list):
        return []
    return [s for s in value if isinstance(s, str) and s.strip()]


def _conform_claim(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    text = item.get("text")
    if not (isinstance(text, str) and 1 <= len(text) <= _TEXT_MAX["claim"]):
        return None
    return {
        "text": text,
        "source_ids": _clean_str_list(item.get("source_ids")),
        "number_refs": _clean_str_list(item.get("number_refs")),
    }


def _conform_fact(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    text, quote, url = item.get("text"), item.get("quote"), item.get("source_url")
    if not (isinstance(text, str) and 1 <= len(text) <= _TEXT_MAX["fact_text"]):
        return None
    if not (isinstance(quote, str) and 1 <= len(quote) <= _TEXT_MAX["fact_quote"]):
        return None
    if not (isinstance(url, str) and 1 <= len(url) <= _TEXT_MAX["fact_url"]):
        return None
    return {"text": text, "quote": quote, "source_url": url}


def _conform_arrays(
    cleaned: dict[str, Any], *, allow_candidate_facts: bool, dropped: list[str]
) -> None:
    """Drop items that would fail the wire schema STRUCTURALLY, in place.

    A small local model sometimes emits an empty quote, an over-long claim, or a
    stray empty ref — any one of which hard-rejects the whole narration at the
    strict schema gate. Dropping just the offending item keeps the good ones; the
    content guards (numbers, betting, citations) still run per surviving item.
    """
    for key in ("claims", "scenarios"):
        items = cleaned.get(key)
        if isinstance(items, list):
            conformed = [c for c in (_conform_claim(i) for i in items) if c is not None]
            if len(conformed) != len(items):
                dropped.append(f"{key}: dropped {len(items) - len(conformed)} malformed item(s)")
            cleaned[key] = conformed
        else:
            cleaned[key] = []
    raw_facts = cleaned.get("candidate_facts")
    if not allow_candidate_facts:
        # Disabled anyway — never let a malformed disabled fact fail the gate.
        if isinstance(raw_facts, list) and raw_facts:
            dropped.append(
                f"candidate_facts: dropped {len(raw_facts)} "
                "(candidate-fact ingestion is disabled)"
            )
        cleaned["candidate_facts"] = []
    elif isinstance(raw_facts, list):
        cleaned["candidate_facts"] = [f for f in (_conform_fact(i) for i in raw_facts) if f]
    else:
        cleaned["candidate_facts"] = []


@dataclass
class NarrationReview:
    """Outcome of reviewing one raw narration."""

    accepted: bool
    narration: dict[str, Any] | None
    rejections: list[str] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)


def _schema() -> dict[str, Any]:
    import json

    from golavo_core.resources import narration_schema_path

    return json.loads(narration_schema_path().read_text(encoding="utf-8"))


def _safe_literals(bundle: dict[str, Any]) -> list[str]:
    """Exact identifier strings the model may echo verbatim (see whitelist).

    Team/competition names, cities, and source identifiers can legitimately
    contain digits ("Schalke 04", "1. FC Köln", a snapshot id). They are trusted
    literals from the bundle, so their embedded digits are not numeric claims.
    """
    match = bundle["match"]
    literals: list[str] = []
    for key in ("home_team", "away_team", "competition", "stage", "city", "country"):
        value = match.get(key)
        if value:
            literals.append(str(value))
    for source in bundle["sources"]:
        literals.append(str(source["source_id"]))
        literals.append(str(source["title"]))
    return literals


def _strip_cot(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _strip_cot(v) for k, v in value.items() if k.lower() not in _COT_KEYS}
    if isinstance(value, list):
        return [_strip_cot(item) for item in value]
    return value


def _review_item(
    item: dict[str, Any],
    *,
    kind: str,
    index: int,
    allowed_numbers: list[dict[str, Any]],
    safe_literals: list[str],
    source_ids: set[str],
    allowed_number_ids: set[str],
    rejections: list[str],
    dropped: list[str],
) -> dict[str, Any] | None:
    text = item["text"]
    label = f"{kind}[{index}]"

    # Hard reject: credential shapes void the entire narration (fail closed). A key
    # or token leaking anywhere is categorically unacceptable and unambiguous.
    if contains_secret_pattern(text):
        rejections.append(f"{label}: credential-shaped content")

    # Soft drops: remove just this claim, keep the rest. Each of these removes the
    # offending claim so its content never reaches the user, while other verified
    # claims still stand — a small local model that trips one check on one fact
    # must not blank the whole read. The guarantees are intact: a claim survives
    # ONLY if it is clean.
    #
    # Betting/gambling language is dropped per-claim (was a whole-read reject): an
    # analytical idiom like "have the edge" should not delete six good claims, and
    # any genuine wagering phrasing is still never shown.
    betting = contains_betting_lexicon(text)
    if betting:
        dropped.append(f"{label}: dropped (betting lexicon {sorted(set(betting))})")
        return None
    if _COT_MARKER_RE.search(text):
        dropped.append(f"{label}: dropped (chain-of-thought marker in text)")
        return None
    valid_sources = [sid for sid in item["source_ids"] if sid in source_ids]
    if not valid_sources:
        dropped.append(f"{label}: dropped (no citation resolves to a bundle source)")
        return None

    # PRUNE the number_refs to only those that are genuinely usable: a real allowed
    # id, whose trusted source this claim cites, AND whose display actually appears
    # in the text. A small model routinely OVER-TAGS — referencing a number it
    # alluded to qualitatively but never wrote. A dangling ref is pruned (no chip),
    # not fatal, so a good qualitative claim survives instead of being dropped.
    number_by_id = {str(number["id"]): number for number in allowed_numbers}
    final_refs = [
        ref
        for ref in item["number_refs"]
        if ref in number_by_id
        and set(number_by_id[ref]["source_ids"]).intersection(valid_sources)
        and str(number_by_id[ref]["display"]) in text
    ]
    # Every numeric token in the text must still be backed by a SURVIVING ref's
    # exact display — otherwise the claim states an unsupported/fabricated number
    # and is dropped so it never reaches the user. This is the number guarantee.
    bad_numbers = unsupported_number_tokens(text, allowed_numbers, final_refs, safe_literals)
    if bad_numbers:
        dropped.append(
            f"{label}: dropped ({len(bad_numbers)} numeric token(s) not backed by a "
            "cited allowed number)"
        )
        return None

    return {"text": text, "source_ids": valid_sources, "number_refs": final_refs}


def _review_candidate_fact(
    fact: dict[str, Any],
    *,
    index: int,
    allowed_values: list[float],
    safe_literals: list[str],
    rejections: list[str],
) -> dict[str, Any] | None:
    text = fact["text"]
    quote = fact["quote"]
    label = f"candidate_facts[{index}]"
    betting = contains_betting_lexicon(text) + contains_betting_lexicon(quote)
    if betting:
        rejections.append(f"{label}: betting lexicon {sorted(set(betting))}")
        return None
    if contains_secret_pattern(text) or contains_secret_pattern(quote):
        rejections.append(f"{label}: credential-shaped content")
        return None
    # Quote-grounding: any number the candidate fact asserts must appear verbatim
    # in the quoted source text OR be an allowed engine number. Otherwise it is a
    # fabricated statistic and the whole narration fails closed.
    quote_numbers = extract_numbers(quote, safe_literals)
    for token in extract_numbers(text, safe_literals):
        grounded = any(number_matches(token, q) for q in quote_numbers) or any(
            number_matches(token, v) for v in allowed_values
        )
        if not grounded:
            rejections.append(f"{label}: number {token} not grounded in the quote")
            return None
    return {"text": text, "quote": quote, "source_url": fact["source_url"]}


_BG_MAX_NOTES = 4  # mirrors the wire schema's background maxItems.
_BG_MAX_TEXT = 360  # mirrors the wire schema's BackgroundNote.text maxLength.


def _review_background_note(
    note: Any,
    *,
    index: int,
    safe_literals: list[str],
    dropped: list[str],
) -> dict[str, Any] | None:
    """Review one background note under a ZERO-number whitelist.

    The background lane carries qualitative colour from the model's own general
    knowledge — never a number. Any digit, spelled-out number, or fraction, any
    betting term, credential shape, or chain-of-thought marker DROPS the note.
    Crucially this NEVER hard-rejects the narration: a bad note is silently
    deleted (audited in ``dropped``) while the grounded lanes keep their existing
    hard-reject semantics. The allowed-number set is the empty list, hard-coded —
    it must never share the grounded lane's allowed_numbers. Because the lane is
    validated here rather than by the wire schema (see ``review_narration``), this
    also enforces the note's own shape (a dict with a 1–360 char ``text``).
    """
    label = f"background[{index}]"
    if not isinstance(note, dict) or not isinstance(note.get("text"), str):
        dropped.append(f"{label}: dropped (malformed background note)")
        return None
    text = note["text"]
    if not 1 <= len(text) <= _BG_MAX_TEXT:
        dropped.append(f"{label}: dropped (text length out of range)")
        return None
    # Empty allowed set + empty refs => EVERY number token is unsupported.
    if unsupported_number_tokens(text, [], [], safe_literals):
        dropped.append(f"{label}: dropped (background must be numberless)")
        return None
    if contains_betting_lexicon(text):
        dropped.append(f"{label}: dropped (betting lexicon)")
        return None
    if contains_secret_pattern(text):
        dropped.append(f"{label}: dropped (credential-shaped content)")
        return None
    if _COT_MARKER_RE.search(text):
        dropped.append(f"{label}: dropped (chain-of-thought marker)")
        return None
    out: dict[str, Any] = {"text": text}
    about = note.get("about")
    if about in ("home", "away", "match"):
        out["about"] = about
    return out


def review_narration(
    raw: Any,
    bundle: dict[str, Any],
    *,
    allow_candidate_facts: bool = False,
    allow_background: bool = False,
) -> NarrationReview:
    """Review a raw model output against ``bundle``; see module docstring."""
    from jsonschema import Draft202012Validator, ValidationError

    rejections: list[str] = []
    dropped: list[str] = []

    if not isinstance(raw, dict):
        return NarrationReview(False, None, ["output is not a JSON object"], dropped)

    cleaned = _prune_unknown(_strip_cot(copy.deepcopy(raw)))
    # The optional background lane is validated per-note below, NOT by the wire
    # schema gate — pop it out first so a malformed note (too many, over-length,
    # bad `about`) can never hard-reject the grounded claims it rides alongside.
    raw_background = cleaned.pop("background", None)
    # Conform each array to the wire schema's structural rules BEFORE the gate, so a
    # single sloppy item from a small local model (an empty quote, an over-long
    # claim, a stray empty ref) drops just itself instead of blanking the whole
    # read. Content rules (numbers, citations) are still enforced per-item below.
    _conform_arrays(cleaned, allow_candidate_facts=allow_candidate_facts, dropped=dropped)
    try:
        Draft202012Validator(_schema()).validate(cleaned)
    except ValidationError as exc:
        path = "/".join(str(part) for part in exc.absolute_path)
        return NarrationReview(False, None, [f"schema: {exc.message} (at /{path})"], dropped)

    allowed_numbers = list(bundle["allowed_numbers"])
    allowed_values = [float(n["value"]) for n in allowed_numbers]
    allowed_number_ids = {n["id"] for n in bundle["allowed_numbers"]}
    source_ids = {s["source_id"] for s in bundle["sources"]}
    safe_literals = _safe_literals(bundle)

    clean_claims: list[dict[str, Any]] = []
    clean_scenarios: list[dict[str, Any]] = []
    for kind, out in (("claims", clean_claims), ("scenarios", clean_scenarios)):
        for index, item in enumerate(cleaned[kind]):
            reviewed = _review_item(
                item,
                kind=kind,
                index=index,
                allowed_numbers=allowed_numbers,
                safe_literals=safe_literals,
                source_ids=source_ids,
                allowed_number_ids=allowed_number_ids,
                rejections=rejections,
                dropped=dropped,
            )
            if reviewed is not None:
                out.append(reviewed)

    clean_candidates: list[dict[str, Any]] = []
    if allow_candidate_facts:
        for index, fact in enumerate(cleaned["candidate_facts"]):
            reviewed = _review_candidate_fact(
                fact,
                index=index,
                allowed_values=allowed_values,
                safe_literals=safe_literals,
                rejections=rejections,
            )
            if reviewed is not None:
                clean_candidates.append(reviewed)
    elif cleaned["candidate_facts"]:
        dropped.append(
            f"candidate_facts: dropped {len(cleaned['candidate_facts'])} "
            "(candidate-fact ingestion is disabled)"
        )

    # Background lane: a parallel, numberless channel. It NEVER contributes to
    # `rejections`, so a bad background note can never void the grounded output.
    # (raw_background was popped before schema validation, above.)
    clean_background: list[dict[str, Any]] = []
    if allow_background and isinstance(raw_background, list):
        if len(raw_background) > _BG_MAX_NOTES:
            dropped.append(
                f"background: kept first {_BG_MAX_NOTES} of {len(raw_background)} notes"
            )
        for index, note in enumerate(raw_background[:_BG_MAX_NOTES]):
            reviewed = _review_background_note(
                note, index=index, safe_literals=safe_literals, dropped=dropped
            )
            if reviewed is not None:
                clean_background.append(reviewed)
    elif raw_background:
        count = len(raw_background) if isinstance(raw_background, list) else 1
        dropped.append(f"background: dropped {count} (background lane disabled)")

    if rejections:
        return NarrationReview(False, None, rejections, dropped)

    if not clean_claims and not clean_scenarios:
        return NarrationReview(
            False, None, ["no grounded claims or scenarios survived review"], dropped
        )

    narration = {
        "schema_version": NARRATION_SCHEMA_VERSION,
        "claims": clean_claims,
        "scenarios": clean_scenarios,
        "candidate_facts": clean_candidates,
        "background": clean_background,
    }
    return NarrationReview(True, narration, rejections, dropped)
