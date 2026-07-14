"""Durable fantasy-pick state machine over the local Golavo ledger."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from golavo_core.artifacts import _atomic_write_bytes
from golavo_core.picks import (
    PICK_SCHEMA_VERSION,
    canonical_pick_bytes,
    derive_rival_picks,
    football_season,
    outcome_of,
    pick_id,
    pick_payload_sha256,
    score_pick,
    season_summary,
    validate_user_pick,
    verify_pick_integrity,
)

_PICKS_LOCK = threading.Lock()
_SAFE_MATCH_ID = re.compile(r"^[A-Za-z0-9_.-]+$")


class PickError(Exception):
    """Typed pick failure carrying an HTTP status and stable reason code."""

    def __init__(self, status_code: int, reason_code: str, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.reason_code = reason_code
        self.detail = detail


def _now(now_utc: datetime | None) -> datetime:
    return (now_utc or datetime.now(UTC)).astimezone(UTC).replace(microsecond=0)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return (parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)).astimezone(UTC)


def _root(ledger: Path) -> Path:
    return Path(ledger) / "picks"


def _draft_path(ledger: Path, match_id: str) -> Path:
    if not _SAFE_MATCH_ID.fullmatch(str(match_id)):
        raise PickError(404, "match_not_found", "no indexed match with that id")
    return _root(ledger) / "drafts" / f"{match_id}.json"


def _locked_paths(ledger: Path) -> list[Path]:
    root = _root(ledger)
    return sorted(root.glob("pk_*.json")) if root.exists() else []


def _payload_digest(record: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_pick_bytes(record)).hexdigest()


def _append_audit(ledger: Path, *, event: str, record: dict[str, Any], at_utc: str) -> None:
    root = _root(ledger)
    root.mkdir(parents=True, exist_ok=True)
    audit = {
        "event": event,
        "match_id": record["match"]["match_id"],
        "pick_id": record.get("pick_id"),
        "at_utc": at_utc,
        "payload_sha256": record.get("payload_sha256") or _payload_digest(record),
    }
    with (root / "audit.jsonl").open("ab") as stream:
        stream.write(canonical_pick_bytes(audit) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())


def _write_draft(ledger: Path, record: dict[str, Any]) -> None:
    validate_user_pick(record)
    path = _draft_path(ledger, record["match"]["match_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_bytes(path, canonical_pick_bytes(record) + b"\n")


def _load_draft(ledger: Path, match_id: str) -> dict[str, Any] | None:
    path = _draft_path(ledger, match_id)
    if not path.is_file():
        return None
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
        validate_user_pick(record)
    except Exception as exc:  # noqa: BLE001 - corrupt user state fails closed
        raise PickError(500, "integrity_error", "the saved pick draft is corrupt") from exc
    return record


def _load_locked(path: Path) -> dict[str, Any]:
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
        return verify_pick_integrity(record, expected_id=path.stem)
    except Exception as exc:  # noqa: BLE001 - every integrity failure is one verdict
        raise PickError(
            500, "integrity_error", "the locked pick failed integrity verification"
        ) from exc


def _fixture_key_from_record(record: dict[str, Any]) -> tuple[str, str, str]:
    match = record["match"]
    return (match["kickoff_utc"][:10], match["home_norm"], match["away_norm"])


def _row_value(row: Any, key: str) -> Any:
    value = row[key]
    from golavo_server.matches import _isna

    return None if _isna(value) else value


def _find_row(match_id: str) -> Any | None:
    from golavo_server import matches

    frame = matches._load_index()
    rows = frame.loc[frame["match_id"].astype("string") == str(match_id)]
    return None if rows.empty else rows.iloc[0]


def _fallback_row(record: dict[str, Any]) -> Any | None:
    import pandas as pd

    from golavo_server import matches

    frame = matches._load_index()
    date, home_norm, away_norm = _fixture_key_from_record(record)
    dates = pd.to_datetime(frame["kickoff_utc"], utc=True).dt.date.astype("string")
    rows = frame.loc[
        dates.eq(date)
        & frame["home_norm"].astype("string").eq(home_norm)
        & frame["away_norm"].astype("string").eq(away_norm)
    ]
    if rows.empty:
        return None
    return rows.sort_values("match_id", kind="mergesort").iloc[0]


def _current_row(record: dict[str, Any]) -> Any | None:
    row = _find_row(record["match"]["match_id"])
    return row if row is not None else _fallback_row(record)


def _row_iso(row: Any) -> str:
    from golavo_server.matches import _iso_utc

    kickoff = _iso_utc(row["kickoff_utc"])
    if kickoff is None:
        raise PickError(422, "no_kickoff", "this fixture has no usable kickoff time")
    return kickoff


def _effective_lock(record: dict[str, Any], row: Any | None) -> datetime:
    stored = _parse(record["lock_at_utc"])
    if row is None:
        return stored
    return min(stored, _parse(_row_iso(row)))


def _match_snapshot(row: Any) -> dict[str, Any]:
    kickoff = _row_iso(row)
    home = str(_row_value(row, "home_team"))
    away = str(_row_value(row, "away_team"))
    is_day_proxy = str(_row_value(row, "source_kind")) == "international" and kickoff.endswith(
        "T00:00:00Z"
    )
    return {
        "match_id": str(row["match_id"]),
        "kickoff_utc": kickoff,
        "kickoff_time_known": not is_day_proxy,
        "home_team": home,
        "away_team": away,
        "home_norm": str(_row_value(row, "home_norm")),
        "away_norm": str(_row_value(row, "away_norm")),
        "competition": (
            str(_row_value(row, "competition"))
            if _row_value(row, "competition") is not None
            else None
        ),
    }


def _find_locked(ledger: Path, match_id: str) -> tuple[Path, dict[str, Any]] | None:
    fallback: tuple[Path, dict[str, Any]] | None = None
    row = _find_row(match_id)
    row_key = None
    if row is not None:
        row_key = (_row_iso(row)[:10], str(row["home_norm"]), str(row["away_norm"]))
    for path in _locked_paths(ledger):
        try:
            record = _load_locked(path)
        except PickError:
            # Peek only far enough to decide whether this is the requested pick.
            # It is never served unverified; unrelated corrupt entries are skipped.
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                raw_match = raw.get("match", {})
                raw_key = (
                    str(raw_match.get("kickoff_utc", ""))[:10],
                    str(raw_match.get("home_norm", "")),
                    str(raw_match.get("away_norm", "")),
                )
                if raw_match.get("match_id") == match_id or (
                    row_key is not None and raw_key == row_key
                ):
                    raise
            except (OSError, ValueError, AttributeError):
                pass
            continue
        if record["match"]["match_id"] == match_id:
            return path, record
        if row_key is not None and _fixture_key_from_record(record) == row_key:
            fallback = (path, record)
    return fallback


def _sealed_record(draft: dict[str, Any], lock_at: datetime) -> dict[str, Any]:
    record = copy.deepcopy(draft)
    lock_iso = _iso(lock_at)
    record.update(
        {
            "status": "locked",
            "lock_at_utc": lock_iso,
            "locked_at_utc": lock_iso,
            "updated_at_utc": lock_iso,
        }
    )
    stable = copy.deepcopy(record)
    stable.pop("pick_id", None)
    stable.pop("payload_sha256", None)
    record["pick_id"] = pick_id(stable)
    record["payload_sha256"] = pick_payload_sha256(record)
    validate_user_pick(record)
    return record


def _write_locked(ledger: Path, record: dict[str, Any]) -> Path:
    verify_pick_integrity(record)
    root = _root(ledger)
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{record['pick_id']}.json"
    data = canonical_pick_bytes(record) + b"\n"
    if path.exists():
        existing = path.read_bytes()
        if existing != data:
            # A corrupt partial under the same id is repairable; a different valid
            # locked pick under one content address is a genuine collision.
            try:
                _load_locked(path)
            except PickError:
                pass
            else:
                raise PickError(409, "pick_collision", f"immutable pick collision at {path}")
    _atomic_write_bytes(path, data)
    return path


def _freeze(
    ledger: Path,
    draft: dict[str, Any],
    *,
    row: Any | None,
    virtual_on_error: bool,
) -> dict[str, Any]:
    record = _sealed_record(draft, _effective_lock(draft, row))
    try:
        _write_locked(ledger, record)
        _append_audit(ledger, event="pick_locked", record=record, at_utc=record["locked_at_utc"])
        _draft_path(ledger, draft["match"]["match_id"]).unlink(missing_ok=True)
    except OSError:
        if not virtual_on_error:
            raise
    return record


def _view(record: dict[str, Any]) -> dict[str, Any]:
    row = _current_row(record)
    if record["status"] == "draft":
        return {
            "schema_version": PICK_SCHEMA_VERSION,
            "status": "draft",
            "record": record,
            "result": None,
            "scoring": None,
        }
    if row is None:
        return {
            "schema_version": PICK_SCHEMA_VERSION,
            "status": "void",
            "record": record,
            "result": None,
            "scoring": None,
        }
    if not bool(row["is_complete"]):
        return {
            "schema_version": PICK_SCHEMA_VERSION,
            "status": "locked",
            "record": record,
            "result": None,
            "scoring": None,
        }
    result = {
        "home_goals": int(row["home_score"]),
        "away_goals": int(row["away_score"]),
    }
    result["outcome"] = outcome_of(result["home_goals"], result["away_goals"])
    return {
        "schema_version": PICK_SCHEMA_VERSION,
        "status": "scored",
        "record": record,
        "result": result,
        "scoring": score_pick(record, result),
    }


def _validate_goals(home_goals: Any, away_goals: Any) -> tuple[int, int]:
    if (
        isinstance(home_goals, bool)
        or isinstance(away_goals, bool)
        or not isinstance(home_goals, int)
        or not isinstance(away_goals, int)
        or not 0 <= home_goals <= 20
        or not 0 <= away_goals <= 20
    ):
        raise PickError(422, "invalid_score", "home_goals and away_goals must be integers 0..20")
    return home_goals, away_goals


def _analysis_snapshot(match_id: str) -> dict[str, Any]:
    from golavo_server import analysis, matches

    envelope = analysis.match_analysis(match_id)
    payload = envelope.get("analysis") if envelope else None
    if not envelope or not envelope.get("available") or not isinstance(payload, dict):
        raise PickError(
            503,
            "analysis_unavailable",
            "the model council is unavailable, so this pick was not saved",
        )
    payload = copy.deepcopy(payload)
    payload["index_fingerprint"] = matches.index_fingerprint()
    derived = derive_rival_picks(payload)
    if not derived["rivals"]:
        raise PickError(
            503,
            "analysis_unavailable",
            "the model council returned no rivals, so this pick was not saved",
        )
    return derived


def get_pick(
    match_id: str, *, ledger: Path, now_utc: datetime | None = None
) -> dict[str, Any] | None:
    resolved_now = _now(now_utc)
    with _PICKS_LOCK:
        draft = _load_draft(ledger, match_id)
        locked = _find_locked(ledger, match_id)
        if locked is not None:
            # Crash repair: the immutable write won but draft deletion did not.
            _draft_path(ledger, match_id).unlink(missing_ok=True)
            return _view(locked[1])
        if draft is None:
            return None
        row = _current_row(draft)
        if resolved_now >= _effective_lock(draft, row):
            return _view(_freeze(ledger, draft, row=row, virtual_on_error=True))
        return _view(draft)


def save_pick(
    match_id: str,
    home_goals: Any,
    away_goals: Any,
    *,
    ledger: Path,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    home, away = _validate_goals(home_goals, away_goals)
    resolved_now = _now(now_utc)
    with _PICKS_LOCK:
        row = _find_row(match_id)
        if row is None:
            raise PickError(404, "match_not_found", "no indexed match with that id")
        if bool(row["is_complete"]):
            raise PickError(422, "fixture_complete", "this fixture already has a final result")
        if _find_locked(ledger, match_id) is not None:
            raise PickError(409, "pick_locked", "this pick locked at kickoff")

        existing = _load_draft(ledger, match_id)
        current_lock = _parse(_row_iso(row))
        effective_lock = (
            min(_parse(existing["lock_at_utc"]), current_lock) if existing else current_lock
        )
        if resolved_now >= effective_lock:
            if existing is not None:
                _freeze(ledger, existing, row=row, virtual_on_error=True)
            raise PickError(409, "pick_locked", "this pick locked at kickoff")

        derived = _analysis_snapshot(match_id)
        now_iso = _iso(resolved_now)
        record = {
            "schema_version": PICK_SCHEMA_VERSION,
            "pick_id": None,
            "status": "draft",
            "match": existing["match"] if existing else _match_snapshot(row),
            "user_pick": {
                "home_goals": home,
                "away_goals": away,
                "outcome": outcome_of(home, away),
            },
            "rivals": derived["rivals"],
            "analysis_fingerprint": derived["analysis_fingerprint"],
            "created_at_utc": existing["created_at_utc"] if existing else now_iso,
            "updated_at_utc": now_iso,
            "lock_at_utc": _iso(effective_lock),
            "locked_at_utc": None,
            "payload_sha256": None,
        }
        _write_draft(ledger, record)
        _append_audit(ledger, event="pick_saved", record=record, at_utc=now_iso)
        return _view(record)


def delete_pick(match_id: str, *, ledger: Path, now_utc: datetime | None = None) -> bool:
    resolved_now = _now(now_utc)
    with _PICKS_LOCK:
        if _find_locked(ledger, match_id) is not None:
            raise PickError(409, "pick_locked", "this pick locked at kickoff")
        draft = _load_draft(ledger, match_id)
        if draft is None:
            return False
        row = _current_row(draft)
        if resolved_now >= _effective_lock(draft, row):
            _freeze(ledger, draft, row=row, virtual_on_error=True)
            raise PickError(409, "pick_locked", "this pick locked at kickoff")
        _draft_path(ledger, match_id).unlink(missing_ok=True)
        _append_audit(ledger, event="pick_deleted", record=draft, at_utc=_iso(resolved_now))
        return True


def _all_match_ids(ledger: Path) -> list[str]:
    ids: set[str] = set()
    drafts = _root(ledger) / "drafts"
    if drafts.exists():
        ids.update(path.stem for path in drafts.glob("*.json"))
    for path in _locked_paths(ledger):
        try:
            ids.add(_load_locked(path)["match"]["match_id"])
        except PickError:
            continue
    return sorted(ids)


def list_picks(
    *,
    ledger: Path,
    status: str | None = None,
    season: str | None = None,
    limit: int = 50,
    offset: int = 0,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    if status is not None and status not in {"draft", "locked", "scored", "void"}:
        raise PickError(422, "invalid_status", "status must be draft, locked, scored, or void")
    if limit < 1 or limit > 500 or offset < 0:
        raise PickError(422, "invalid_pagination", "limit must be 1..500 and offset must be >= 0")
    views: list[dict[str, Any]] = []
    for match_id in _all_match_ids(ledger):
        try:
            view = get_pick(match_id, ledger=ledger, now_utc=now_utc)
        except PickError as exc:
            if exc.reason_code == "integrity_error":
                continue
            raise
        if view is None or (status is not None and view["status"] != status):
            continue
        if season is not None and football_season(view["record"]["match"]["kickoff_utc"]) != season:
            continue
        views.append(view)
    views.sort(
        key=lambda view: (
            view["record"]["match"]["kickoff_utc"],
            view["record"]["match"]["match_id"],
        ),
        reverse=True,
    )
    total = len(views)
    return {
        "schema_version": PICK_SCHEMA_VERSION,
        "items": views[offset : offset + limit],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def picks_summary(
    *, ledger: Path, season: str | None = None, now_utc: datetime | None = None
) -> dict[str, Any]:
    listed = list_picks(ledger=ledger, limit=500, now_utc=now_utc)
    return season_summary(listed["items"], season=season)
