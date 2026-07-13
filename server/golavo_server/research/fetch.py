"""The ONE place the research lane touches the network.

Golavo is local-first; this module — like ``fixtures.py`` — is an explicit,
consent-gated exception. Every safety property lives here so the callers
(``wikipedia``/``websearch``) stay simple:

* https only, and the hostname must be on a small allowlist — re-checked after
  any redirect, so a 302 can't bounce us to an arbitrary host;
* a real, contactable User-Agent (Wikipedia etiquette);
* hard byte and time caps;
* one exception type (``ResearchFetchError``) for every failure, so orchestration
  degrades gracefully;
* an injectable ``Fetch`` seam (mirroring ``fixtures.check_new_fixtures``) so CI
  and unit tests never open a socket.

The kill switch ``GOLAVO_NO_RESEARCH=1`` short-circuits every fetch — set in CI.
"""

from __future__ import annotations

import os
import urllib.error
import urllib.request
from collections.abc import Callable
from urllib.parse import urlsplit

from golavo_server import __version__

USER_AGENT = (
    f"Golavo/{__version__} (+https://github.com/udhawan97/Golavo; "
    "local-first football forecaster; contact via repo issues)"
)

# Only these hosts are ever contacted. Wikipedia for reference; DuckDuckGo's
# keyless HTML endpoints for a general web search (see websearch.py for the
# honest caveats).
ALLOWED_HOSTS = frozenset(
    {"en.wikipedia.org", "html.duckduckgo.com", "lite.duckduckgo.com"}
)

# A single, injectable fetch primitive: url -> raw bytes.
Fetch = Callable[[str], bytes]


class ResearchFetchError(Exception):
    """Any failure to fetch a research URL (network, policy, or size)."""


def research_disabled() -> bool:
    """True when the CI/offline kill switch is set."""
    return os.environ.get("GOLAVO_NO_RESEARCH") == "1"


def _check_host(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme != "https":
        raise ResearchFetchError(f"non-https URL refused: {url!r}")
    if parts.hostname not in ALLOWED_HOSTS:
        raise ResearchFetchError(f"host not on the research allowlist: {parts.hostname!r}")


class _StrictRedirect(urllib.request.HTTPRedirectHandler):
    """Re-validate the target host on every redirect (fail closed)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        _check_host(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_StrictRedirect())


def fetch_url(url: str, *, timeout: float = 10.0, max_bytes: int = 1_000_000) -> bytes:
    """Fetch ``url`` with the allowlist, UA, and caps enforced. Raises on failure."""
    if research_disabled():
        raise ResearchFetchError("research is disabled (GOLAVO_NO_RESEARCH=1)")
    _check_host(url)
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/json"},
    )
    try:
        with _OPENER.open(req, timeout=timeout) as resp:
            # Re-check the final URL after any followed redirect.
            _check_host(resp.geturl())
            return resp.read(max_bytes + 1)[:max_bytes]
    except ResearchFetchError:
        raise
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise ResearchFetchError(f"fetch failed: {type(exc).__name__}") from exc


def _resolve(fetch: Fetch | None) -> Fetch:
    """The injected fetch, or the real one — resolved at CALL time so a test
    monkeypatch on this module is honored."""
    return fetch if fetch is not None else fetch_url
