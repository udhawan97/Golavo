"""Consent-gated, display-only Sportmonks outside signals.

This module is intentionally not part of ``golavo_core``. Sportmonks
predictions, bookmaker prices, lineups, and player match statistics are
third-party context displayed beside a Golavo match; they never enter fitting,
sealing, settlement, calibration, scoring, AI evidence, or exports. Requests
happen only after an explicit UI action and responses are never persisted.
"""

from __future__ import annotations

import hashlib
import http.client
import json
import math
import os
import re
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import unicodedata
from collections.abc import Callable
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import certifi

from golavo_server import runtime

SOURCE_ID = "sportmonks-v3"
SOURCE_NAME = "Sportmonks Football API v3"
API_HOST = "api.sportmonks.com"
TERMS_URL = "https://www.sportmonks.com/terms-of-service/"
PRIVACY_URL = "https://www.sportmonks.com/privacy-policy/"
PRICING_URL = "https://www.sportmonks.com/football-api/plans-pricing/"
DOCS_URL = "https://docs.sportmonks.com/v3/"
TERMS_REVIEWED_DATE = "2026-08-30"
TERMS_CONTENT_SHA256 = "43901aed7fd5e36e36205e814a064d5851ecb66df8387f0079a586bed6df8aeb"
TERMS_ACCEPTANCE_VERSION = f"sportmonks-terms-sha256:{TERMS_CONTENT_SHA256}"
SCHEMA_VERSION = "0.1.0"
CAPABILITIES = ("external_prediction", "external_odds", "player_lens")
ENV_KEY = "SPORTMONKS_API_TOKEN"
KEYCHAIN_SERVICE = "golavo-sportmonks"
KEYCHAIN_ACCOUNT = "golavo"
MAX_RESPONSE_BYTES = 2_000_000
MAX_FIXTURE_PAGES = 4
MATCH_WINNER_MARKET_ID = 1
FULLTIME_RESULT_PREDICTION_TYPE_ID = 237
TOP_FIVE_COMPETITIONS = {
    "English Premier League",
    "Bundesliga",
    "La Liga",
    "Serie A",
    "Ligue 1",
}
SPORTMONKS_COMPETITION_NAMES = {
    "English Premier League": "Premier League",
    "Bundesliga": "Bundesliga",
    "La Liga": "La Liga",
    "Serie A": "Serie A",
    "Ligue 1": "Ligue 1",
}
MAX_LINEUP_PLAYERS = 60
PLAYER_METRIC_SCHEMA: dict[int, tuple[str, str, str]] = {
    # Pinned from Sportmonks' official fixture-player statistics definition.
    # (developer_name, Golavo display label, unit)
    40: ("CAPTAIN", "Captain", "boolean"),
    41: ("SHOTS_OFF_TARGET", "Shots off target", "count"),
    42: ("SHOTS_TOTAL", "Total shots", "count"),
    52: ("GOALS", "Goals", "count"),
    56: ("FOULS", "Fouls", "count"),
    57: ("SAVES", "Saves", "count"),
    58: ("SHOTS_BLOCKED", "Shots blocked", "count"),
    64: ("HIT_WOODWORK", "Hit woodwork", "count"),
    78: ("TACKLES", "Tackles", "count"),
    79: ("ASSISTS", "Assists", "count"),
    80: ("PASSES", "Passes", "count"),
    82: ("SUCCESSFUL_PASSES_PERCENTAGE", "Successful passes", "percent"),
    83: ("REDCARDS", "Red cards", "count"),
    84: ("YELLOWCARDS", "Yellow cards", "count"),
    85: ("YELLOWRED_CARDS", "Second-yellow red cards", "count"),
    86: ("SHOTS_ON_TARGET", "Shots on target", "count"),
    88: ("GOALS_CONCEDED", "Goals conceded", "count"),
    94: ("DISPOSSESSED", "Dispossessed", "count"),
    96: ("PLAYER_FOULS_DRAWN", "Fouls drawn", "count"),
    98: ("TOTAL_CROSSES", "Crosses", "count"),
    99: ("ACCURATE_CROSSES", "Accurate crosses", "count"),
    100: ("INTERCEPTIONS", "Interceptions", "count"),
    101: ("CLEARANCES", "Clearances", "count"),
    104: ("SAVES_INSIDE_BOX", "Saves inside box", "count"),
    105: ("TOTAL_DUELS", "Duels", "count"),
    106: ("DUELS_WON", "Duels won", "count"),
    107: ("AERIALS_WON", "Aerials won", "count"),
    108: ("DRIBBLE_ATTEMPTS", "Dribble attempts", "count"),
    109: ("SUCCESSFUL_DRIBBLES", "Successful dribbles", "count"),
    110: ("DRIBBLED_PAST", "Dribbled past", "count"),
    116: ("ACCURATE_PASSES", "Accurate passes", "count"),
    117: ("KEY_PASSES", "Key passes", "count"),
    118: ("RATING", "Provider rating", "provider_score"),
    119: ("MINUTES_PLAYED", "Minutes played", "minutes"),
    120: ("TOUCHES", "Touches", "count"),
    122: ("LONG_BALLS", "Long balls", "count"),
    123: ("LONG_BALLS_WON", "Accurate long balls", "count"),
    581: ("BIG_CHANCES_MISSED", "Big chances missed", "count"),
    1491: ("DUELS_LOST", "Duels lost", "count"),
    1584: ("ACCURATE_PASSES_PERCENTAGE", "Accurate passes", "percent"),
    1605: ("SUCCESSFUL_DRIBBLES_PERCENTAGE", "Successful dribbles", "percent"),
}
PLAYER_METRIC_FILTER = ",".join(str(value) for value in sorted(PLAYER_METRIC_SCHEMA))
MAX_PLAYER_METRICS = len(PLAYER_METRIC_SCHEMA)

_REQUEST_LOCAL = threading.local()
_ACTIVE_REQUEST_LOCK = threading.Lock()
_ACTIVE_REQUESTS: set[threading.Event] = set()
_ACTIVE_CONNECTIONS: dict[threading.Event, set[http.client.HTTPSConnection]] = {}


class SportmonksError(Exception):
    """A bounded, user-safe connector failure."""

    def __init__(self, code: str, message: str, *, status: int, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.status = status
        self.retryable = retryable


Fetcher = Callable[[str, str], tuple[dict[str, Any], str]]


def _active_cancel_event() -> threading.Event | None:
    value = getattr(_REQUEST_LOCAL, "cancel_event", None)
    return value if isinstance(value, threading.Event) else None


def _ensure_request_active() -> None:
    event = _active_cancel_event()
    if event is not None and event.is_set():
        raise SportmonksError(
            "request_cancelled",
            "Sportmonks request was cancelled after the connector was disabled",
            status=409,
        )


@contextmanager
def _request_scope(event: threading.Event):
    previous = getattr(_REQUEST_LOCAL, "cancel_event", None)
    with _ACTIVE_REQUEST_LOCK:
        _ACTIVE_REQUESTS.add(event)
        _ACTIVE_CONNECTIONS[event] = set()
    _REQUEST_LOCAL.cancel_event = event
    try:
        yield
    finally:
        with _ACTIVE_REQUEST_LOCK:
            connections = _ACTIVE_CONNECTIONS.pop(event, set())
            _ACTIVE_REQUESTS.discard(event)
        for connection in connections:
            connection.close()
        if previous is None:
            delattr(_REQUEST_LOCAL, "cancel_event")
        else:
            _REQUEST_LOCAL.cancel_event = previous


def cancel_pending_requests() -> int:
    """Stop connector work already running in sidecar worker threads."""
    with _ACTIVE_REQUEST_LOCK:
        events = list(_ACTIVE_REQUESTS)
        connections = [
            connection
            for event in events
            for connection in _ACTIVE_CONNECTIONS.get(event, set())
        ]
        for event in events:
            event.set()
    for connection in connections:
        try:
            if connection.sock is not None:
                connection.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        connection.close()
    return len(events)


def _cancellable_transport(fetcher: Fetcher) -> Fetcher:
    def fetch(path: str, token: str) -> tuple[dict[str, Any], str]:
        _ensure_request_active()
        result = fetcher(path, token)
        _ensure_request_active()
        return result

    return fetch


def _utc_z(value: datetime | None = None) -> str:
    current = value or datetime.now(UTC)
    return current.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _root() -> Path:
    root = runtime.sportmonks_dir()
    if root is None:
        raise RuntimeError("Sportmonks settings require the installed desktop app")
    return root


def _settings_path() -> Path:
    return _root() / "settings.json"


def default_settings() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "enabled": False,
        "capabilities": list(CAPABILITIES),
        "terms_accepted_at_utc": None,
        "terms_acceptance_version": None,
    }


def load_settings() -> dict[str, Any]:
    try:
        value = json.loads(_settings_path().read_text(encoding="utf-8"))
    except (OSError, RuntimeError, TypeError, ValueError):
        return default_settings()
    if not isinstance(value, dict) or value.get("schema_version") != SCHEMA_VERSION:
        return default_settings()
    enabled = value.get("enabled") is True
    capabilities = value.get("capabilities")
    accepted_at = value.get("terms_accepted_at_utc")
    accepted_version = value.get("terms_acceptance_version")
    if (
        not isinstance(capabilities, list)
        or not capabilities
        or not all(isinstance(item, str) for item in capabilities)
        or len(capabilities) != len(set(capabilities))
        or set(capabilities) - set(CAPABILITIES)
    ):
        return default_settings()
    accepted = (
        isinstance(accepted_at, str)
        and accepted_version == TERMS_ACCEPTANCE_VERSION
    )
    if enabled and not accepted:
        enabled = False
    return {
        "schema_version": SCHEMA_VERSION,
        "enabled": enabled,
        "capabilities": capabilities,
        "terms_accepted_at_utc": accepted_at if accepted else None,
        "terms_acceptance_version": accepted_version if accepted else None,
    }


def _atomic_settings(payload: dict[str, Any]) -> None:
    path = _settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=".settings-",
            delete=False,
        ) as handle:
            json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        os.replace(temporary, path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink(missing_ok=True)


def configure(value: dict[str, Any]) -> dict[str, Any]:
    allowed = {"enabled", "capabilities", "accept_terms"}
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ValueError(f"unknown Sportmonks settings fields: {unknown}")
    current = load_settings()
    enabled = value.get("enabled", current["enabled"])
    capabilities = value.get("capabilities", current["capabilities"])
    if not isinstance(enabled, bool):
        raise ValueError("enabled must be boolean")
    if (
        not isinstance(capabilities, list)
        or not capabilities
        or not all(isinstance(item, str) for item in capabilities)
        or len(capabilities) != len(set(capabilities))
        or set(capabilities) - set(CAPABILITIES)
    ):
        raise ValueError("capabilities must be a non-empty, unique allowlisted list")
    accepted_at = current["terms_accepted_at_utc"]
    accepted_version = current["terms_acceptance_version"]
    if enabled and accepted_version != TERMS_ACCEPTANCE_VERSION:
        if value.get("accept_terms") is not True:
            raise PermissionError(
                "review and accept the current Sportmonks disclosure before enabling"
            )
        accepted_at = _utc_z()
        accepted_version = TERMS_ACCEPTANCE_VERSION
    if not enabled or capabilities != current["capabilities"]:
        cancel_pending_requests()
    payload = {
        "schema_version": SCHEMA_VERSION,
        "enabled": enabled,
        "capabilities": capabilities,
        "terms_accepted_at_utc": accepted_at,
        "terms_acceptance_version": accepted_version,
    }
    _atomic_settings(payload)
    return status()


def _run_security(
    args: list[str], *, input_text: str | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["security", *args],
        input=input_text,
        capture_output=True,
        text=True,
        timeout=8,
        check=False,
    )


def load_api_token() -> tuple[str | None, str]:
    """Load a token without ever returning it to an API caller."""
    environment = os.environ.get(ENV_KEY, "").strip()
    if environment:
        return environment, "environment"
    if sys.platform != "darwin":
        return None, "none"
    try:
        result = _run_security(
            ["find-generic-password", "-s", KEYCHAIN_SERVICE, "-a", KEYCHAIN_ACCOUNT, "-w"]
        )
    except (OSError, subprocess.SubprocessError):
        return None, "none"
    token = result.stdout.strip() if result.returncode == 0 else ""
    return (token, "keychain") if token else (None, "none")


_TOKEN_RE = re.compile(r"[A-Za-z0-9._-]{12,512}\Z")


def save_api_token(token: str) -> dict[str, Any]:
    if runtime.launch_token() is None:
        raise RuntimeError("credential changes require the private desktop app")
    if sys.platform != "darwin":
        raise RuntimeError(f"set {ENV_KEY} in the environment on this platform")
    if not isinstance(token, str) or _TOKEN_RE.fullmatch(token) is None:
        raise ValueError("Sportmonks token must be 12-512 safe token characters")
    try:
        # Leaving -w as the final argument makes `security` read the secret from
        # stdin, keeping it out of the process list and server logs.
        result = _run_security(
            [
                "add-generic-password",
                "-s",
                KEYCHAIN_SERVICE,
                "-a",
                KEYCHAIN_ACCOUNT,
                "-U",
                "-w",
            ],
            input_text=f"{token}\n",
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError("macOS Keychain could not store the Sportmonks token") from exc
    if result.returncode != 0:
        raise RuntimeError("macOS Keychain rejected the Sportmonks token")
    return status()


def delete_api_token() -> dict[str, Any]:
    cancel_pending_requests()
    if runtime.launch_token() is None:
        raise RuntimeError("credential changes require the private desktop app")
    if os.environ.get(ENV_KEY):
        raise RuntimeError(f"remove {ENV_KEY} from the environment to disconnect it")
    if sys.platform != "darwin":
        raise RuntimeError(f"remove {ENV_KEY} from the environment on this platform")
    try:
        result = _run_security(
            ["delete-generic-password", "-s", KEYCHAIN_SERVICE, "-a", KEYCHAIN_ACCOUNT]
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError("macOS Keychain could not remove the Sportmonks token") from exc
    if result.returncode not in (0, 44):
        raise RuntimeError("macOS Keychain could not remove the Sportmonks token")
    return status()


def status() -> dict[str, Any]:
    settings = load_settings()
    token, source = load_api_token()
    return {
        **settings,
        "provider": {
            "source_id": SOURCE_ID,
            "name": SOURCE_NAME,
            "docs_url": DOCS_URL,
            "terms_url": TERMS_URL,
            "privacy_url": PRIVACY_URL,
            "pricing_url": PRICING_URL,
            "terms_reviewed_date": TERMS_REVIEWED_DATE,
            "terms_content_sha256": TERMS_CONTENT_SHA256,
            "terms_acceptance_version": TERMS_ACCEPTANCE_VERSION,
        },
        "connector_supported": runtime.sportmonks_dir() is not None,
        "credential": {
            "configured": token is not None,
            "source": source,
            "writable": runtime.launch_token() is not None and sys.platform == "darwin",
            "environment_variable": ENV_KEY,
        },
        "request_policy": "foreground_click_only",
        "storage_policy": "derived_response_memory_only",
        "usage": {
            "display": True,
            "model_input": False,
            "forecast_sealing": False,
            "forecast_settlement": False,
            "calibration": False,
            "scoring": False,
            "ai_evidence": False,
            "exports": False,
        },
    }


_ALLOWED_PATH = re.compile(
    r"/v3/football/(?:"
    r"fixtures/date/\d{4}-\d{2}-\d{2}\?include=participants;league;season&per_page=50&page=[1-4]"
    rf"|fixtures/\d+\?include=lineups\.details\.type;metadata\.type&filters=lineupDetailTypes:{re.escape(PLAYER_METRIC_FILTER)}"
    r"|predictions/probabilities/fixtures/\d+\?include=type"
    r"|odds/pre-match/fixtures/\d+/markets/1\?include=bookmaker;market"
    r")\Z"
)


def _request_json(path: str, token: str) -> tuple[dict[str, Any], str]:
    _ensure_request_active()
    if _ALLOWED_PATH.fullmatch(path) is None:
        raise SportmonksError(
            "path_rejected", "provider request path was not allowlisted", status=500
        )
    context = ssl.create_default_context(cafile=certifi.where())
    connection = http.client.HTTPSConnection(API_HOST, timeout=12, context=context)
    event = _active_cancel_event()
    if event is not None:
        with _ACTIVE_REQUEST_LOCK:
            if event.is_set():
                connection.close()
                _ensure_request_active()
            _ACTIVE_CONNECTIONS.setdefault(event, set()).add(connection)
    try:
        connection.request(
            "GET",
            path,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
                "Cache-Control": "no-store",
                "User-Agent": "Golavo/0.17 outside-signals",
            },
        )
        response = connection.getresponse()
        body = response.read(MAX_RESPONSE_BYTES + 1)
    except (OSError, TimeoutError, http.client.HTTPException) as exc:
        _ensure_request_active()
        raise SportmonksError(
            "provider_unavailable",
            "Sportmonks did not answer in time",
            status=503,
            retryable=True,
        ) from exc
    finally:
        if event is not None:
            with _ACTIVE_REQUEST_LOCK:
                _ACTIVE_CONNECTIONS.get(event, set()).discard(connection)
        connection.close()
    _ensure_request_active()
    if len(body) > MAX_RESPONSE_BYTES:
        raise SportmonksError(
            "response_too_large", "Sportmonks response exceeded the safe size limit", status=502
        )
    if response.status == 401:
        raise SportmonksError(
            "credential_rejected", "Sportmonks rejected the API token", status=401
        )
    if response.status == 403:
        raise SportmonksError(
            "plan_missing",
            "This Sportmonks plan does not include the requested feed",
            status=403,
        )
    if response.status == 429:
        raise SportmonksError(
            "rate_limited",
            "Sportmonks rate limit reached; try again after the provider reset",
            status=429,
            retryable=True,
        )
    if response.status >= 500:
        raise SportmonksError(
            "provider_unavailable",
            "Sportmonks is temporarily unavailable",
            status=503,
            retryable=True,
        )
    if response.status != 200:
        raise SportmonksError(
            "provider_rejected", f"Sportmonks returned HTTP {response.status}", status=502
        )
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SportmonksError(
            "malformed_response", "Sportmonks returned malformed JSON", status=502
        ) from exc
    if not isinstance(payload, dict):
        raise SportmonksError(
            "malformed_response", "Sportmonks returned an unexpected response", status=502
        )
    return payload, hashlib.sha256(body).hexdigest()


def _normal_name(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(character for character in normalized if character.isalnum())


def _participant(fixture: dict[str, Any], location: str) -> dict[str, Any] | None:
    participants = fixture.get("participants")
    if not isinstance(participants, list):
        return None
    matches = []
    for participant in participants:
        if isinstance(participant, dict):
            meta = participant.get("meta")
            if isinstance(meta, dict) and meta.get("location") == location:
                matches.append(participant)
    return matches[0] if len(matches) == 1 else None


def _domestic_scope_matches(
    fixture: dict[str, Any], match: dict[str, Any], kickoff: datetime
) -> bool:
    competition = match.get("competition")
    expected_name = SPORTMONKS_COMPETITION_NAMES.get(competition)
    if expected_name is None:
        return False
    league = fixture.get("league")
    season = fixture.get("season")
    if not isinstance(league, dict) or not isinstance(season, dict):
        return False
    if any(
        not isinstance(value.get("id"), int) or isinstance(value.get("id"), bool)
        for value in (league, season)
    ):
        return False
    league_id = fixture.get("league_id")
    season_id = fixture.get("season_id")
    if (
        not isinstance(league_id, int)
        or isinstance(league_id, bool)
        or not isinstance(season_id, int)
        or isinstance(season_id, bool)
        or league_id != league["id"]
        or season_id != season["id"]
    ):
        return False
    if _normal_name(league.get("name")) != _normal_name(expected_name):
        return False
    start = kickoff.year if kickoff.month >= 7 else kickoff.year - 1
    provider_season = _normal_name(season.get("name"))
    return provider_season in {
        f"{start}{str(start + 1)[-2:]}",
        f"{start}{start + 1}",
    }


def _fixture_matches(fixture: dict[str, Any], match: dict[str, Any]) -> bool:
    home = _participant(fixture, "home")
    away = _participant(fixture, "away")
    if home is None or away is None:
        return False
    home_id = home.get("id")
    away_id = away.get("id")
    if (
        not isinstance(home_id, int)
        or isinstance(home_id, bool)
        or not isinstance(away_id, int)
        or isinstance(away_id, bool)
        or home_id == away_id
    ):
        return False
    if _normal_name(home.get("name")) != _normal_name(match.get("home_team")):
        return False
    if _normal_name(away.get("name")) != _normal_name(match.get("away_team")):
        return False
    try:
        kickoff = datetime.fromisoformat(
            str(match["kickoff_utc"]).replace("Z", "+00:00")
        )
    except (KeyError, TypeError, ValueError):
        return False
    provider_timestamp = fixture.get("starting_at_timestamp")
    if not isinstance(provider_timestamp, int) or isinstance(provider_timestamp, bool):
        return False
    provider_kickoff = datetime.fromtimestamp(provider_timestamp, UTC)
    precision = match.get("kickoff_precision")
    if precision == "exact":
        if (
            match.get("competition") in SPORTMONKS_COMPETITION_NAMES
            and not _domestic_scope_matches(fixture, match, kickoff)
        ):
            return False
        return abs(provider_timestamp - kickoff.timestamp()) <= 15 * 60
    if precision == "day":
        return (
            _domestic_scope_matches(fixture, match, kickoff)
            and provider_kickoff.date() == kickoff.date()
        )
    return False


def _find_fixture(
    match: dict[str, Any], token: str, fetcher: Fetcher
) -> tuple[dict[str, Any], list[str], str]:
    if match.get("kickoff_precision") not in {"exact", "day"}:
        raise SportmonksError(
            "match_precision_insufficient",
            "Outside signals require an exact kickoff or a certified calendar date",
            status=422,
        )
    if (
        match.get("kickoff_precision") == "day"
        and match.get("competition") not in SPORTMONKS_COMPETITION_NAMES
    ):
        raise SportmonksError(
            "match_precision_insufficient",
            "Calendar-date matching is limited to a verified domestic competition scope",
            status=422,
        )
    try:
        kickoff = datetime.fromisoformat(str(match["kickoff_utc"]).replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError) as exc:
        raise SportmonksError(
            "match_invalid", "Golavo match kickoff is invalid", status=422
        ) from exc
    date = kickoff.astimezone(UTC).date().isoformat()
    candidates: list[dict[str, Any]] = []
    hashes: list[str] = []
    for page in range(1, MAX_FIXTURE_PAGES + 1):
        query = urlencode({"per_page": 50, "page": page})
        query = f"include=participants;league;season&{query}"
        payload, digest = fetcher(f"/v3/football/fixtures/date/{date}?{query}", token)
        hashes.append(digest)
        rows = payload.get("data")
        if not isinstance(rows, list):
            raise SportmonksError(
                "malformed_response", "Sportmonks fixture rows were malformed", status=502
            )
        candidates.extend(
            fixture
            for fixture in rows
            if isinstance(fixture, dict) and _fixture_matches(fixture, match)
        )
        pagination = payload.get("pagination")
        if not isinstance(pagination, dict):
            meta = payload.get("meta")
            pagination = meta.get("pagination") if isinstance(meta, dict) else None
        if not isinstance(pagination, dict) or not isinstance(
            pagination.get("has_more"), bool
        ):
            raise SportmonksError(
                "malformed_response", "Sportmonks pagination was malformed", status=502
            )
        if page == MAX_FIXTURE_PAGES and pagination["has_more"]:
            raise SportmonksError(
                "fixture_search_truncated",
                "Sportmonks fixture search exceeded the safe page limit",
                status=409,
            )
        if not pagination["has_more"]:
            break
    if not candidates:
        raise SportmonksError(
            "fixture_not_matched",
            "No exact Sportmonks fixture matched both teams and kickoff",
            status=404,
        )
    provider_ids = {item.get("id") for item in candidates}
    if len(candidates) != 1 or len(provider_ids) != 1:
        raise SportmonksError(
            "fixture_ambiguous",
            "More than one Sportmonks fixture matched; no outside signal was promoted",
            status=409,
        )
    fixture = candidates[0]
    if not isinstance(fixture.get("id"), int) or isinstance(fixture.get("id"), bool):
        raise SportmonksError(
            "malformed_response", "Sportmonks fixture id was malformed", status=502
        )
    home = _participant(fixture, "home") or {}
    away = _participant(fixture, "away") or {}
    if any(
        not isinstance(participant.get("id"), int)
        or isinstance(participant.get("id"), bool)
        for participant in (home, away)
    ):
        raise SportmonksError(
            "malformed_response", "Sportmonks participant ids were malformed", status=502
        )
    method = "exact_normalized_teams_and_kickoff"
    if match.get("competition") in SPORTMONKS_COMPETITION_NAMES:
        method = (
            "exact_competition_season_teams_and_kickoff"
            if match.get("kickoff_precision") == "exact"
            else "exact_competition_season_teams_and_calendar_date"
        )
    return fixture, hashes, method


def _unavailable(error: SportmonksError) -> dict[str, Any]:
    return {
        "status": "unavailable",
        "reason_code": error.code,
        "message": str(error),
        "retryable": error.retryable,
    }


def _prediction(
    fixture_id: int, token: str, fetcher: Fetcher
) -> tuple[dict[str, Any], str | None]:
    try:
        payload, digest = fetcher(
            f"/v3/football/predictions/probabilities/fixtures/{fixture_id}?include=type",
            token,
        )
        rows = payload.get("data")
        if not isinstance(rows, list):
            raise SportmonksError(
                "malformed_response", "Sportmonks prediction rows were malformed", status=502
            )
        candidates = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            prediction_type = row.get("type")
            developer_name = (
                prediction_type.get("developer_name")
                if isinstance(prediction_type, dict)
                else None
            )
            if (
                row.get("type_id") == FULLTIME_RESULT_PREDICTION_TYPE_ID
                or developer_name == "FULLTIME_RESULT_PROBABILITY"
            ):
                row_fixture_id = row.get("fixture_id")
                if (
                    not isinstance(row_fixture_id, int)
                    or isinstance(row_fixture_id, bool)
                    or row_fixture_id != fixture_id
                ):
                    raise SportmonksError(
                        "fixture_identity_mismatch",
                        "Sportmonks prediction did not repeat the selected fixture id",
                        status=502,
                    )
                candidates.append(row)
        if len(candidates) != 1:
            raise SportmonksError(
                "prediction_unavailable",
                "Sportmonks has no single full-time result prediction for this fixture",
                status=404,
            )
        row = candidates[0]
        if (
            not isinstance(row.get("id"), int)
            or isinstance(row.get("id"), bool)
            or not isinstance(row.get("type_id"), int)
            or isinstance(row.get("type_id"), bool)
        ):
            raise SportmonksError(
                "malformed_response", "Sportmonks prediction identity was malformed", status=502
            )
        values = row.get("predictions")
        if not isinstance(values, dict):
            raise SportmonksError(
                "malformed_response", "Sportmonks prediction values were malformed", status=502
            )
        parsed: dict[str, float] = {}
        for name in ("home", "draw", "away"):
            raw = values.get(name)
            if not isinstance(raw, (int, float)) or isinstance(raw, bool):
                raise SportmonksError(
                    "malformed_response", "Sportmonks prediction values were incomplete", status=502
                )
            number = float(raw)
            if not math.isfinite(number) or not 0 <= number <= 100:
                raise SportmonksError(
                    "malformed_response",
                    "Sportmonks prediction values were out of range",
                    status=502,
                )
            parsed[name] = number
        if not 99 <= sum(parsed.values()) <= 101:
            raise SportmonksError(
                "malformed_response", "Sportmonks prediction values did not sum to 100%", status=502
            )
        return (
            {
                "status": "available",
                "prediction_id": row.get("id"),
                "type_id": row.get("type_id"),
                "label": "Sportmonks full-time result probability",
                "percent": parsed,
            },
            digest,
        )
    except SportmonksError as exc:
        if exc.code in {
            "credential_rejected",
            "plan_missing",
            "rate_limited",
            "provider_unavailable",
            "request_cancelled",
        }:
            raise
        return _unavailable(exc), None


def _odds(
    fixture_id: int, token: str, fetcher: Fetcher
) -> tuple[dict[str, Any], str | None]:
    try:
        payload, digest = fetcher(
            f"/v3/football/odds/pre-match/fixtures/{fixture_id}/markets/{MATCH_WINNER_MARKET_ID}"
            "?include=bookmaker;market",
            token,
        )
        rows = payload.get("data")
        if not isinstance(rows, list):
            raise SportmonksError(
                "malformed_response", "Sportmonks odds rows were malformed", status=502
            )
        books: dict[int, dict[str, Any]] = {}
        conflicted_books: set[int] = set()
        for row in rows:
            if (
                not isinstance(row, dict)
                or row.get("market_id") != MATCH_WINNER_MARKET_ID
                or row.get("stopped") is True
            ):
                continue
            row_fixture_id = row.get("fixture_id")
            if (
                not isinstance(row_fixture_id, int)
                or isinstance(row_fixture_id, bool)
                or row_fixture_id != fixture_id
            ):
                raise SportmonksError(
                    "fixture_identity_mismatch",
                    "Sportmonks odds did not repeat the selected fixture id",
                    status=502,
                )
            bookmaker_id = row.get("bookmaker_id")
            if not isinstance(bookmaker_id, int) or isinstance(bookmaker_id, bool):
                continue
            label = str(row.get("label") or row.get("name") or "").strip().casefold()
            selection = (
                "home"
                if label in {"home", "1"}
                else "draw"
                if label in {"draw", "x"}
                else "away"
                if label in {"away", "2"}
                else None
            )
            try:
                decimal_value = float(row.get("value"))
            except (TypeError, ValueError):
                continue
            if (
                selection is None
                or not math.isfinite(decimal_value)
                or not 1 < decimal_value < 1000
            ):
                continue
            bookmaker = row.get("bookmaker")
            bookmaker_name = (
                str(bookmaker.get("name")).strip()
                if isinstance(bookmaker, dict) and bookmaker.get("name")
                else f"Bookmaker {bookmaker_id}"
            )
            updated_at = row.get("latest_bookmaker_update") or row.get("updated_at")
            if not isinstance(updated_at, str):
                updated_at = None
            book = books.setdefault(
                bookmaker_id,
                {
                    "bookmaker_id": bookmaker_id,
                    "bookmaker_name": bookmaker_name,
                    "market_id": MATCH_WINNER_MARKET_ID,
                    "market": str(row.get("market_description") or "Match Winner"),
                    "updated_at_utc": updated_at,
                    "decimal": {},
                },
            )
            if selection in book["decimal"]:
                conflicted_books.add(bookmaker_id)
                continue
            book["decimal"][selection] = decimal_value
        complete = [
            book
            for bookmaker_id, book in books.items()
            if bookmaker_id not in conflicted_books
            and set(book["decimal"]) == {"home", "draw", "away"}
        ]
        complete.sort(key=lambda book: (book["bookmaker_name"].casefold(), book["bookmaker_id"]))
        if not complete:
            raise SportmonksError(
                "odds_unavailable",
                "Sportmonks has no complete active match-winner market for this fixture",
                status=404,
            )
        return {
            "status": "available",
            "market": "Match Winner",
            "format": "decimal",
            "bookmakers": complete[:8],
        }, digest
    except SportmonksError as exc:
        if exc.code in {
            "credential_rejected",
            "plan_missing",
            "rate_limited",
            "provider_unavailable",
            "request_cancelled",
        }:
            raise
        return _unavailable(exc), None


def _lineup_confirmed(fixture: dict[str, Any]) -> bool | None:
    rows = fixture.get("metadata")
    if not isinstance(rows, list):
        return None
    values: list[bool] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        kind = row.get("type")
        if not isinstance(kind, dict) or kind.get("developer_name") != "LINEUP_CONFIRMED":
            continue
        type_id = row.get("type_id")
        if (
            not isinstance(type_id, int)
            or isinstance(type_id, bool)
            or kind.get("id") != type_id
        ):
            return None
        value = row.get("values")
        if isinstance(value, bool):
            values.append(value)
        elif isinstance(value, dict):
            nested = value.get("value", value.get("lineup_confirmed"))
            if isinstance(nested, bool):
                values.append(nested)
            else:
                return None
        else:
            return None
    return values[0] if len(values) == 1 else None


def _metric_value(detail: dict[str, Any], unit: str) -> int | float | bool | None:
    data = detail.get("data")
    if not isinstance(data, dict):
        return None
    value = data.get("value")
    if unit == "boolean":
        return value if isinstance(value, bool) else None
    if unit in {"count", "minutes"}:
        return (
            value
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0
            else None
        )
    if unit in {"percent", "provider_score"}:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        numeric = float(value)
        if not math.isfinite(numeric) or numeric < 0:
            return None
        if unit == "percent" and numeric > 100:
            return None
        return numeric
    return None


def _player_lens(
    fixture_id: int,
    home_team_id: int,
    away_team_id: int,
    competition: Any,
    token: str,
    fetcher: Fetcher,
) -> tuple[dict[str, Any], str | None]:
    if competition not in TOP_FIVE_COMPETITIONS:
        return _unavailable(SportmonksError(
            "competition_not_supported",
            "Player Lens is limited to Golavo's five supported domestic leagues",
            status=404,
        )), None
    try:
        payload, digest = fetcher(
            f"/v3/football/fixtures/{fixture_id}"
            "?include=lineups.details.type;metadata.type"
            f"&filters=lineupDetailTypes:{PLAYER_METRIC_FILTER}",
            token,
        )
        fixture = payload.get("data")
        if not isinstance(fixture, dict) or fixture.get("id") != fixture_id:
            raise SportmonksError(
                "fixture_identity_mismatch",
                "Sportmonks player data did not repeat the selected fixture id",
                status=502,
            )
        rows = fixture.get("lineups")
        if not isinstance(rows, list):
            raise SportmonksError(
                "player_data_unavailable",
                "Sportmonks returned no lineup collection for this fixture",
                status=404,
            )
        if len(rows) > MAX_LINEUP_PLAYERS:
            raise SportmonksError(
                "malformed_response",
                "Sportmonks player data exceeded the safe lineup limit",
                status=502,
            )
        players: list[dict[str, Any]] = []
        seen_player_ids: set[int] = set()
        seen_lineup_ids: set[int] = set()
        for row in rows:
            if not isinstance(row, dict):
                continue
            player_id = row.get("player_id")
            team_id = row.get("team_id")
            lineup_id = row.get("id")
            player_name = row.get("player_name")
            participation_type = row.get("type_id")
            if (
                row.get("fixture_id") != fixture_id
                or not isinstance(player_id, int)
                or isinstance(player_id, bool)
                or not isinstance(team_id, int)
                or isinstance(team_id, bool)
                or team_id not in {home_team_id, away_team_id}
                or not isinstance(lineup_id, int)
                or isinstance(lineup_id, bool)
                or not isinstance(player_name, str)
                or not player_name.strip()
                or len(player_name) > 160
                or participation_type not in {11, 12}
            ):
                continue
            if player_id in seen_player_ids or lineup_id in seen_lineup_ids:
                raise SportmonksError(
                    "player_identity_ambiguous",
                    "Sportmonks repeated a player or lineup identity within one fixture",
                    status=502,
                )
            seen_player_ids.add(player_id)
            seen_lineup_ids.add(lineup_id)
            details = row.get("details")
            metrics: list[dict[str, Any]] = []
            if isinstance(details, list):
                if len(details) > MAX_PLAYER_METRICS:
                    raise SportmonksError(
                        "malformed_response",
                        "Sportmonks player statistics exceeded the safe metric limit",
                        status=502,
                    )
                seen_types: set[int] = set()
                for detail in details:
                    if not isinstance(detail, dict):
                        continue
                    type_id = detail.get("type_id")
                    kind = detail.get("type")
                    if (
                        isinstance(type_id, int)
                        and not isinstance(type_id, bool)
                        and type_id in seen_types
                    ):
                        raise SportmonksError(
                            "player_metric_ambiguous",
                            "Sportmonks repeated a player metric identity",
                            status=502,
                        )
                    identity_mismatch = (
                        detail.get("fixture_id") != fixture_id
                        or detail.get("player_id") != player_id
                        or detail.get("team_id") != team_id
                        or detail.get("lineup_id") != lineup_id
                    )
                    if identity_mismatch:
                        continue
                    if (
                        not isinstance(type_id, int)
                        or isinstance(type_id, bool)
                        or not isinstance(kind, dict)
                    ):
                        raise SportmonksError(
                            "player_metric_schema_drift",
                            "Sportmonks returned an untyped player metric",
                            status=502,
                        )
                    schema = PLAYER_METRIC_SCHEMA.get(type_id)
                    if schema is None:
                        raise SportmonksError(
                            "player_metric_schema_drift",
                            "Sportmonks returned a player metric outside Golavo's pinned schema",
                            status=502,
                        )
                    developer_name, label, unit = schema
                    if kind.get("id") != type_id or kind.get("developer_name") != developer_name:
                        raise SportmonksError(
                            "player_metric_schema_drift",
                            "Sportmonks player metric metadata no longer matches "
                            "Golavo's pinned schema",
                            status=502,
                        )
                    value = _metric_value(detail, unit)
                    if value is None:
                        raise SportmonksError(
                            "player_metric_schema_drift",
                            "Sportmonks returned a player metric with an invalid value or unit",
                            status=502,
                        )
                    seen_types.add(type_id)
                    metrics.append({
                        "type_id": type_id,
                        "developer_name": developer_name,
                        "label": label,
                        "group": kind.get("stat_group")
                        if isinstance(kind.get("stat_group"), str) else None,
                        "unit": unit,
                        "value": value,
                    })
            players.append({
                "lineup_id": lineup_id,
                "player_id": player_id,
                "team_id": team_id,
                "name": player_name.strip(),
                "jersey_number": row.get("jersey_number")
                if isinstance(row.get("jersey_number"), int)
                and not isinstance(row.get("jersey_number"), bool) else None,
                "position_id": row.get("position_id")
                if isinstance(row.get("position_id"), int)
                and not isinstance(row.get("position_id"), bool) else None,
                "participation": "starter" if participation_type == 11 else "substitute",
                "metrics": sorted(
                    metrics,
                    key=lambda item: (item["label"].casefold(), item["type_id"]),
                ),
            })
        if not players:
            raise SportmonksError(
                "player_data_unavailable",
                "Sportmonks returned no identity-safe player rows for this fixture",
                status=404,
            )
        players.sort(key=lambda item: (
            0 if item["team_id"] == home_team_id else 1,
            0 if item["participation"] == "starter" else 1,
            item["name"].casefold(),
            item["player_id"],
        ))
        confirmed = _lineup_confirmed(fixture)
        return {
            "status": "available",
            "lineup_state": (
                "confirmed"
                if confirmed is True
                else "predicted"
                if confirmed is False
                else "unverified"
            ),
            "players": players,
            "coverage": {
                "player_count": len(players),
                "players_with_metrics": sum(bool(player["metrics"]) for player in players),
                "missing_stat_is_zero": False,
            },
        }, digest
    except SportmonksError as exc:
        if exc.code in {
            "credential_rejected",
            "plan_missing",
            "rate_limited",
            "provider_unavailable",
            "request_cancelled",
        }:
            raise
        return _unavailable(exc), None


def _fetch_outside_signals(
    match: dict[str, Any], *, fetcher: Fetcher | None = None, now_utc: datetime | None = None
) -> dict[str, Any]:
    settings = load_settings()
    if not settings["enabled"]:
        raise SportmonksError(
            "provider_disabled", "Enable Sportmonks in Settings before fetching", status=409
        )
    if settings["terms_acceptance_version"] != TERMS_ACCEPTANCE_VERSION:
        raise SportmonksError(
            "terms_review_required",
            "Review the current Sportmonks disclosure in Settings",
            status=409,
        )
    if (
        settings["capabilities"] == ["player_lens"]
        and match.get("competition") not in TOP_FIVE_COMPETITIONS
    ):
        raise SportmonksError(
            "competition_not_supported",
            "Player Lens is limited to Golavo's five supported domestic leagues",
            status=404,
        )
    token, _source = load_api_token()
    if token is None:
        raise SportmonksError(
            "credential_missing", "Add your Sportmonks API token in Settings", status=409
        )
    transport = _cancellable_transport(fetcher or _request_json)
    fixture, fixture_hashes, match_method = _find_fixture(match, token, transport)
    fixture_id = int(fixture["id"])
    hashes: dict[str, Any] = {"fixture_pages": fixture_hashes}
    prediction: dict[str, Any] = {
        "status": "disabled",
        "reason_code": "capability_disabled",
        "message": "External predictions are disabled in Settings",
        "retryable": False,
    }
    odds: dict[str, Any] = {
        "status": "disabled",
        "reason_code": "capability_disabled",
        "message": "External odds are disabled in Settings",
        "retryable": False,
    }
    player_lens: dict[str, Any] = {
        "status": "disabled",
        "reason_code": "capability_disabled",
        "message": "Player Lens is disabled in Settings",
        "retryable": False,
    }
    if "external_prediction" in settings["capabilities"]:
        prediction, digest = _prediction(fixture_id, token, transport)
        hashes["prediction"] = digest
    if "external_odds" in settings["capabilities"]:
        odds, digest = _odds(fixture_id, token, transport)
        hashes["odds"] = digest
    home = _participant(fixture, "home") or {}
    away = _participant(fixture, "away") or {}
    league_id = fixture.get("league_id")
    season_id = fixture.get("season_id")
    if "player_lens" in settings["capabilities"]:
        player_lens, digest = _player_lens(
            fixture_id,
            int(home["id"]),
            int(away["id"]),
            match.get("competition"),
            token,
            transport,
        )
        hashes["player_lens"] = digest
    capability_results = {
        "external_prediction": prediction,
        "external_odds": odds,
        "player_lens": player_lens,
    }
    states = {
        capability_results[capability]["status"]
        for capability in settings["capabilities"]
    }
    overall = (
        "available"
        if states == {"available"}
        else "partial"
        if "available" in states
        else "unavailable"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": overall,
        "label": "Outside signals — not a Golavo forecast.",
        "provider": {
            "source_id": SOURCE_ID,
            "name": SOURCE_NAME,
            "docs_url": DOCS_URL,
            "terms_url": TERMS_URL,
        },
        "identity": {
            "golavo_match_id": match.get("match_id"),
            "provider_fixture_id": fixture_id,
            "provider_home_team_id": home.get("id"),
            "provider_away_team_id": away.get("id"),
            "provider_home_team": home.get("name"),
            "provider_away_team": away.get("name"),
            "provider_league_id": league_id
            if isinstance(league_id, int) and not isinstance(league_id, bool) else None,
            "provider_league": fixture.get("league", {}).get("name")
            if isinstance(fixture.get("league"), dict) else None,
            "provider_season_id": season_id
            if isinstance(season_id, int) and not isinstance(season_id, bool) else None,
            "provider_season": fixture.get("season", {}).get("name")
            if isinstance(fixture.get("season"), dict) else None,
            "provider_kickoff_utc": (
                _utc_z(datetime.fromtimestamp(fixture["starting_at_timestamp"], UTC))
                if isinstance(fixture.get("starting_at_timestamp"), int)
                and not isinstance(fixture.get("starting_at_timestamp"), bool)
                else None
            ),
            "match_method": match_method,
        },
        "prediction": prediction,
        "odds": odds,
        "player_lens": player_lens,
        "provenance": {
            "fetched_at_utc": _utc_z(now_utc),
            "terms_acceptance_version": TERMS_ACCEPTANCE_VERSION,
            "raw_response_sha256": hashes,
            "raw_response_storage": "not_persisted",
            "model_input": False,
        },
    }


def fetch_outside_signals(
    match: dict[str, Any], *, fetcher: Fetcher | None = None, now_utc: datetime | None = None
) -> dict[str, Any]:
    cancel_event = threading.Event()
    with _request_scope(cancel_event):
        return _fetch_outside_signals(match, fetcher=fetcher, now_utc=now_utc)
