"""The honesty core: the guardrails every candidate fact must clear.

A candidate becomes a fact only if it (1) meets its template's minimum-sample
floor, (2) cites at least one source, (3) is not stale, and (4) is
number-disciplined — every digit in its prose is one of its declared numbers.
Coincidences are then capped and ranked by specificity, not significance. Each
rejection is recorded in a ``suppressed`` audit trail so the guard is visible.
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

from ._history import Candidate, as_date_iso, as_utc_iso
from .registry import Template

_LABEL_RANK = {"predictive": 0, "context": 1, "coincidence": 2}

# A digit-run token, byte-identical to the AI whitelist's scanner
# (golavo_core.ai.whitelist._NUMBER_RE) so number-discipline here is an exact
# proxy for what the served-narration guard would accept. Numbers on either side
# of an en-dash scoreline ("2–1") are read as two separate tokens; a comma glued
# to a digit ("8,") is captured whole, so templates must never write "verb N,".
_TOKEN_RE = re.compile(r"(?<![\w.])[-+]?(?:\d[\d,]*(?:\.\d+)?|\.\d+)(?:[eE][-+]?\d+)?%?")


def _to_utc(value: Any) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")


def assert_number_discipline(fact: dict[str, Any]) -> None:
    """Fail closed if the fact's text states a digit not in its ``numbers`` list.

    This is what makes a fact safe to fold verbatim into the AI numeric
    whitelist: the digits a reader (or the model) can see are exactly the ones
    the fact vouches for.
    """
    displays = {str(number["display"]) for number in fact["numbers"]}
    for match in _TOKEN_RE.finditer(fact["text"]):
        token = match.group(0)
        if token not in displays:
            raise ValueError(
                f"fact {fact['id']!r} states undisciplined number {token!r}; "
                f"declared displays are {sorted(displays)}"
            )


def build_fact(
    candidate: Candidate, template: Template, source_ids: tuple[str, ...], as_of: pd.Timestamp
) -> tuple[dict[str, Any], bool]:
    """Assemble the full fact dict and compute its freshness. Returns (fact, stale)."""
    last = _to_utc(candidate.last_date)
    as_of_utc = _to_utc(as_of)
    age_days = max(int((as_of_utc - last).days), 0)
    stale = template.staleness_days is not None and age_days > template.staleness_days
    fact = {
        "id": template.id,
        "version": template.version,
        "label": template.label,
        "scope": template.scope,
        "subject": candidate.subject,
        "text": candidate.text,
        "values": candidate.values,
        "numbers": candidate.numbers,
        "sample_n": int(candidate.sample_n),
        "denominator": int(candidate.denominator),
        "base_rate": None if candidate.base_rate is None else round(float(candidate.base_rate), 6),
        "date_range": [as_date_iso(candidate.first_date), as_date_iso(candidate.last_date)],
        "source_ids": list(source_ids),
        "freshness": {
            "as_of_utc": as_utc_iso(as_of_utc),
            "last_event_utc": as_utc_iso(last),
            "age_days": age_days,
            "stale": bool(stale),
            "staleness_days": template.staleness_days,
        },
        "min_sample": int(template.min_sample),
        "specificity": round(float(candidate.specificity), 6),
    }
    return fact, bool(stale)


def _suppress(template: Template, subject: str, reason: str, detail: str) -> dict[str, Any]:
    return {"id": template.id, "subject": subject, "reason": reason, "detail": detail}


def apply_guardrails(
    proposals: list[tuple[Template, Candidate]],
    *,
    source_ids: tuple[str, ...],
    as_of: pd.Timestamp,
    coincidence_cap: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Run every guardrail. Returns (accepted_facts, suppressed_audit), both sorted."""
    accepted: list[dict[str, Any]] = []
    suppressed: list[dict[str, Any]] = []

    for template, candidate in proposals:
        if candidate.sample_n < template.min_sample:
            suppressed.append(
                _suppress(
                    template, candidate.subject, "min_sample",
                    f"sample_n={candidate.sample_n} < min_sample={template.min_sample}",
                )
            )
            continue
        if not source_ids:
            suppressed.append(
                _suppress(template, candidate.subject, "no_source", "no snapshot ids")
            )
            continue
        fact, stale = build_fact(candidate, template, source_ids, as_of)
        if stale:
            suppressed.append(
                _suppress(
                    template, candidate.subject, "stale",
                    f"age_days={fact['freshness']['age_days']} > "
                    f"staleness_days={template.staleness_days}",
                )
            )
            continue
        assert_number_discipline(fact)
        accepted.append(fact)

    # Coincidence cap: keep the most specific few, suppress (and log) the rest.
    coincidences = sorted(
        (f for f in accepted if f["label"] == "coincidence"),
        key=lambda f: (-f["specificity"], f["id"], f["subject"]),
    )
    kept = coincidences[:coincidence_cap]
    for fact in coincidences[coincidence_cap:]:
        suppressed.append(
            {
                "id": fact["id"],
                "subject": fact["subject"],
                "reason": "coincidence_cap",
                "detail": f"specificity={fact['specificity']} below the top {coincidence_cap}",
            }
        )
    kept_ids = {id(fact) for fact in kept}
    final = [f for f in accepted if f["label"] != "coincidence" or id(f) in kept_ids]

    final.sort(key=lambda f: (_LABEL_RANK[f["label"]], -f["specificity"], f["id"], f["subject"]))
    suppressed.sort(key=lambda s: (s["reason"], s["id"], str(s.get("subject", ""))))
    return final, suppressed
