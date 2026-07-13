"""Web-research lane: fetchers (canned bytes, no sockets), orchestrator budgets,
and the fail-soft/consent guarantees. Zero network by construction."""

from __future__ import annotations

import json

import pytest

from golavo_server.research import fetch as fetchmod
from golavo_server.research import websearch, wikipedia
from golavo_server.research.fetch import ResearchFetchError
from golavo_server.research.orchestrator import plan_queries, run_research


# ---- fetch policy ----------------------------------------------------------


def test_non_https_is_refused() -> None:
    with pytest.raises(ResearchFetchError):
        fetchmod.fetch_url("http://en.wikipedia.org/x")


def test_off_allowlist_host_is_refused() -> None:
    with pytest.raises(ResearchFetchError):
        fetchmod.fetch_url("https://evil.example/x")


def test_kill_switch_short_circuits(monkeypatch) -> None:
    monkeypatch.setenv("GOLAVO_NO_RESEARCH", "1")
    assert fetchmod.research_disabled() is True
    with pytest.raises(ResearchFetchError):
        fetchmod.fetch_url("https://en.wikipedia.org/x")


# ---- wikipedia (injected fetch) --------------------------------------------


def test_wikipedia_search_and_extract_parse_canned_json() -> None:
    def fake_fetch(url: str) -> bytes:
        if "list=search" in url:
            return json.dumps({"query": {"search": [{"title": "Spain national football team"}]}}).encode()
        return json.dumps(
            {"query": {"pages": {"1": {"title": "Spain national football team", "extract": "Spain are a national team."}}}}
        ).encode()

    titles = wikipedia.search("spain", fetch=fake_fetch)
    assert titles == ["Spain national football team"]
    page = wikipedia.extract("Spain national football team", fetch=fake_fetch)
    assert page and page["url"].startswith("https://en.wikipedia.org/wiki/")
    assert "national team" in page["text"]


def test_wikipedia_fails_soft_on_bad_json() -> None:
    assert wikipedia.search("x", fetch=lambda url: b"not json") == []
    assert wikipedia.extract("x", fetch=lambda url: b"not json") is None


# ---- websearch (injected fetch) --------------------------------------------

_LITE_HTML = """
<html><body><table>
<tr><td><a class="result-link" href="https://example.org/a">Spain beat France</a></td></tr>
<tr><td class="result-snippet">Spain won the match 2-1 in the final.</td></tr>
</table></body></html>
"""


def test_websearch_parses_snippets() -> None:
    hits = websearch.search_snippets("spain france", fetch=lambda url: _LITE_HTML.encode())
    assert len(hits) == 1
    assert hits[0]["url"] == "https://example.org/a"
    assert "final" in hits[0]["snippet"]


def test_websearch_anomaly_page_yields_nothing() -> None:
    page = b"<html><body>Unusual traffic detected, are you a robot?</body></html>"
    assert websearch.search_snippets("x", fetch=lambda url: page) == []


def test_websearch_fetch_failure_yields_nothing() -> None:
    def boom(url: str) -> bytes:
        raise ResearchFetchError("down")

    assert websearch.search_snippets("x", fetch=boom) == []


# ---- orchestrator ----------------------------------------------------------

_BUNDLE = {"match": {"home_team": "Spain", "away_team": "France", "competition": "FIFA World Cup"}}


def test_plan_queries_dedupes_and_grows_with_depth() -> None:
    fast = plan_queries(_BUNDLE, "fast")
    deep = plan_queries(_BUNDLE, "deep")
    assert len(deep) > len(fast)
    assert len(set(fast)) == len(fast)


def test_run_research_gathers_and_caps(monkeypatch) -> None:
    # These exercise the injected-fetcher path (no sockets), so clear the CI
    # env kill switch that would otherwise short-circuit to empty.
    monkeypatch.delenv("GOLAVO_NO_RESEARCH", raising=False)

    def wiki_search(q, **k):
        return ["Spain national football team", "France national football team"]

    def wiki_extract(t, **k):
        return {"title": t, "url": f"https://en.wikipedia.org/wiki/{t.replace(' ', '_')}",
                "text": "Some long factual text about the team. " * 5}

    def web_search(q, **k):
        return [{"title": "News", "url": "https://example.org/news", "snippet": "A recent report."}]

    stages: list[str] = []
    result = run_research(
        _BUNDLE, "fast",
        wiki_search=wiki_search, wiki_extract=wiki_extract, web_search=web_search,
        progress=lambda stage, detail, counts: stages.append(detail),
    )
    assert 0 < len(result.sources) <= 3  # fast budget
    # Every source has a unique web_N id and appears in the corpus.
    ids = [s.source_id for s in result.sources]
    assert ids == [f"web_{i + 1}" for i in range(len(ids))]
    assert set(result.corpus().keys()) == {s.url for s in result.sources}
    assert stages  # progress fired


def test_run_research_partial_failure_notes_and_survives(monkeypatch) -> None:
    monkeypatch.delenv("GOLAVO_NO_RESEARCH", raising=False)

    def wiki_search(q, **k):
        return ["Spain"]

    def wiki_extract(t, **k):
        return {"title": "Spain", "url": "https://en.wikipedia.org/wiki/Spain", "text": "Spain text."}

    def web_search(q, **k):
        raise RuntimeError("ddg down")

    result = run_research(
        _BUNDLE, "fast",
        wiki_search=wiki_search, wiki_extract=wiki_extract, web_search=web_search,
    )
    assert any(s.provider == "wikipedia" for s in result.sources)
    assert any("web search" in n.lower() for n in result.notes)


def test_run_research_disabled_returns_empty(monkeypatch) -> None:
    monkeypatch.setenv("GOLAVO_NO_RESEARCH", "1")
    result = run_research(_BUNDLE, "deep")
    assert result.sources == []
    assert result.notes
