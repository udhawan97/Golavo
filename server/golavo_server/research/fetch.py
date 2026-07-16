"""Pinned-IP, registry-bound fetch primitive for explicit match research."""

from __future__ import annotations

import http.client
import ipaddress
import os
import socket
import ssl
import time
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

from golavo_server import __version__

from .policy import ResearchPolicyError, SourcePolicy, canonicalize_url, redirect_allowed

USER_AGENT = (
    f"Golavo/{__version__} (+https://github.com/udhawan97/Golavo; "
    "foreground evidence research; contact via repo issues)"
)
MAX_REDIRECTS = 2
CHUNK_BYTES = 16_384


class ResearchFetchError(Exception):
    def __init__(self, reason_code: str, detail: str, *, retry_after: str | None = None) -> None:
        super().__init__(detail)
        self.reason_code = reason_code
        self.detail = detail
        self.retry_after = retry_after


@dataclass(frozen=True)
class FetchResponse:
    canonical_url: str
    source_id: str
    status: int
    content_type: str
    body: bytes
    etag: str | None
    last_modified: str | None


Fetch = Callable[[str], bytes]
Cancel = Callable[[], bool]


def research_disabled() -> bool:
    return os.environ.get("GOLAVO_NO_RESEARCH") == "1"


def _cancelled(cancel: Cancel | None) -> bool:
    return bool(cancel and cancel())


def _public_addresses(host: str, port: int) -> list[str]:
    try:
        rows = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ResearchFetchError("dns_failed", "research host could not be resolved") from exc
    addresses: list[str] = []
    for row in rows:
        raw = str(row[4][0]).split("%", 1)[0]
        try:
            address = ipaddress.ip_address(raw)
        except ValueError as exc:
            raise ResearchFetchError("dns_invalid", "research host resolved unexpectedly") from exc
        if not address.is_global:
            raise ResearchFetchError(
                "unsafe_address", "research hosts must resolve only to public IPs"
            )
        if raw not in addresses:
            addresses.append(raw)
    if not addresses:
        raise ResearchFetchError("dns_empty", "research host resolved to no usable address")
    return addresses


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, address: str, port: int, timeout: float) -> None:
        super().__init__(host, port=port, timeout=timeout, context=ssl.create_default_context())
        self._address = address

    def connect(self) -> None:
        raw = socket.create_connection((self._address, self.port), self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except Exception:
            raw.close()
            raise


def _one_request(
    url: str,
    policy: SourcePolicy,
    *,
    deadline: float,
    cancel: Cancel | None,
) -> tuple[int, dict[str, str], bytes]:
    if _cancelled(cancel):
        raise ResearchFetchError("cancelled", "research was cancelled")
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    port = parsed.port or 443
    addresses = _public_addresses(host, port)
    last_error: Exception | None = None
    for address in addresses:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ResearchFetchError("timeout", "research request exceeded its total deadline")
        connection = _PinnedHTTPSConnection(host, address, port, remaining)
        try:
            path = parsed.path or "/"
            if parsed.query:
                path += "?" + parsed.query
            connection.request(
                "GET",
                path,
                headers={
                    "Host": host,
                    "User-Agent": USER_AGENT,
                    "Accept": ", ".join(policy.content_types),
                    "Accept-Encoding": "identity",
                    "Connection": "close",
                },
            )
            response = connection.getresponse()
            headers = {key.casefold(): value for key, value in response.getheaders()}
            if headers.get("content-encoding", "identity").casefold() not in {"", "identity"}:
                raise ResearchFetchError(
                    "encoded_response_refused", "compressed research responses are refused"
                )
            declared = headers.get("content-length")
            if declared:
                try:
                    if int(declared) > policy.max_raw_bytes:
                        raise ResearchFetchError(
                            "response_too_large", "research response exceeds its source cap"
                        )
                except ValueError as exc:
                    raise ResearchFetchError(
                        "invalid_content_length", "invalid research response length"
                    ) from exc
            body = bytearray()
            while True:
                if time.monotonic() >= deadline:
                    raise ResearchFetchError(
                        "timeout", "research request exceeded its total deadline"
                    )
                if _cancelled(cancel):
                    raise ResearchFetchError("cancelled", "research was cancelled")
                chunk = response.read(CHUNK_BYTES)
                if not chunk:
                    break
                body.extend(chunk)
                if len(body) > policy.max_raw_bytes:
                    raise ResearchFetchError(
                        "response_too_large", "research response exceeds its source cap"
                    )
            return response.status, headers, bytes(body)
        except ResearchFetchError:
            raise
        except (OSError, ssl.SSLError, http.client.HTTPException) as exc:
            last_error = exc
        finally:
            connection.close()
    raise ResearchFetchError(
        "network_failed", "research source could not be reached"
    ) from last_error


def fetch_response(
    url: str,
    *,
    source_id: str | None = None,
    timeout: float = 7.0,
    cancel: Cancel | None = None,
) -> FetchResponse:
    if research_disabled():
        raise ResearchFetchError("research_disabled", "research is disabled in this environment")
    try:
        current, policy = canonicalize_url(url, source_id=source_id)
    except ResearchPolicyError as exc:
        raise ResearchFetchError(exc.reason_code, exc.detail) from exc
    deadline = time.monotonic() + timeout
    for redirect_count in range(MAX_REDIRECTS + 1):
        status, headers, body = _one_request(current, policy, deadline=deadline, cancel=cancel)
        if status in {301, 302, 303, 307, 308}:
            location = headers.get("location")
            target = urljoin(current, location or "")
            if (
                redirect_count >= MAX_REDIRECTS
                or not location
                or not redirect_allowed(policy, target)
            ):
                raise ResearchFetchError(
                    "redirect_refused", "research redirect left the approved endpoint"
                )
            current, policy = canonicalize_url(target, source_id=policy.source_id)
            continue
        if status in {429, 503}:
            raise ResearchFetchError(
                "source_busy",
                "research source asked Golavo to slow down",
                retry_after=headers.get("retry-after"),
            )
        if status != 200:
            raise ResearchFetchError("http_error", f"research source returned HTTP {status}")
        content_type = headers.get("content-type", "").split(";", 1)[0].strip().casefold()
        if content_type not in policy.content_types:
            raise ResearchFetchError(
                "content_type_refused", "research source returned an unapproved content type"
            )
        if not body:
            raise ResearchFetchError("empty_response", "research source returned no content")
        return FetchResponse(
            canonical_url=current,
            source_id=policy.source_id,
            status=status,
            content_type=content_type,
            body=body,
            etag=headers.get("etag"),
            last_modified=headers.get("last-modified"),
        )
    raise ResearchFetchError("redirect_refused", "too many research redirects")


def fetch_url(url: str, *, timeout: float = 7.0, max_bytes: int | None = None) -> bytes:
    """Compatibility seam for documented source adapters and network-free tests."""
    response = fetch_response(url, timeout=timeout)
    if max_bytes is not None and len(response.body) > max_bytes:
        raise ResearchFetchError("response_too_large", "research response exceeds caller cap")
    return response.body


def _resolve(fetch: Fetch | None) -> Fetch:
    return fetch if fetch is not None else fetch_url
