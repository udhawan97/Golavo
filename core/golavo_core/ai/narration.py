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

NARRATION_SCHEMA_VERSION = "0.1.0"

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

    # Hard rejects: a single one fails the entire narration (fail closed).
    betting = contains_betting_lexicon(text)
    if betting:
        rejections.append(f"{label}: betting lexicon {sorted(set(betting))}")
    bad_numbers = unsupported_number_tokens(
        text, allowed_numbers, item["number_refs"], safe_literals
    )
    if bad_numbers:
        rejections.append(
            f"{label}: {len(bad_numbers)} numeric token(s) did not match exact "
            "displays of referenced numbers"
        )
    if contains_secret_pattern(text):
        rejections.append(f"{label}: credential-shaped content")

    # Soft drops: remove just this claim, keep the rest.
    if _COT_MARKER_RE.search(text):
        dropped.append(f"{label}: dropped (chain-of-thought marker in text)")
        return None
    valid_sources = [sid for sid in item["source_ids"] if sid in source_ids]
    if not valid_sources:
        dropped.append(f"{label}: dropped (no citation resolves to a bundle source)")
        return None
    bad_refs = [ref for ref in item["number_refs"] if ref not in allowed_number_ids]
    if bad_refs:
        dropped.append(f"{label}: dropped (number_refs not in allowed_numbers: {bad_refs})")
        return None

    number_by_id = {str(number["id"]): number for number in allowed_numbers}
    uncited_refs = [
        ref
        for ref in item["number_refs"]
        if not set(number_by_id[ref]["source_ids"]).intersection(valid_sources)
    ]
    if uncited_refs:
        dropped.append(
            f"{label}: dropped (number_refs lack one of their trusted sources: {uncited_refs})"
        )
        return None

    # Extra refs are also misleading: the UI renders them as trusted number
    # chips. Require every referenced display to appear in this claim's text.
    missing_displays = [
        str(number["display"])
        for number in allowed_numbers
        if number["id"] in item["number_refs"] and str(number["display"]) not in text
    ]
    if missing_displays:
        dropped.append(
            f"{label}: dropped (number_refs not present in text: {missing_displays})"
        )
        return None

    return {"text": text, "source_ids": valid_sources, "number_refs": list(item["number_refs"])}


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


def review_narration(
    raw: Any,
    bundle: dict[str, Any],
    *,
    allow_candidate_facts: bool = False,
) -> NarrationReview:
    """Review a raw model output against ``bundle``; see module docstring."""
    from jsonschema import Draft202012Validator, ValidationError

    rejections: list[str] = []
    dropped: list[str] = []

    if not isinstance(raw, dict):
        return NarrationReview(False, None, ["output is not a JSON object"], dropped)

    cleaned = _strip_cot(copy.deepcopy(raw))
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
    }
    return NarrationReview(True, narration, rejections, dropped)
