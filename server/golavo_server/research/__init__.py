"""Consent-gated, evidence-bound foreground match research."""

from __future__ import annotations

from .fetch import ResearchFetchError, research_disabled
from .orchestrator import (
    ResearchResult,
    ResearchSource,
    discover,
    execute_run,
    plan_queries,
    run_capture,
    run_research,
)

__all__ = [
    "ResearchFetchError",
    "ResearchResult",
    "ResearchSource",
    "discover",
    "execute_run",
    "plan_queries",
    "research_disabled",
    "run_capture",
    "run_research",
]
