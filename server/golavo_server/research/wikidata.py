"""Wikidata discovery through documented, read-only APIs."""

from __future__ import annotations

import json
from urllib.parse import urlencode

from .fetch import Fetch, ResearchFetchError, _resolve

_ACTION = "https://www.wikidata.org/w/api.php"
_REST = "https://www.wikidata.org/w/rest.php/wikibase/v1/entities/items"


def search(
    query: str,
    *,
    limit: int = 4,
    fetch: Fetch | None = None,
    fail_soft: bool = True,
) -> list[dict[str, str]]:
    params = {
        "action": "wbsearchentities",
        "search": query,
        "language": "en",
        "type": "item",
        "limit": max(1, min(limit, 10)),
        "format": "json",
    }
    try:
        raw = _resolve(fetch)(f"{_ACTION}?{urlencode(params)}")
        payload = json.loads(raw.decode("utf-8"))
    except ResearchFetchError:
        if not fail_soft:
            raise
        return []
    except (UnicodeDecodeError, ValueError):
        return []
    rows = payload.get("search") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return []
    result = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        qid = str(row.get("id") or "")
        label = str(row.get("label") or "").strip()
        if not qid.startswith("Q") or not qid[1:].isdigit() or not label:
            continue
        result.append(
            {
                "provider": "wikidata",
                "title": label,
                "description": str(row.get("description") or ""),
                "url": f"{_REST}/{qid}",
                "source_id": "wikidata",
            }
        )
    return result[:limit]
