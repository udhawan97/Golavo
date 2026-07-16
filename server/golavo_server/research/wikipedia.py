"""Wikipedia lookups via the public MediaWiki API (keyless, documented, stable).

Two calls: ``search`` (titles for a query) and ``extract`` (plain-text intro +
body for a title). Both fail SOFT — any error returns ``[]``/``None`` so the
orchestrator degrades to fewer sources rather than failing the whole read. Only
``en.wikipedia.org`` is used; the fetch layer enforces the allowlist and UA.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote, urlencode

from .fetch import Fetch, ResearchFetchError, _resolve

_API = "https://en.wikipedia.org/w/api.php"


def _get_json(url: str, fetch: Fetch | None, *, fail_soft: bool = True) -> Any | None:
    try:
        raw = _resolve(fetch)(url)
    except ResearchFetchError:
        if not fail_soft:
            raise
        return None
    try:
        return json.loads(raw.decode("utf-8", "replace"))
    except (ValueError, UnicodeDecodeError):
        return None


def search(
    query: str,
    *,
    limit: int = 3,
    fetch: Fetch | None = None,
    fail_soft: bool = True,
) -> list[str]:
    """Return up to ``limit`` article titles matching ``query`` (best-effort)."""
    params = {
        "action": "query",
        "list": "search",
        "format": "json",
        "srsearch": query,
        "srlimit": max(1, min(limit, 10)),
        "srprop": "",
    }
    data = _get_json(f"{_API}?{urlencode(params)}", fetch, fail_soft=fail_soft)
    try:
        hits = data["query"]["search"]  # type: ignore[index]
    except (TypeError, KeyError):
        return []
    return [str(h["title"]) for h in hits if isinstance(h, dict) and h.get("title")]


def discovery(
    query: str,
    *,
    limit: int = 3,
    fetch: Fetch | None = None,
    fail_soft: bool = True,
) -> list[dict[str, str]]:
    """Documented API discovery. Returned URLs fetch page text, not search snippets."""
    return [
        {
            "provider": "wikipedia",
            "title": title,
            "url": extract_url(title),
            "source_id": "wikipedia-en",
        }
        for title in search(query, limit=limit, fetch=fetch, fail_soft=fail_soft)
    ]


def extract_url(title: str) -> str:
    params = {
        "action": "query",
        "prop": "extracts|info|revisions",
        "explaintext": "1",
        "inprop": "url",
        "rvprop": "ids|timestamp",
        "redirects": "1",
        "format": "json",
        "formatversion": "2",
        "titles": title,
    }
    return f"{_API}?{urlencode(params)}"


def extract(title: str, *, max_chars: int = 2500, fetch: Fetch | None = None) -> dict | None:
    """Return ``{title, url, text}`` for an article, or None. Plain-text extract."""
    data = _get_json(extract_url(title), fetch)
    try:
        pages = data["query"]["pages"]  # type: ignore[index]
    except (TypeError, KeyError):
        return None
    values = pages.values() if isinstance(pages, dict) else pages if isinstance(pages, list) else []
    for page in values:
        text = str(page.get("extract") or "").strip()
        if not text:
            continue
        real_title = str(page.get("title") or title)
        return {
            "title": real_title,
            "url": f"https://en.wikipedia.org/wiki/{quote(real_title.replace(' ', '_'))}",
            "text": text[:max_chars],
        }
    return None
