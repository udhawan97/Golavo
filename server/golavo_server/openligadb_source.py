"""Strict OpenLigaDB source adapter for the isolated ODbL overlay.

This module is the overlay's only network boundary.  Callers choose from fixed
competition shortcuts; they can never supply a URL, host, endpoint shape or
team filter.  Every response is retained byte-for-byte before parsing and is
identified by SHA-256 in the immutable generation manifest.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Event
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

SOURCE_ID = "openligadb"
LICENSE_ID = "ODbL-1.0"
API_ORIGIN = "https://api.openligadb.de"
ATTRIBUTION = "Datenquelle: OpenLigaDB (www.openligadb.de) — Open Database License (ODbL) v1.0."
LICENSE_URL = "https://www.openligadb.de/lizenz"
SOURCE_URL = "https://www.openligadb.de/"
COMPETITION_SHORTCUTS = ("bl1", "bl2", "bl3", "dfb")
DEFAULT_INTERVAL_SECONDS = 12 * 60 * 60
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_SNAPSHOT_BYTES = 64 * 1024 * 1024
TOTAL_RESPONSE_TIMEOUT_SECONDS = 60.0

_EXPECTED_NAME_PREFIXES = {
    "bl1": ("1. Fußball-Bundesliga",),
    "bl2": ("2. Fußball-Bundesliga",),
    "bl3": ("3. Liga",),
    "dfb": ("DFB Pokal", "DFB-Pokal"),
}
_SEASON_RE = re.compile(r"^[0-9]{4}$")
_APPROVED_PATHS = (
    re.compile(r"^/getavailableleagues/(?P<season>[0-9]{4})$"),
    re.compile(r"^/getavailablegroups/(?P<shortcut>bl1|bl2|bl3|dfb)/(?P<season>[0-9]{4})$"),
    re.compile(
        r"^/getlastchangedate/(?P<shortcut>bl1|bl2|bl3|dfb)/"
        r"(?P<season>[0-9]{4})/(?P<group>[1-9][0-9]{0,2})$"
    ),
    re.compile(
        r"^/getmatchdata/(?P<shortcut>bl1|bl2|bl3|dfb)/"
        r"(?P<season>[0-9]{4})/(?P<group>[1-9][0-9]{0,2})$"
    ),
)


def utc_z(value: datetime | None = None) -> str:
    return (
        (value or datetime.now(UTC))
        .astimezone(UTC)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def current_season(value: datetime | None = None) -> str:
    now = (value or datetime.now(UTC)).astimezone(UTC)
    return str(now.year if now.month >= 7 else now.year - 1)


class OpenLigaDBError(Exception):
    def __init__(self, code: str, message: str, *, retryable: bool = True) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class OpenLigaDBConflict(OpenLigaDBError):
    def __init__(self, message: str) -> None:
        super().__init__("source_conflict", message, retryable=False)


class OpenLigaDBCancelled(OpenLigaDBError):
    def __init__(self) -> None:
        super().__init__("cancelled", "OpenLigaDB refresh cancelled", retryable=False)


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: dict[str, str]
    body: bytes
    final_url: str


def approved_path(path: str, *, season: str | None = None) -> bool:
    """Whether a path matches the frozen endpoint and identity allowlist."""
    if not path.startswith("/") or "?" in path or "#" in path:
        return False
    for pattern in _APPROVED_PATHS:
        matched = pattern.fullmatch(path)
        if matched is not None:
            return season is None or matched.group("season") == season
    return False


def _validate_url(url: str, *, season: str | None = None) -> None:
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "api.openligadb.de"
        or parsed.port not in (None, 443)
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or not approved_path(parsed.path, season=season)
    ):
        raise OpenLigaDBError(
            "unsafe_endpoint", f"unapproved OpenLigaDB URL: {url}", retryable=False
        )


class ApiFetcher:
    """Injectable, bounded HTTPS client that rejects redirect/path drift."""

    def get_path(
        self,
        path: str,
        *,
        season: str,
        cancel: Event | None = None,
        max_bytes: int = MAX_RESPONSE_BYTES,
    ) -> HttpResponse:
        if not approved_path(path, season=season):
            raise OpenLigaDBError(
                "unsafe_endpoint", f"unapproved OpenLigaDB path: {path}", retryable=False
            )
        url = API_ORIGIN + path
        _validate_url(url, season=season)
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "Golavo-OpenLigaDB-overlay/1",
            },
            method="GET",
        )
        started = time.monotonic()
        try:
            try:
                response = urlopen(request, timeout=20)  # noqa: S310 - strict allowlist
            except HTTPError as exc:
                if exc.code in (429, 503):
                    raise OpenLigaDBError(
                        "rate_limited", f"OpenLigaDB returned HTTP {exc.code}"
                    ) from exc
                raise OpenLigaDBError(
                    "upstream_http", f"OpenLigaDB returned HTTP {exc.code}"
                ) from exc
            with response:
                final_url = response.geturl()
                _validate_url(final_url, season=season)
                if final_url != url:
                    raise OpenLigaDBError(
                        "unsafe_redirect",
                        f"OpenLigaDB redirected {path} to a different endpoint",
                        retryable=False,
                    )
                declared = response.headers.get("Content-Length")
                if declared is not None and int(declared) > max_bytes:
                    raise OpenLigaDBError(
                        "download_too_large",
                        f"OpenLigaDB response exceeds {max_bytes} bytes",
                        retryable=False,
                    )
                chunks: list[bytes] = []
                total = 0
                while True:
                    if cancel is not None and cancel.is_set():
                        raise OpenLigaDBCancelled()
                    if time.monotonic() - started > TOTAL_RESPONSE_TIMEOUT_SECONDS:
                        raise OpenLigaDBError("timeout", "OpenLigaDB response exceeded 60 seconds")
                    chunk = response.read(64 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_bytes:
                        raise OpenLigaDBError(
                            "download_too_large",
                            f"OpenLigaDB response exceeds {max_bytes} bytes",
                            retryable=False,
                        )
                    chunks.append(chunk)
                return HttpResponse(
                    status=int(response.status),
                    headers={key.lower(): value for key, value in response.headers.items()},
                    body=b"".join(chunks),
                    final_url=final_url,
                )
        except OpenLigaDBError:
            raise
        except (TimeoutError, URLError, OSError, ValueError) as exc:
            code = "timeout" if isinstance(exc, TimeoutError) else "offline"
            raise OpenLigaDBError(code, f"could not reach OpenLigaDB: {exc}") from exc


def _loads(payload: bytes, context: str) -> Any:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f"duplicate JSON key {key!r}")
            value[key] = item
        return value

    try:
        return json.loads(payload, object_pairs_hook=reject_duplicates)
    except (TypeError, ValueError, UnicodeDecodeError) as exc:
        raise OpenLigaDBError(
            "invalid_schema", f"{context}: invalid or ambiguous JSON", retryable=False
        ) from exc


def _league_rows(payload: bytes, season: str) -> dict[str, dict[str, Any]]:
    rows = _loads(payload, "available leagues")
    if not isinstance(rows, list):
        raise OpenLigaDBError(
            "invalid_schema", "available leagues must be an array", retryable=False
        )
    by_shortcut: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise OpenLigaDBError(
                "invalid_schema", "available league row is not an object", retryable=False
            )
        shortcut = str(row.get("leagueShortcut") or "").casefold()
        if shortcut in COMPETITION_SHORTCUTS:
            by_shortcut.setdefault(shortcut, []).append(row)
    resolved: dict[str, dict[str, Any]] = {}
    for shortcut, candidates in by_shortcut.items():
        if len(candidates) != 1:
            raise OpenLigaDBConflict(f"multiple current-season rows use shortcut {shortcut!r}")
        row = candidates[0]
        sport = row.get("sport")
        name = str(row.get("leagueName") or "")
        if (
            str(row.get("leagueSeason")) != season
            or not isinstance(sport, dict)
            or sport.get("sportId") != 1
            or not any(name.startswith(prefix) for prefix in _EXPECTED_NAME_PREFIXES[shortcut])
            or not isinstance(row.get("leagueId"), int)
        ):
            raise OpenLigaDBConflict(
                f"shortcut {shortcut!r} does not match Golavo's frozen competition identity"
            )
        resolved[shortcut] = row
    return resolved


def _group_rows(payload: bytes, shortcut: str) -> list[dict[str, Any]]:
    rows = _loads(payload, f"{shortcut} groups")
    if not isinstance(rows, list):
        raise OpenLigaDBError(
            "invalid_schema", f"{shortcut} groups must be an array", retryable=False
        )
    seen_order: set[int] = set()
    seen_id: set[int] = set()
    result: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            raise OpenLigaDBError(
                "invalid_schema", f"{shortcut} group is not an object", retryable=False
            )
        order = row.get("groupOrderID")
        group_id = row.get("groupID")
        name = row.get("groupName")
        if (
            not isinstance(order, int)
            or not 1 <= order <= 999
            or not isinstance(group_id, int)
            or not isinstance(name, str)
            or not name.strip()
        ):
            raise OpenLigaDBError(
                "invalid_schema", f"{shortcut} returned an invalid group", retryable=False
            )
        if order in seen_order or group_id in seen_id:
            raise OpenLigaDBConflict(f"{shortcut} returned duplicate group identities")
        seen_order.add(order)
        seen_id.add(group_id)
        result.append(row)
    return sorted(result, key=lambda item: int(item["groupOrderID"]))


def _safe_relative(relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise OpenLigaDBError(
            "unsafe_path", f"unsafe raw response path: {relative}", retryable=False
        )
    return path


def capture_snapshot(
    raw_root: Path,
    selected: list[str] | tuple[str, ...],
    *,
    fetcher: ApiFetcher | None = None,
    cancel: Event | None = None,
    now: datetime | None = None,
    reuse_from: Path | None = None,
) -> dict[str, Any]:
    """Capture and validate one current-season raw snapshot.

    Missing allowlisted competitions are an honest capability state. Ambiguous
    identities, malformed groups, non-JSON bodies, partial downloads and any
    endpoint drift fail the whole candidate before a database is built.
    """
    chosen = list(selected)
    if not chosen or len(chosen) != len(set(chosen)):
        raise OpenLigaDBError(
            "invalid_selection",
            "competition selection must be non-empty and unique",
            retryable=False,
        )
    unknown = sorted(set(chosen) - set(COMPETITION_SHORTCUTS))
    if unknown:
        raise OpenLigaDBError(
            "invalid_selection", f"unapproved competition shortcuts: {unknown}", retryable=False
        )
    chosen.sort(key=COMPETITION_SHORTCUTS.index)
    season = current_season(now)
    if _SEASON_RE.fullmatch(season) is None:
        raise OpenLigaDBError("invalid_season", season, retryable=False)
    captured_at = utc_z(now)
    root = Path(raw_root)
    root.mkdir(parents=True, exist_ok=False)
    client = fetcher or ApiFetcher()
    receipts: list[dict[str, Any]] = []
    total = 0
    previous_receipts: dict[str, dict[str, Any]] = {}
    previous_root: Path | None = None
    if reuse_from is not None:
        previous_root = Path(reuse_from)
        try:
            previous_manifest = json.loads(
                (previous_root / "generation.json").read_text(encoding="utf-8")
            )
        except (OSError, TypeError, ValueError):
            previous_manifest = {}
        for item in previous_manifest.get("raw_receipts", []):
            if isinstance(item, dict) and isinstance(item.get("endpoint"), str):
                previous_receipts[str(item["endpoint"])] = item

    def fetch_store(path: str, relative: str) -> bytes:
        nonlocal total
        if cancel is not None and cancel.is_set():
            raise OpenLigaDBCancelled()
        response = client.get_path(path, season=season, cancel=cancel)
        if response.status != 200:
            raise OpenLigaDBError("upstream_http", f"{path}: HTTP {response.status}")
        content_type = response.headers.get("content-type", "")
        if content_type and "json" not in content_type.casefold():
            raise OpenLigaDBError(
                "invalid_content_type",
                f"{path}: expected JSON, got {content_type}",
                retryable=False,
            )
        total += len(response.body)
        if total > MAX_SNAPSHOT_BYTES:
            raise OpenLigaDBError(
                "download_too_large", "OpenLigaDB snapshot exceeds 64 MiB", retryable=False
            )
        target = root / _safe_relative(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        part = target.with_name(target.name + ".part")
        try:
            with part.open("xb") as handle:
                handle.write(response.body)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(part, target)
        except Exception:
            part.unlink(missing_ok=True)
            raise
        digest = hashlib.sha256(response.body).hexdigest()
        receipts.append(
            {
                "path": target.relative_to(root).as_posix(),
                "endpoint": path,
                "sha256": digest,
                "bytes": len(response.body),
                "content_type": content_type or None,
                "captured_at_utc": captured_at,
            }
        )
        return response.body

    def reuse_store(endpoint: str, relative: str) -> bytes | None:
        nonlocal total
        receipt = previous_receipts.get(endpoint)
        if receipt is None or previous_root is None:
            return None
        previous_relative = Path(str(receipt.get("path") or ""))
        if (
            previous_relative.is_absolute()
            or ".." in previous_relative.parts
            or not previous_relative.parts
        ):
            return None
        source = previous_root / "raw" / previous_relative
        try:
            body = source.read_bytes()
        except OSError:
            return None
        if hashlib.sha256(body).hexdigest() != receipt.get("sha256"):
            return None
        total += len(body)
        if total > MAX_SNAPSHOT_BYTES:
            raise OpenLigaDBError(
                "download_too_large", "OpenLigaDB snapshot exceeds 64 MiB", retryable=False
            )
        target = root / _safe_relative(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        part = target.with_name(target.name + ".part")
        try:
            with part.open("xb") as handle:
                with source.open("rb") as input_handle:
                    shutil.copyfileobj(input_handle, handle, length=64 * 1024)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(part, target)
        except Exception:
            part.unlink(missing_ok=True)
            raise
        receipts.append(
            {
                "path": target.relative_to(root).as_posix(),
                "endpoint": endpoint,
                "sha256": receipt["sha256"],
                "bytes": len(body),
                "content_type": receipt.get("content_type"),
                "captured_at_utc": receipt.get("captured_at_utc") or captured_at,
                "reused_at_utc": captured_at,
            }
        )
        return body

    leagues_path = f"/getavailableleagues/{season}"
    leagues_body = fetch_store(leagues_path, "available-leagues.json")
    leagues = _league_rows(leagues_body, season)
    capabilities: list[dict[str, Any]] = []
    competitions: list[dict[str, Any]] = []
    for shortcut in chosen:
        league = leagues.get(shortcut)
        if league is None:
            capabilities.append(
                {
                    "shortcut": shortcut,
                    "season": season,
                    "state": "absent",
                    "reason": (
                        "OpenLigaDB does not publish this allowlisted competition "
                        "for the current season"
                    ),
                }
            )
            continue
        groups_path = f"/getavailablegroups/{shortcut}/{season}"
        groups_body = fetch_store(groups_path, f"{shortcut}/groups.json")
        groups = _group_rows(groups_body, shortcut)
        if not groups:
            capabilities.append(
                {
                    "shortcut": shortcut,
                    "season": season,
                    "state": "absent",
                    "reason": "OpenLigaDB publishes the league identity but no groups",
                }
            )
            continue
        competitions.append({"shortcut": shortcut, "league": league, "groups": groups})
        capabilities.append(
            {
                "shortcut": shortcut,
                "season": season,
                "state": "available",
                "reason": None,
                "league_id": league["leagueId"],
                "league_name": league["leagueName"],
                "group_count": len(groups),
            }
        )
        for group in groups:
            order = int(group["groupOrderID"])
            changed_path = f"/getlastchangedate/{shortcut}/{season}/{order}"
            changed_body = fetch_store(
                changed_path, f"{shortcut}/groups/{order:03d}-last-change.json"
            )
            changed_value = _loads(changed_body, f"{shortcut} group {order} last change")
            if not isinstance(changed_value, str) or not changed_value.strip():
                raise OpenLigaDBError(
                    "invalid_schema",
                    f"{shortcut} group {order} returned an invalid last-change value",
                    retryable=False,
                )
            matches_path = f"/getmatchdata/{shortcut}/{season}/{order}"
            matches_relative = f"{shortcut}/groups/{order:03d}-matches.json"
            matches_body: bytes | None = None
            previous_changed = previous_receipts.get(changed_path)
            if previous_changed is not None and previous_root is not None:
                previous_changed_path = (
                    previous_root / "raw" / str(previous_changed.get("path") or "")
                )
                try:
                    previous_changed_body = previous_changed_path.read_bytes()
                except OSError:
                    previous_changed_body = b""
                if (
                    hashlib.sha256(previous_changed_body).hexdigest()
                    == previous_changed.get("sha256")
                    and _loads(
                        previous_changed_body,
                        f"previous {shortcut} group {order} last change",
                    )
                    == changed_value
                ):
                    matches_body = reuse_store(matches_path, matches_relative)
            if matches_body is None:
                matches_body = fetch_store(matches_path, matches_relative)
            matches_value = _loads(matches_body, f"{shortcut} group {order} matches")
            if not isinstance(matches_value, list):
                raise OpenLigaDBError(
                    "invalid_schema",
                    f"{shortcut} group {order} matches must be an array",
                    retryable=False,
                )

    # The available-leagues response contains every community-created league.
    # Retain its exact bytes for provenance, but do not let an unrelated league
    # churn Golavo's active generation. Only the selected allowlisted identities
    # and their own group/revision/match responses define relevant content.
    identity_revision = []
    for shortcut in chosen:
        row = leagues.get(shortcut)
        identity_revision.append(
            {
                "shortcut": shortcut,
                "league_id": row.get("leagueId") if row else None,
                "league_name": row.get("leagueName") if row else None,
                "league_season": row.get("leagueSeason") if row else None,
                "sport_id": (row.get("sport") or {}).get("sportId") if row else None,
            }
        )
    revision_payload = {
        "season": season,
        "identities": identity_revision,
        "responses": [
            {"endpoint": item["endpoint"], "sha256": item["sha256"]}
            for item in sorted(receipts, key=lambda item: str(item["endpoint"]))
            if item["endpoint"] != leagues_path
        ],
    }
    content_revision = hashlib.sha256(
        json.dumps(revision_payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": "0.1.0",
        "source_id": SOURCE_ID,
        "license": LICENSE_ID,
        "season": season,
        "captured_at_utc": captured_at,
        "selected_competitions": chosen,
        "content_revision": content_revision,
        "receipts": receipts,
        "competitions": competitions,
        "capabilities": capabilities,
    }
