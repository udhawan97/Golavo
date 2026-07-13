"""Consent-gated web-research lane for the optional AI read.

Local-first exception, like ``fixtures``: only runs when the request carries
``allow_research: true`` (the Settings toggle gates whether the UI ever sends it)
and never in CI (``GOLAVO_NO_RESEARCH=1``). Fetched text is fed to the model
strictly as UNTRUSTED data; the narration guard checks every research quote
against the actually-fetched page.
"""

from __future__ import annotations

from .fetch import ResearchFetchError, research_disabled
from .orchestrator import ResearchResult, ResearchSource, plan_queries, run_research

__all__ = [
    "ResearchFetchError",
    "ResearchResult",
    "ResearchSource",
    "plan_queries",
    "research_disabled",
    "run_research",
]
