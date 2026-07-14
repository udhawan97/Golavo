"""General web search via DuckDuckGo's keyless HTML endpoints.

HONEST CAVEATS (read before relying on this): these endpoints are undocumented,
scraping them sits against DuckDuckGo's bot policy, they intermittently serve an
"anomaly"/challenge page instead of results, and the markup can change without
notice. Therefore EVERY failure path returns ``[]`` and the orchestrator falls
back to Wikipedia-only with a user-visible note. Only the result SNIPPETS are
used as research text — we never fetch arbitrary result pages, which keeps the
parsing surface and the ToS exposure minimal.

The function is provider-shaped so a future keyless provider (e.g. a user's own
SearXNG instance) can slot in without touching callers.
"""

from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import urlencode

from .fetch import Fetch, ResearchFetchError, _resolve

_LITE = "https://lite.duckduckgo.com/lite/"
_HTML = "https://html.duckduckgo.com/html/"
_ANOMALY_MARKERS = ("anomaly", "challenge", "unusual traffic", "are you a robot")


class _LiteParser(HTMLParser):
    """Pull (title, url, snippet) triples from DDG's lite results table.

    The lite layout is a table of rows: an anchor with class ``result-link`` for
    the title/url, then a ``result-snippet`` cell. We accumulate text between the
    markers we recognise and are tolerant of missing pieces.
    """

    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict[str, str]] = []
        self._mode: str | None = None
        self._href: str | None = None
        self._title: list[str] = []
        self._snippet: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        cls = (a.get("class") or "")
        if tag == "a" and "result-link" in cls:
            self._flush()
            self._mode = "title"
            self._href = a.get("href") or ""
        elif tag in ("td", "div") and "result-snippet" in cls:
            self._mode = "snippet"

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._mode == "title":
            self._mode = None
        elif tag in ("td", "div") and self._mode == "snippet":
            self._mode = None

    def handle_data(self, data: str) -> None:
        if self._mode == "title":
            self._title.append(data)
        elif self._mode == "snippet":
            self._snippet.append(data)

    def _flush(self) -> None:
        title = " ".join("".join(self._title).split())
        snippet = " ".join("".join(self._snippet).split())
        href = (self._href or "").strip()
        if title and href.startswith("http"):
            self.results.append({"title": title, "url": href, "snippet": snippet})
        self._href, self._title, self._snippet = None, [], []

    def close(self) -> None:  # noqa: D102
        self._flush()
        super().close()


def _parse(html: str) -> list[dict[str, str]]:
    lowered = html.lower()
    if any(marker in lowered for marker in _ANOMALY_MARKERS):
        return []
    parser = _LiteParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception:  # a malformed page must never crash the read
        return []
    return parser.results


def search_snippets(
    query: str, *, limit: int = 4, fetch: Fetch | None = None
) -> list[dict[str, str]]:
    """Return up to ``limit`` {title, url, snippet}. ``[]`` on ANY failure."""
    getter = _resolve(fetch)
    for endpoint in (_LITE, _HTML):
        url = f"{endpoint}?{urlencode({'q': query})}"
        try:
            raw = getter(url)
        except ResearchFetchError:
            continue
        results = _parse(raw.decode("utf-8", "replace"))
        if results:
            return results[:limit]
    return []
