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

from .registry import DATASET_BY_TEMPLATE

_FOLDED_LABELS = ("context", "predictive")

# Human titles for the finer dataset attribution (see below). "results" keeps the
# base pack id (so the council numbers, which fit on results, share it).
_DATASET_TITLES = {
    "goalscorers": "goalscorer records",
    "shootouts": "penalty shootouts",
    "standings": "World Cup standings",
    "awards": "World Cup awards",
}


def _scope_sources(fact: dict[str, Any]) -> tuple[list[str], list[dict[str, Any]]]:
    """Attribute a folded fact to a finer ``<pack>#<dataset>`` source when it was
    derived from the goalscorers/shootouts side tables, so the AI's citation chips
    vary instead of all resolving to one "data pack". A ``results`` fact keeps its
    base pack id. Returns (scoped_source_ids, extra_source_entries)."""
    dataset = DATASET_BY_TEMPLATE.get(str(fact["id"]), "results")
    base_ids = list(fact["source_ids"])
    if dataset == "results" or dataset not in _DATASET_TITLES:
        return base_ids, []
    scoped: list[str] = []
    extras: list[dict[str, Any]] = []
    for sid in base_ids:
        scoped_id = f"{sid}#{dataset}"
        scoped.append(scoped_id)
        # A minimal descriptor; build_match_evidence_bundle finalizes it into a
        # full Source (url/license) so this module stays free of those concerns.
        extras.append(
            {
                "source_id": scoped_id,
                "base_source_id": sid,
                "dataset": dataset,
                "title": f"Vendored data pack · {sid} · {_DATASET_TITLES[dataset]}",
                "license": "CC-BY-SA-4.0" if sid == "fjelstul-worldcup" else "CC0-1.0",
            }
        )
    return scoped, extras


def notebook_to_evidence(
    notebook: dict[str, Any],
    *,
    include_labels: tuple[str, ...] = _FOLDED_LABELS,
    scope_datasets: bool = True,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (evidence_facts, allowed_numbers, extra_sources) for a bundle.

    ``extra_sources`` are the per-dataset source entries a scorer/shootout fact
    cites — pass them to ``build_match_evidence_bundle(extra_sources=...)`` so the
    bundle's ``sources`` list resolves every cited id (varied citation chips).
    ``scope_datasets=False`` keeps the base pack ids (the sealed-forecast path,
    whose sources carry richer snapshot metadata under the base id)."""
    facts: list[dict[str, Any]] = []
    numbers: list[dict[str, Any]] = []
    extra_sources: dict[str, dict[str, Any]] = {}

    for index, fact in enumerate(notebook["facts"]):
        if fact["label"] not in include_labels:
            continue
        if contains_betting_lexicon(fact["text"]):
            continue

        if scope_datasets:
            scoped_source_ids, extras = _scope_sources(fact)
        else:
            scoped_source_ids, extras = list(fact["source_ids"]), []
        for entry in extras:
            extra_sources.setdefault(entry["source_id"], entry)

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
                    "source_ids": scoped_source_ids,
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
                "source_ids": scoped_source_ids,
                "number_refs": number_refs,
            }
        )

    return facts, numbers, list(extra_sources.values())
