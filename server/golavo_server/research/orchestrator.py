"""Plan and run the web-research lane for one match bundle.

Pure orchestration over the fetchers: it plans a few queries from the fixture,
gathers Wikipedia extracts and web-search snippets, sanitizes and caps every
page, and returns a :class:`ResearchResult` the gateway feeds to the model (as
fenced UNTRUSTED data) and the guard checks quotes against. Every fetcher is
injectable so CI/unit tests never open a socket, and every failure is caught and
folded into honest ``notes`` — a fully-failed run yields zero sources and the
read proceeds engine-only.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from golavo_core.ai.sanitize import sanitize_untrusted

from . import wikipedia, websearch
from .fetch import Fetch, research_disabled

# Per-depth budget: how many pages to gather and how much of each the model sees.
_PLAN = {
    "fast": {"fetches": 3, "chars": 1500, "wiki_searches": 1, "web_searches": 1},
    "deep": {"fetches": 8, "chars": 2200, "wiki_searches": 2, "web_searches": 2},
}

Progress = Callable[[str, str, dict[str, Any]], None]


@dataclass(frozen=True)
class ResearchSource:
    source_id: str  # "web_1", "web_2", ...
    provider: str  # "wikipedia" | "websearch"
    title: str
    url: str
    text: str


@dataclass
class ResearchResult:
    sources: list[ResearchSource] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    planned: int = 0

    def corpus(self) -> dict[str, str]:
        """url -> fetched text, for the guard's verbatim-quote check."""
        return {s.url: s.text for s in self.sources}

    def prompt_sources(self) -> list[dict[str, Any]]:
        return [
            {"source_id": s.source_id, "url": s.url, "title": s.title, "text": s.text}
            for s in self.sources
        ]

    def envelope_sources(self) -> list[dict[str, Any]]:
        """kind:"web" source entries for the response (never enter the bundle)."""
        return [
            {"source_id": s.source_id, "kind": "web", "title": s.title, "url": s.url}
            for s in self.sources
        ]


def plan_queries(bundle: dict[str, Any], depth: str) -> list[str]:
    """Heuristic query plan from the fixture — no extra model round-trip."""
    match = bundle.get("match", {})
    home = str(match.get("home_team") or "").strip()
    away = str(match.get("away_team") or "").strip()
    comp = str(match.get("competition") or "").strip()
    queries: list[str] = []
    if home and away:
        queries.append(f"{home} {away} {comp} match".strip())
    if home:
        queries.append(f"{home} national football team")
    if away:
        queries.append(f"{away} national football team")
    if depth == "deep":
        if home and away:
            queries.append(f"{home} vs {away} head to head")
        if comp:
            queries.append(f"{comp}")
    # De-dup, preserve order.
    seen: set[str] = set()
    out: list[str] = []
    for q in queries:
        if q and q not in seen:
            seen.add(q)
            out.append(q)
    return out


def run_research(
    bundle: dict[str, Any],
    depth: str,
    *,
    wiki_search: Callable[..., list[str]] | None = None,
    wiki_extract: Callable[..., dict | None] | None = None,
    web_search: Callable[..., list[dict[str, str]]] | None = None,
    fetch: Fetch | None = None,
    progress: Progress | None = None,
) -> ResearchResult:
    """Gather web research for ``bundle``. Never raises — failures become notes."""
    result = ResearchResult()
    if research_disabled():
        result.notes.append("web research is disabled in this environment")
        return result

    plan = _PLAN.get(depth, _PLAN["fast"])
    chars = plan["chars"]
    _wiki_search = wiki_search or (lambda q, **k: wikipedia.search(q, fetch=fetch, **k))
    _wiki_extract = wiki_extract or (lambda t, **k: wikipedia.extract(t, fetch=fetch, **k))
    _web_search = web_search or (lambda q, **k: websearch.search_snippets(q, fetch=fetch, **k))

    queries = plan_queries(bundle, depth)
    result.planned = plan["fetches"]

    def _emit(stage: str) -> None:
        if progress:
            progress(
                "researching",
                stage,
                {"fetched": len(result.sources), "planned": plan["fetches"]},
            )

    seen_urls: set[str] = set()

    def _add(provider: str, title: str, url: str, text: str) -> bool:
        cleaned = sanitize_untrusted(text or "", max_chars=chars)
        if not cleaned or url in seen_urls or not url.startswith("http"):
            return False
        seen_urls.add(url)
        idx = len(result.sources) + 1
        result.sources.append(
            ResearchSource(f"web_{idx}", provider, title.strip() or url, url, cleaned)
        )
        _emit(f"Reading: {title.strip() or url}")
        return True

    # 1) Wikipedia extracts — the reliable, license-clean backbone.
    wiki_titles: list[str] = []
    for q in queries[: plan["wiki_searches"]]:
        try:
            wiki_titles.extend(_wiki_search(q, limit=2))
        except Exception:
            result.notes.append("a Wikipedia search failed; continued")
    for title in dict.fromkeys(wiki_titles):  # de-dup, keep order
        if len(result.sources) >= plan["fetches"]:
            break
        try:
            page = _wiki_extract(title, max_chars=chars)
        except Exception:
            page = None
        if page:
            _add("wikipedia", page["title"], page["url"], page["text"])

    # 2) Web-search snippets — richer but fragile (see websearch.py).
    web_hits = 0
    for q in queries[: plan["web_searches"]]:
        if len(result.sources) >= plan["fetches"]:
            break
        try:
            hits = _web_search(q, limit=3)
        except Exception:
            hits = []
        if not hits:
            continue
        for hit in hits:
            if len(result.sources) >= plan["fetches"]:
                break
            if _add("websearch", hit.get("title", ""), hit.get("url", ""), hit.get("snippet", "")):
                web_hits += 1
    if web_hits == 0:
        result.notes.append("web search returned nothing usable; used Wikipedia only")

    if not result.sources:
        result.notes.append("no web sources could be fetched; the read is engine-only")
    return result
