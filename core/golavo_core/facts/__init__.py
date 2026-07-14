"""Deterministic, source-backed fact and coincidence templates.

Pre-registered templates only (no free-text mining). Each fact carries its
sample, denominator, source ids, and a predictive/context/coincidence label.
Coincidences never touch the model.

Public API:
  * ``build_notebook`` / ``notebook_for_artifact`` — compute a notebook
  * ``validate_notebook`` — schema + guardrail validation
  * ``notebook_to_evidence`` — fold context/predictive facts into an AI bundle
  * ``REGISTRY`` / ``REGISTRY_VERSION`` / ``family_size`` — the template family
  * ``assert_facts_isolated`` / ``verify_notebook_pipeline_pure`` — the
    machine-checked no-write invariant
"""

from __future__ import annotations

from .engine import (
    GENERATOR,
    NOTEBOOK_SCHEMA_VERSION,
    build_notebook,
    notebook_for_artifact,
    validate_notebook,
)
from .evidence import notebook_to_evidence
from .invariant import (
    assert_facts_isolated,
    assert_no_number_written,
    verify_notebook_pipeline_pure,
)
from .packs import load_side_tables
from .registry import COINCIDENCE_CAP, REGISTRY, REGISTRY_VERSION, Template, family_size
from .wc_history import WorldCupHistory, load_wc_history

__all__ = [
    "COINCIDENCE_CAP",
    "GENERATOR",
    "NOTEBOOK_SCHEMA_VERSION",
    "REGISTRY",
    "REGISTRY_VERSION",
    "Template",
    "WorldCupHistory",
    "assert_facts_isolated",
    "assert_no_number_written",
    "build_notebook",
    "family_size",
    "load_side_tables",
    "load_wc_history",
    "notebook_for_artifact",
    "notebook_to_evidence",
    "validate_notebook",
    "verify_notebook_pipeline_pure",
]
