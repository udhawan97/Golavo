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


def _get_json(url: str, fetch: Fetch | None) -> Any | None:
    try:
        raw = _resolve(fetch)(url)
    except ResearchFetchError:
        return None
    try:
        return json.loads(raw.decode("utf-8", "replace"))
    except (ValueError, UnicodeDecodeError):
        return None


def search(query: str, *, limit: int = 3, fetch: Fetch | None = None) -> list[str]:
    """Return up to ``limit`` article titles matching ``query`` (best-effort)."""
    params = {
        "action": "query", "list": "search", "format": "json",
        "srsearch": query, "srlimit": max(1, min(limit, 10)), "srprop": "",
    }
    data = _get_json(f"{_API}?{urlencode(params)}", fetch)
    try:
        hits = data["query"]["search"]  # type: ignore[index]
    except (TypeError, KeyError):
        return []
    return [str(h["title"]) for h in hits if isinstance(h, dict) and h.get("title")]


def extract(title: str, *, max_chars: int = 2500, fetch: Fetch | None = None) -> dict | None:
    """Return ``{title, url, text}`` for an article, or None. Plain-text extract."""
    params = {
        "action": "query", "prop": "extracts", "explaintext": "1",
        "redirects": "1", "format": "json", "titles": title,
    }
    data = _get_json(f"{_API}?{urlencode(params)}", fetch)
    try:
        pages = data["query"]["pages"]  # type: ignore[index]
    except (TypeError, KeyError):
        return None
    for page in pages.values() if isinstance(pages, dict) else []:
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
