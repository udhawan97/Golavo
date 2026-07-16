"""On-demand MatchAnalysis over the frozen index (read-only, leak-safe).

Wraps ``golavo_core.analysis.build_match_analysis`` for the API: it resolves a
match id in the committed index, scopes history to the fixture's own source (so a
shared team string cannot merge a club's form into an international fixture — the
same discipline the on-demand notebook uses), and returns a Replay (completed) or
Preview (scheduled) envelope. It never writes and never seals; the leak-safe
``kickoff - 1s`` cutoff lives in the core engine.

Results are memoised per ``(match_id, index-object-identity)``. The index frame is
immutable within a process (``matches._load_index`` caches it), so keying on its
object id means a runtime refresh — which rebuilds the frame — transparently
invalidates every cached analysis with no explicit cache-busting.
"""

from __future__ import annotations

import hashlib
import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from golavo_server import matches, runtime

# Bounded per-process memo (L1). ~64 fits is plenty for a session's cockpit
# browsing; the FIFO bound keeps a long session from growing without limit.
_CACHE: dict[tuple[str, int], dict[str, Any]] = {}
_CACHE_ORDER: list[tuple[str, int]] = []
_CACHE_MAX = 128

# L2 disk cache: content-addressed by (match_id, index fingerprint, schema
# version), so it survives restarts and self-invalidates on any index change. It
# is an ACCELERATOR — every read/write swallows I/O errors and falls back to
# recompute; it is never a dependency.
_DISK_MAX = 512
_CACHE_SCHEMA_VERSION = "0.1.0"


def _remember(key: tuple[str, int], value: dict[str, Any]) -> None:
    _CACHE[key] = value
    _CACHE_ORDER.append(key)
    while len(_CACHE_ORDER) > _CACHE_MAX:
        stale = _CACHE_ORDER.pop(0)
        _CACHE.pop(stale, None)


def reset_cache() -> None:
    """Drop the in-process analysis memo (tests / after an index repoint).

    Only clears L1: the disk cache is content-addressed by the index fingerprint,
    so a repointed index simply lands on different keys and never serves stale
    bytes.
    """
    _CACHE.clear()
    _CACHE_ORDER.clear()


def _analysis_schema_version() -> str:
    from golavo_core.analysis import ANALYSIS_SCHEMA_VERSION

    return ANALYSIS_SCHEMA_VERSION


@lru_cache(maxsize=1)
def _analysis_validator() -> Any:
    from golavo_core.resources import match_analysis_schema_path
    from jsonschema import Draft202012Validator, FormatChecker

    schema = json.loads(match_analysis_schema_path().read_text(encoding="utf-8"))
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _disk_path(match_id: str) -> Path | None:
    root = runtime.analysis_cache_dir()
    if root is None:
        return None
    token = f"{match_id}|{matches.index_fingerprint()}|{_analysis_schema_version()}"
    key = hashlib.sha256(token.encode("utf-8")).hexdigest()[:20]
    return root / f"an_{key}.json"


def _canonical_bytes(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def _discard(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass


def _disk_read(path: Path, match_id: str) -> dict[str, Any] | None:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(obj, dict):
        _discard(path)
        return None
    envelope = obj.get("envelope")
    want = _analysis_schema_version()
    expected = {
        "cache_schema_version": _CACHE_SCHEMA_VERSION,
        "match_id": match_id,
        "index_fingerprint": matches.index_fingerprint(),
        "analysis_schema_version": want,
    }
    if any(obj.get(key) != value for key, value in expected.items()) or not isinstance(
        envelope, dict
    ):
        _discard(path)
        return None
    digest = hashlib.sha256(_canonical_bytes(envelope)).hexdigest()
    if obj.get("payload_sha256") != digest:
        _discard(path)
        return None
    analysis = envelope.get("analysis")
    if envelope.get("available") is True:
        if not isinstance(analysis, dict) or analysis.get("schema_version") != want:
            _discard(path)
            return None
        if analysis.get("match", {}).get("match_id") != match_id:
            _discard(path)
            return None
        try:
            _analysis_validator().validate(analysis)
        except Exception:  # noqa: BLE001 -- a cache is untrusted and optional
            _discard(path)
            return None
    elif envelope.get("available") is not False or analysis is not None:
        _discard(path)
        return None
    return envelope


def _disk_write(path: Path, match_id: str, envelope: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        record = {
            "cache_schema_version": _CACHE_SCHEMA_VERSION,
            "match_id": match_id,
            "index_fingerprint": matches.index_fingerprint(),
            "analysis_schema_version": _analysis_schema_version(),
            "payload_sha256": hashlib.sha256(_canonical_bytes(envelope)).hexdigest(),
            "envelope": envelope,
        }
        tmp.write_bytes(_canonical_bytes(record) + b"\n")
        os.replace(tmp, path)  # atomic
        _prune(path.parent)
    except OSError:
        pass  # the cache is an accelerator, never a dependency


def _prune(root: Path) -> None:
    try:
        files = sorted(root.glob("an_*.json"), key=lambda p: p.stat().st_mtime)
    except OSError:
        return
    for stale in files[:-_DISK_MAX] if len(files) > _DISK_MAX else []:
        try:
            stale.unlink()
        except OSError:
            pass


def match_analysis(match_id: str) -> dict[str, Any] | None:
    """MatchAnalysis envelope for one indexed match; None if the id is unknown.

    Returns ``{"available": True, "analysis": {...}}`` for a fixture we can model,
    or ``{"available": False, "reason": ...}`` when the fixture has no kickoff or
    the fit fails — always failing closed to an honest envelope rather than a 500.
    """
    from golavo_core.analysis import AnalysisUnavailable, build_match_analysis

    frame = matches._load_index()
    key = (str(match_id), id(frame))
    cached = _CACHE.get(key)
    if cached is not None:
        return cached

    # L2: content-addressed disk cache (desktop only). A hit skips five model fits.
    disk_path = _disk_path(str(match_id))
    if disk_path is not None:
        disk = _disk_read(disk_path, str(match_id))
        if disk is not None:
            _remember(key, disk)
            return disk

    sel = frame.loc[frame["match_id"].astype("string") == str(match_id)]
    if sel.empty:
        return None
    row = sel.iloc[0]

    source_id = matches._str_or_none(row["source_id"])
    source_kind = matches._str_or_none(row["source_kind"])
    competition = matches._str_or_none(row["competition"])
    scoped = frame
    if source_id is not None:
        scoped = frame.loc[frame["source_id"].astype("string") == source_id]
    if source_kind == "club" and competition is not None:
        scoped = scoped.loc[scoped["competition"].astype("string") == competition]

    match_row = {
        "match_id": str(row["match_id"]),
        "kickoff_utc": row["kickoff_utc"],
        "home_team": matches._str_or_none(row["home_team"]),
        "away_team": matches._str_or_none(row["away_team"]),
        "home_score": matches._int_or_none(row["home_score"]),
        "away_score": matches._int_or_none(row["away_score"]),
        "is_complete": bool(row["is_complete"]),
        "neutral": bool(matches._bool_or_none(row["neutral"])),
        "competition": competition,
        "source_id": source_id,
    }

    try:
        analysis = build_match_analysis(matches=scoped, match_row=match_row)
    except AnalysisUnavailable as exc:
        # A stable "no kickoff" verdict is safe to cache (memo + disk); a fixture
        # doesn't grow a kickoff mid-session.
        envelope: dict[str, Any] = {"available": False, "reason": str(exc), "analysis": None}
        _remember(key, envelope)
        if disk_path is not None:
            _disk_write(disk_path, str(match_id), envelope)
        return envelope
    except Exception as exc:  # noqa: BLE001 (fail closed; never 500 the cockpit)
        # A transient fit failure is NOT cached — retrying may succeed.
        return {"available": False, "reason": f"analysis failed: {exc}", "analysis": None}

    envelope = {"available": True, "reason": None, "analysis": analysis}
    _remember(key, envelope)
    if disk_path is not None:
        _disk_write(disk_path, str(match_id), envelope)
    return envelope


def warm_home_window(limit: int = 12) -> None:
    """Precompute the council for the most-recent + soonest-upcoming matches.

    Runs in a daemon thread after the index warms, so the first cockpit a user
    opens from the Matchday home is likely already cached (R7 latency mitigation).
    Best-effort: any failure is swallowed — warming must never crash the sidecar.
    """
    try:
        import pandas as pd

        frame = matches._load_index()
        played = frame["is_complete"].astype("boolean").fillna(False).astype(bool)
        ko = pd.to_datetime(frame["kickoff_utc"], utc=True)
        recent = (
            frame.loc[played]
            .assign(_ko=ko.loc[played])
            .sort_values(by=["_ko", "match_id"], ascending=[False, True], kind="mergesort")
            .head(limit)
        )
        today = pd.Timestamp.now(tz="UTC").normalize()
        upcoming = (
            frame.loc[(~played) & (ko >= today)]
            .assign(_ko=ko.loc[(~played) & (ko >= today)])
            .sort_values(by=["_ko", "match_id"], ascending=[True, True], kind="mergesort")
            .head(limit)
        )
        ids = list(recent["match_id"].astype("string")) + list(
            upcoming["match_id"].astype("string")
        )
        for mid in ids:
            try:
                match_analysis(str(mid))
            except Exception:  # noqa: BLE001 (one bad fixture must not stop warming)
                continue
    except Exception:  # noqa: BLE001 (warming is entirely best-effort)
        return
