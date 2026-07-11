"""Adapt a Commentator's Notebook into AI evidence-bundle facts + numbers.

Only context and predictive facts are folded — coincidences are quarantined and
never shown to the model. Each folded fact keeps its number-disciplined text, and
every number it states becomes a namespaced (``nb_*``) entry in the bundle's
``allowed_numbers`` whitelist. The existing numeric guard is therefore unchanged:
the model may cite these facts, but can no more invent a notebook number than an
engine one. Betting-lexicon text is dropped defensively so it never reaches the
prompt.
"""

from __future__ import annotations

from typing import Any

from golavo_core.ai.whitelist import contains_betting_lexicon

_FOLDED_LABELS = ("context", "predictive")


def notebook_to_evidence(
    notebook: dict[str, Any], *, include_labels: tuple[str, ...] = _FOLDED_LABELS
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (evidence_facts, allowed_numbers) to append to an evidence bundle."""
    facts: list[dict[str, Any]] = []
    numbers: list[dict[str, Any]] = []

    for index, fact in enumerate(notebook["facts"]):
        if fact["label"] not in include_labels:
            continue
        if contains_betting_lexicon(fact["text"]):
            continue

        number_refs: list[str] = []
        for number in fact["numbers"]:
            number_id = f"nb_{fact['id']}_{index}_{number['key']}"
            numbers.append(
                {
                    "id": number_id,
                    "value": number["value"],
                    "unit": number["unit"],
                    "label": f"{fact['subject']} · {fact['id']} · {number['key']}",
                    "display": number["display"],
                    "source_ids": list(fact["source_ids"]),
                }
            )
            number_refs.append(number_id)

        facts.append(
            {
                # Folded as `context`: it is grounded background the model may
                # cite. The predictive/context distinction is preserved in the
                # notebook itself; coincidences are never here.
                "fact_id": f"nb_{fact['id']}_{index}",
                "text": fact["text"],
                "kind": "context",
                "source_ids": list(fact["source_ids"]),
                "number_refs": number_refs,
            }
        )

    return facts, numbers
