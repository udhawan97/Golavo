"""Approved-source revision checks and bounded pinned downloads.

This is the only runtime module allowed to reach the public data sources.  It
accepts no caller-provided URLs: repository, branch and path allowlists are
compiled here and mirrored in ``data/sources/registry.json`` for disclosure.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Event
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

MARTJ42 = "martj42-international-results"
WORLDCUP = "openfootball-worldcup-json"
FOOTBALL = "openfootball-football-json"
APPROVED_SOURCE_IDS = (MARTJ42, WORLDCUP, FOOTBALL)
LEAGUE_CODES = ("en.1", "es.1", "de.1", "it.1", "fr.1")

_CONFIG: dict[str, dict[str, Any]] = {
    MARTJ42: {
        "repo": "martj42/international_results",
        "branch": "master",
        "interval_seconds": 6 * 60 * 60,
        "files": ("results.csv", "goalscorers.csv", "shootouts.csv", "former_names.csv", "LICENSE"),
    },
    WORLDCUP: {
        "repo": "openfootball/worldcup.json",
        "branch": "master",
        "interval_seconds": 6 * 60 * 60,
        "files": ("2026/worldcup.json", "2026/worldcup.stadiums.json", "LICENSE.md"),
    },
    FOOTBALL: {
        "repo": "openfootball/football.json",
        "branch": "master",
        "interval_seconds": 24 * 60 * 60,
    },
}

_ALLOWED_HOSTS = frozenset({"api.github.com", "raw.githubusercontent.com"})
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_MAX_METADATA_BYTES = 4 * 1024 * 1024
_MAX_FILE_BYTES = 32 * 1024 * 1024
_TOTAL_TIMEOUT_SECONDS = 120.0


def utc_z(value: datetime | None = None) -> str:
    return (
        (value or datetime.now(UTC))
        .astimezone(UTC)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def current_european_season(value: datetime | None = None) -> str:
    now = (value or datetime.now(UTC)).astimezone(UTC)
    start = now.year if now.month >= 7 else now.year - 1
    return f"{start}-{str(start + 1)[-2:]}"


class RefreshSourceError(Exception):
    def __init__(self, code: str, message: str, *, retryable: bool = True) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class RefreshCancelled(RefreshSourceError):
    def __init__(self) -> None:
        super().__init__("cancelled", "refresh cancelled", retryable=False)


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: dict[str, str]
    body: bytes
    final_url: str


class Fetcher:
    """Small injectable HTTPS client with redirect, size and timeout gates."""

    def get(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        max_bytes: int = _MAX_METADATA_BYTES,
        cancel: Event | None = None,
    ) -> HttpResponse:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in _ALLOWED_HOSTS:
            raise RefreshSourceError(
                "unsafe_redirect", f"unapproved refresh URL: {url}", retryable=False
            )
        request_headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "Golavo-approved-source-refresh/1",
            **(headers or {}),
        }
        request = Request(url, headers=request_headers)
        started = time.monotonic()
        try:
            try:
                response = urlopen(request, timeout=30)  # noqa: S310 - strict allowlist above
            except HTTPError as exc:
                if exc.code == 304:
                    return HttpResponse(
                        status=304,
                        headers={k.lower(): v for k, v in exc.headers.items()},
                        body=b"",
                        final_url=url,
                    )
                body = exc.read(min(max_bytes, 16 * 1024))
                if exc.code in (403, 429):
                    raise RefreshSourceError(
                        "rate_limited", f"upstream returned HTTP {exc.code}", retryable=True
                    ) from exc
                raise RefreshSourceError(
                    "upstream_http", f"upstream returned HTTP {exc.code}: {body[:160]!r}"
                ) from exc
            with response:
                final_url = response.geturl()
                final = urlparse(final_url)
                if final.scheme != "https" or final.hostname not in _ALLOWED_HOSTS:
                    raise RefreshSourceError(
                        "unsafe_redirect",
                        f"upstream redirected to unapproved URL: {final_url}",
                        retryable=False,
                    )
                declared = response.headers.get("Content-Length")
                if declared is not None and int(declared) > max_bytes:
                    raise RefreshSourceError(
                        "download_too_large", f"response exceeds {max_bytes} bytes", retryable=False
                    )
                chunks: list[bytes] = []
                total = 0
                while True:
                    if cancel is not None and cancel.is_set():
                        raise RefreshCancelled()
                    if time.monotonic() - started > _TOTAL_TIMEOUT_SECONDS:
                        raise RefreshSourceError("timeout", "source download exceeded 120 seconds")
                    chunk = response.read(64 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_bytes:
                        raise RefreshSourceError(
                            "download_too_large",
                            f"response exceeds {max_bytes} bytes",
                            retryable=False,
                        )
                    chunks.append(chunk)
                return HttpResponse(
                    status=int(response.status),
                    headers={k.lower(): v for k, v in response.headers.items()},
                    body=b"".join(chunks),
                    final_url=final_url,
                )
        except RefreshSourceError:
            raise
        except (TimeoutError, URLError, OSError, ValueError) as exc:
            code = "timeout" if isinstance(exc, TimeoutError) else "offline"
            raise RefreshSourceError(code, f"could not reach approved source: {exc}") from exc


@dataclass(frozen=True)
class SourceObservation:
    source_id: str
    ref: str
    committed_at_utc: str
    etag: str | None
    checked_at_utc: str
    changed: bool
    capability: str
    season: str | None = None
    current_paths: tuple[str, ...] = ()

    def as_state(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "observed_ref": self.ref,
            "upstream_committed_at_utc": self.committed_at_utc,
            "etag": self.etag,
            "last_checked_at_utc": self.checked_at_utc,
            "last_changed_at_utc": self.checked_at_utc if self.changed else None,
            "capability": self.capability,
            "season": self.season,
            "current_paths": list(self.current_paths),
            "health": "current" if self.changed else "unchanged",
            "error": None,
        }


def source_interval_seconds(source_id: str) -> int:
    return int(_CONFIG[source_id]["interval_seconds"])


def _parse_commit(source_id: str, response: HttpResponse) -> tuple[str, str]:
    try:
        payload = json.loads(response.body)
        ref = str(payload["sha"])
        committed = str(payload["commit"]["committer"]["date"])
    except (KeyError, TypeError, ValueError, UnicodeDecodeError) as exc:
        raise RefreshSourceError(
            "invalid_schema", f"{source_id}: unexpected commit response", retryable=False
        ) from exc
    if _SHA_RE.fullmatch(ref) is None:
        raise RefreshSourceError(
            "invalid_schema", f"{source_id}: invalid commit SHA", retryable=False
        )
    return ref, committed


def _football_paths(tree_body: bytes, season: str) -> tuple[str, ...]:
    try:
        tree = json.loads(tree_body)
        if tree.get("truncated") is True:
            raise ValueError("truncated tree")
        paths = {str(entry["path"]) for entry in tree["tree"] if entry.get("type") == "blob"}
    except (KeyError, TypeError, ValueError, UnicodeDecodeError) as exc:
        raise RefreshSourceError(
            "invalid_schema", "football.json returned an invalid or truncated tree", retryable=False
        ) from exc
    return tuple(
        f"{season}/{code}.json" for code in LEAGUE_CODES if f"{season}/{code}.json" in paths
    )


def check_source(
    source_id: str,
    previous: dict[str, Any] | None = None,
    *,
    fetcher: Fetcher | None = None,
    now: datetime | None = None,
    cancel: Event | None = None,
) -> SourceObservation:
    if source_id not in _CONFIG:
        raise RefreshSourceError("source_not_approved", source_id, retryable=False)
    cfg = _CONFIG[source_id]
    previous = previous or {}
    checked = utc_z(now)
    headers: dict[str, str] = {}
    if previous.get("etag"):
        headers["If-None-Match"] = str(previous["etag"])
    client = fetcher or Fetcher()
    commit_url = f"https://api.github.com/repos/{cfg['repo']}/commits/{cfg['branch']}"
    response = client.get(commit_url, headers=headers, cancel=cancel)
    season = current_european_season(now) if source_id == FOOTBALL else None
    previous_ref = str(previous.get("observed_ref") or previous.get("active_ref") or "")
    if response.status == 304:
        if _SHA_RE.fullmatch(previous_ref) is None:
            raise RefreshSourceError(
                "invalid_state", f"{source_id}: 304 without a saved ref", retryable=False
            )
        ref = previous_ref
        committed = str(previous.get("upstream_committed_at_utc") or "")
        changed = False
        etag = str(previous.get("etag")) if previous.get("etag") else None
    elif response.status == 200:
        ref, committed = _parse_commit(source_id, response)
        changed = ref != previous_ref
        etag = response.headers.get("etag")
    else:
        raise RefreshSourceError("upstream_http", f"{source_id}: HTTP {response.status}")

    current_paths: tuple[str, ...] = ()
    capability = "available"
    if source_id == FOOTBALL:
        previous_season = previous.get("season")
        if response.status != 304 or previous_season != season:
            tree_url = f"https://api.github.com/repos/{cfg['repo']}/git/trees/{ref}?recursive=1"
            tree = client.get(tree_url, cancel=cancel, max_bytes=_MAX_METADATA_BYTES)
            if tree.status != 200:
                raise RefreshSourceError("upstream_http", f"football tree HTTP {tree.status}")
            current_paths = _football_paths(tree.body, str(season))
        else:
            current_paths = tuple(str(path) for path in previous.get("current_paths", []))
        capability = "partial" if current_paths else "absent"

    return SourceObservation(
        source_id=source_id,
        ref=ref,
        committed_at_utc=committed,
        etag=etag,
        checked_at_utc=checked,
        changed=changed,
        capability=capability,
        season=season,
        current_paths=current_paths,
    )


def _raw_url(source_id: str, ref: str, path: str) -> str:
    repo = str(_CONFIG[source_id]["repo"])
    return f"https://raw.githubusercontent.com/{repo}/{ref}/{path}"


def source_paths(observation: SourceObservation) -> tuple[str, ...]:
    if observation.source_id == FOOTBALL:
        return (*observation.current_paths, "LICENSE.md") if observation.current_paths else ()
    return tuple(str(path) for path in _CONFIG[observation.source_id]["files"])


def download_source_snapshot(
    observation: SourceObservation,
    raw_root: Path,
    *,
    fetcher: Fetcher | None = None,
    cancel: Event | None = None,
) -> dict[str, Any]:
    """Capture one pinned source snapshot without leaving partial files behind."""
    if _SHA_RE.fullmatch(observation.ref) is None:
        raise RefreshSourceError(
            "invalid_schema", "download requires a full commit SHA", retryable=False
        )
    client = fetcher or Fetcher()
    root = Path(raw_root) / observation.source_id / observation.ref
    root.mkdir(parents=True, exist_ok=False)
    receipts: list[dict[str, Any]] = []
    total = 0

    def store(relative: str, url: str, response: HttpResponse) -> None:
        nonlocal total
        total += len(response.body)
        if total > 64 * 1024 * 1024:
            raise RefreshSourceError(
                "download_too_large", "source snapshot exceeds 64 MiB", retryable=False
            )
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        part = target.with_name(target.name + ".part")
        with part.open("xb") as handle:
            handle.write(response.body)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(part, target)
        receipts.append(
            {
                "path": relative,
                "pinned_url": url,
                "sha256": hashlib.sha256(response.body).hexdigest(),
                "bytes": len(response.body),
                "content_type": response.headers.get("content-type"),
            }
        )

    # A pinned tree is the immutable evidence behind an honest club capability,
    # including the important "current season absent" state where there are no
    # data files to download. Re-checking the tree at the immutable commit also
    # closes the gap between the earlier revision check and snapshot capture.
    if observation.source_id == FOOTBALL:
        tree_url = (
            f"https://api.github.com/repos/{_CONFIG[FOOTBALL]['repo']}/git/trees/"
            f"{observation.ref}?recursive=1"
        )
        tree = client.get(tree_url, cancel=cancel, max_bytes=_MAX_METADATA_BYTES)
        if tree.status != 200:
            raise RefreshSourceError("upstream_http", f"football tree HTTP {tree.status}")
        captured_paths = _football_paths(tree.body, str(observation.season))
        if captured_paths != observation.current_paths:
            raise RefreshSourceError(
                "source_changed_during_refresh",
                "football capability disagrees with its pinned tree",
                retryable=False,
            )
        store("git-tree.json", tree_url, tree)

    for relative in source_paths(observation):
        if cancel is not None and cancel.is_set():
            raise RefreshCancelled()
        url = _raw_url(observation.source_id, observation.ref, relative)
        response = client.get(
            url,
            headers={"Accept": "application/octet-stream"},
            max_bytes=_MAX_FILE_BYTES,
            cancel=cancel,
        )
        if response.status != 200:
            raise RefreshSourceError("upstream_http", f"{relative}: HTTP {response.status}")
        store(relative, url, response)
    return {
        "schema_version": "0.1.0",
        "source_id": observation.source_id,
        "repository": _CONFIG[observation.source_id]["repo"],
        "branch": _CONFIG[observation.source_id]["branch"],
        "upstream_ref": observation.ref,
        "upstream_committed_at_utc": observation.committed_at_utc,
        "retrieved_at_utc": observation.checked_at_utc,
        "etag": observation.etag,
        "license": "CC0-1.0",
        "files": receipts,
    }
