"""Read-only match search + on-demand Commentator's Notebook over the frozen index.

Everything here reads the committed, immutable match index (``data/index``) and
never writes. Three honesty properties hold end to end:

* **Search is navigation, not verification.** Attaching a forecast to a match is
  a cheap ``json.loads`` scan of the ledger (no integrity check) — the forecast
  route still recomputes each artifact's identity when it actually serves it.
* **Samples can never masquerade as real seals.** The caller passes the real
  ledger dir (``ARTIFACT_DIR``); we scan exactly that, so a synthetic sample id
  can never attach to a real fixture.
* **On-demand notebooks cannot leak the future.** A notebook computed on the fly
  uses ``as_of = kickoff - 1s`` — the same conservative cutoff ``seal_forecast``
  uses — so the fixture's own result and every later match are excluded.

pandas/pyarrow are imported INSIDE functions to keep the frozen sidecar's boot
(and ``/health`` readiness) fast; see ``main.py``'s import note.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from golavo_core import resources

# The frozen UI contract (Workstream D) pins these envelopes at 0.2.0.
SCHEMA_VERSION = "0.2.0"

def _resolve_index_paths() -> dict[str, Path]:
    """The refreshed index + side tables when a runtime refresh has produced them,
    else the committed read-only bundle.

    All-or-nothing on the refreshed *index*: a runtime refresh writes the Parquet,
    its side tables and the alias map together, so gating on the index alone can
    never mix fresh rows with a stale alias map. In source/CI mode there is no
    refresh dir, so this always returns the bundle (and existing tests that repoint
    the globals directly are unaffected).
    """
    from golavo_server import runtime  # local: avoid an import cycle at load

    refreshed = runtime.refresh_dir()
    if refreshed is not None and (refreshed / "matches_index.parquet").exists():
        return {
            "index": refreshed / "matches_index.parquet",
            "meta": refreshed / "matches_index.meta.json",
            "goalscorers": refreshed / "goalscorers.parquet",
            "shootouts": refreshed / "shootouts.parquet",
            "aliases": refreshed / "aliases.json",
        }
    return {
        "index": Path(resources.match_index_path()),
        "meta": Path(resources.match_index_meta_path()),
        "goalscorers": Path(resources.match_index_goalscorers_path()),
        "shootouts": Path(resources.match_index_shootouts_path()),
        "aliases": Path(resources.match_index_aliases_path()),
    }


# Module globals so tests can point them at a tiny fixture index (mirrors the
# ARTIFACT_DIR pattern in main.py). The index is immutable within a process
# (barring an explicit refresh), so it is loaded once and cached.
_paths = _resolve_index_paths()
INDEX_PATH = _paths["index"]
INDEX_META_PATH = _paths["meta"]
GOALSCORERS_PATH = _paths["goalscorers"]
SHOOTOUTS_PATH = _paths["shootouts"]
ALIASES_PATH = _paths["aliases"]

_CACHE: Any = None  # the loaded index DataFrame; reset_cache() clears it

# Advisory warm-up state for the UI's staged splash / warming card. Written only
# from _load_index(); dict-key writes are atomic under the GIL, so no lock is
# needed for this coarse, read-mostly hint. index_status() reports it and NEVER
# triggers the (slow) load itself, so /api/v1/status answers in microseconds even
# mid-warmup.
_WARM: dict[str, Any] = {"state": "cold", "since_utc": None, "error": None}
_META_ROWS: Any = "unread"  # memoized row_count from meta.json: "unread" | int | None


def repoint_to_refreshed() -> None:
    """Swing the module at the refreshed index and drop the cache.

    Called after a successful runtime refresh so the next search / notebook reads
    the fresh bytes. Idempotent, and a no-op when no refresh dir is present.
    """
    global INDEX_PATH, INDEX_META_PATH, GOALSCORERS_PATH, SHOOTOUTS_PATH, ALIASES_PATH
    p = _resolve_index_paths()
    INDEX_PATH, INDEX_META_PATH = p["index"], p["meta"]
    GOALSCORERS_PATH = p["goalscorers"]
    SHOOTOUTS_PATH = p["shootouts"]
    ALIASES_PATH = p["aliases"]
    reset_cache()


class MatchIndexUnavailable(Exception):
    """The committed match index is missing or unreadable.

    The search surface fails closed with a 503 rather than serving a half-built
    page from a corrupt or absent index.
    """


def reset_cache() -> None:
    """Drop the cached index frame (tests call this after repointing INDEX_PATH)."""
    global _CACHE, _META_ROWS
    _CACHE = None
    _META_ROWS = "unread"
    _WARM["state"] = "cold"
    _WARM["since_utc"] = None
    _WARM["error"] = None


def _load_index() -> Any:
    """Load and cache the frozen match index, or raise MatchIndexUnavailable.

    Lazy on purpose: pandas/pyarrow cost ~25s to import from the frozen bundle,
    so the first search pays it (the sidecar warms it in the background) while
    /health and the forecast surface stay light. Drives the advisory ``_WARM``
    state machine (cold -> warming -> ready|error) so the UI splash can show
    honest, real-stage progress instead of a pure fake curve.
    """
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    if _WARM["state"] == "cold":
        _WARM["state"] = "warming"
        _WARM["since_utc"] = datetime.now(timezone.utc).isoformat()
    import pandas as pd

    path = Path(INDEX_PATH)
    if not path.exists():
        _WARM["state"] = "error"
        _WARM["error"] = f"match index not found at {path}"
        raise MatchIndexUnavailable(f"match index not found at {path}")
    try:
        frame = pd.read_parquet(path)
    except Exception as exc:  # noqa: BLE001 (any read/parse failure => unavailable)
        _WARM["state"] = "error"
        _WARM["error"] = f"match index unreadable: {exc}"
        raise MatchIndexUnavailable(f"match index unreadable: {exc}") from exc
    _CACHE = frame
    _WARM["state"] = "ready"
    return frame


def _meta_row_count() -> int | None:
    """Row count from the index meta.json, memoized. Cheap: a small JSON read, no
    pandas/pyarrow — safe to call during warmup. Any failure -> None."""
    global _META_ROWS
    if _META_ROWS != "unread":
        return _META_ROWS
    import json

    try:
        meta = json.loads(Path(INDEX_META_PATH).read_text(encoding="utf-8"))
        value = meta.get("row_count")
        _META_ROWS = int(value) if value is not None else None
    except Exception:  # noqa: BLE001 (missing/corrupt meta -> unknown count)
        _META_ROWS = None
    return _META_ROWS


def index_status() -> dict[str, Any]:
    """Live warm-up status for the UI. Reports only; never triggers the load."""
    ready = _CACHE is not None
    return {
        "index_ready": ready,
        "index_state": "ready" if ready else _WARM["state"],
        "index_rows": _meta_row_count(),
        "warming_since": _WARM["since_utc"],
    }


def _normalize(text: Any) -> str:
    """Fold a query to the index's search key: NFKD -> drop combining -> casefold.

    Matches ``golavo_core.ingest.match_index.normalize`` exactly, so a query need
    not reproduce diacritics to hit ``home_norm``/``away_norm`` (already folded).
    """
    import unicodedata

    decomposed = unicodedata.normalize("NFKD", str(text))
    without_marks = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return without_marks.casefold().strip()


def _load_aliases() -> dict[str, list[str]]:
    """Former-name -> canonical display names map (keys already normalized)."""
    import json

    try:
        raw = json.loads(Path(ALIASES_PATH).read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _isna(value: Any) -> bool:
    import pandas as pd

    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _iso_utc(value: Any) -> str | None:
    """A pandas timestamp -> UTC ISO 8601 with a trailing ``Z`` (NaT -> None)."""
    if value is None or _isna(value):
        return None
    import pandas as pd

    ts = pd.Timestamp(value)
    ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
    return ts.isoformat().replace("+00:00", "Z")


def _str_or_none(value: Any) -> str | None:
    return None if value is None or _isna(value) else str(value)


def _int_or_none(value: Any) -> int | None:
    return None if value is None or _isna(value) else int(value)


def _bool_or_none(value: Any) -> bool | None:
    return None if value is None or _isna(value) else bool(value)


def _summary(obj: dict[str, Any]) -> dict[str, Any]:
    """The compact forecast card the UI shows next to a match."""
    forecast = obj.get("forecast")
    forecast = forecast if isinstance(forecast, dict) else {}
    return {
        "artifact_id": obj["artifact_id"],
        "status": obj.get("status"),
        "horizon": forecast.get("horizon"),
        "sealed_at_utc": forecast.get("sealed_at_utc"),
    }


def artifact_links(
    forecasts_dir: Path,
) -> tuple[dict[str, list[dict[str, Any]]], dict[tuple[str, str, str], list[dict[str, Any]]]]:
    """Scan a LEDGER directory of ``fa_*.json`` and index them for match linking.

    Deliberately cheap: a plain ``json.loads`` with NO integrity verification —
    linking is navigation, and the forecast route re-verifies each artifact when
    it actually serves it. Corrupt files are skipped. The caller passes the real
    ledger dir (never the sample fallback) so synthetic sample ids can never
    attach to a real match. Returns ``(by_match_id, by_fixture)`` where a fixture
    key is ``(date_str, home_norm, away_norm)``.
    """
    import json

    by_match_id: dict[str, list[dict[str, Any]]] = {}
    by_fixture: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    folder = Path(forecasts_dir)
    if not folder.exists():
        return by_match_id, by_fixture

    for path in sorted(folder.glob("fa_*.json")):
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        if not isinstance(obj, dict) or "artifact_id" not in obj:
            continue
        match = obj.get("match")
        if not isinstance(match, dict):
            continue
        summary = _summary(obj)

        match_id = match.get("match_id")
        if match_id is not None:
            by_match_id.setdefault(str(match_id), []).append(summary)

        home = match.get("home_team")
        away = match.get("away_team")
        kickoff = match.get("kickoff_utc")
        if home is not None and away is not None and kickoff is not None:
            key = (str(kickoff)[:10], _normalize(home), _normalize(away))
            by_fixture.setdefault(key, []).append(summary)

    return by_match_id, by_fixture


def _links_for_row(
    row: Any,
    by_match_id: dict[str, list[dict[str, Any]]],
    by_fixture: dict[tuple[str, str, str], list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], str | None]:
    """Forecasts attached to one index row, and HOW they were linked.

    match_id is authoritative; a fixture (date + normalized teams) match is the
    fallback for a forecast sealed against a differently-keyed snapshot.
    """
    import pandas as pd

    match_id = str(row["match_id"])
    if match_id in by_match_id:
        return by_match_id[match_id], "match_id"

    date_value = row["date"]
    if not _isna(date_value):
        date_str = pd.Timestamp(date_value).date().isoformat()
        key = (date_str, str(row["home_norm"]), str(row["away_norm"]))
        if key in by_fixture:
            return by_fixture[key], "fixture"
    return [], None


def _row_to_dict(
    row: Any,
    by_match_id: dict[str, list[dict[str, Any]]],
    by_fixture: dict[tuple[str, str, str], list[dict[str, Any]]],
) -> dict[str, Any]:
    """One index row -> the frozen MatchRow shape, JSON-clean (NA/NaT -> null)."""
    forecasts, _linked_by = _links_for_row(row, by_match_id, by_fixture)
    return {
        "match_id": str(row["match_id"]),
        "kickoff_utc": _iso_utc(row["kickoff_utc"]),
        "home_team": _str_or_none(row["home_team"]),
        "away_team": _str_or_none(row["away_team"]),
        "home_score": _int_or_none(row["home_score"]),
        "away_score": _int_or_none(row["away_score"]),
        "competition": _str_or_none(row["competition"]),
        "country": _str_or_none(row["country"]),
        "city": _str_or_none(row["city"]),
        "neutral": _bool_or_none(row["neutral"]),
        "is_complete": bool(row["is_complete"]),
        "source_kind": _str_or_none(row["source_kind"]),
        "source_id": _str_or_none(row["source_id"]),
        "forecasts": forecasts,
    }


def search_matches(
    q: str,
    competition: str | None = None,
    status: str | None = None,
    limit: int = 25,
    offset: int = 0,
    *,
    forecasts_dir: Path,
) -> dict[str, Any]:
    """Substring + alias search over the frozen index, newest first within rank.

    Only the query is normalized; the corpus is matched against the pre-folded
    ``home_norm``/``away_norm`` columns. Aliases (former country names) resolve to
    canonical teams. Ranking: a team-name PREFIX hit first, then kickoff desc,
    then match_id — fully deterministic. Forecast links come from the passed
    ledger dir only.
    """
    import pandas as pd

    frame = _load_index()
    nq = _normalize(q)
    limit = max(1, min(int(limit), 100))
    offset = max(0, int(offset))

    home_norm = frame["home_norm"].fillna("")
    away_norm = frame["away_norm"].fillna("")
    comp_norm = frame["competition"].fillna("").str.casefold()

    aliases = _load_aliases()

    def _token_mask(token: str) -> Any:
        submask = (
            home_norm.str.contains(token, regex=False)
            | away_norm.str.contains(token, regex=False)
            | comp_norm.str.contains(token, regex=False)
        )
        canonical = aliases.get(token, [])
        if canonical:
            canon_norms = {_normalize(name) for name in canonical}
            submask = submask | home_norm.isin(canon_norms) | away_norm.isin(canon_norms)
        return submask

    # Tokenize on whitespace and AND the per-token matches, so a multi-word query
    # like "argentina switzerland" requires BOTH terms to appear (in either team or
    # the competition) instead of matching the whole string as one substring — which
    # found nothing, because no single field literally contains "argentina switzerland".
    # A single-token query reduces to the old behaviour exactly.
    tokens = nq.split()
    lead = tokens[0] if tokens else nq
    if not tokens:
        mask = pd.Series(False, index=frame.index)
    else:
        mask = _token_mask(tokens[0])
        for token in tokens[1:]:
            mask = mask & _token_mask(token)

    # Multi-word former-name aliases (e.g. "soviet union" -> Russia) cannot be hit
    # token-by-token, so also resolve the WHOLE query as an alias key and OR that in.
    whole_alias = aliases.get(nq, [])
    if whole_alias:
        canon_norms = {_normalize(name) for name in whole_alias}
        mask = mask | home_norm.isin(canon_norms) | away_norm.isin(canon_norms)

    sel = frame.loc[mask]

    if competition:
        sel = sel.loc[sel["competition"] == competition]

    played = sel["is_complete"].astype("boolean").fillna(False).astype(bool)
    if status == "played":
        sel = sel.loc[played]
    elif status == "upcoming":
        # kickoff is a 00:00 UTC day proxy, so compare against the START of today,
        # not `now` — otherwise a fixture drops out of "upcoming" at UTC midnight on
        # its own match day (kickoff 00:00 < now), exactly when interest peaks.
        today = pd.Timestamp.now(tz="UTC").normalize()
        kickoff = pd.to_datetime(sel["kickoff_utc"], utc=True)
        sel = sel.loc[(~played) & (kickoff >= today)]

    total = int(len(sel))

    sel = sel.copy()
    h = sel["home_norm"].fillna("")
    a = sel["away_norm"].fillna("")
    # False sorts before True (ascending), so a leading-token prefix hit leads.
    sel["_not_prefix"] = ~(h.str.startswith(lead) | a.str.startswith(lead))
    sel["_ko"] = pd.to_datetime(sel["kickoff_utc"], utc=True)
    sel = sel.sort_values(
        by=["_not_prefix", "_ko", "match_id"],
        ascending=[True, False, True],
        kind="mergesort",
    )

    page = sel.iloc[offset : offset + limit]
    by_match_id, by_fixture = artifact_links(Path(forecasts_dir))
    matches = [_row_to_dict(row, by_match_id, by_fixture) for _, row in page.iterrows()]

    return {
        "schema_version": SCHEMA_VERSION,
        "query": q,
        "total": total,
        "limit": limit,
        "offset": offset,
        "matches": matches,
    }


def get_match(match_id: str, *, forecasts_dir: Path) -> dict[str, Any] | None:
    """One match by id -> MatchDetailResponse, or None if absent (route -> 404)."""
    frame = _load_index()
    sel = frame.loc[frame["match_id"].astype("string") == str(match_id)]
    if sel.empty:
        return None
    row = sel.iloc[0]
    by_match_id, by_fixture = artifact_links(Path(forecasts_dir))
    match = _row_to_dict(row, by_match_id, by_fixture)
    _forecasts, linked_by = _links_for_row(row, by_match_id, by_fixture)
    return {"schema_version": SCHEMA_VERSION, "match": match, "linked_by": linked_by}


def recent_matches(
    limit: int = 24,
    *,
    competition: str | None = None,
    source_kind: str | None = None,
    forecasts_dir: Path,
) -> dict[str, Any]:
    """The Games home rails: upcoming fixtures and the most recent results.

    ``upcoming`` = scheduled rows (no result) with a kickoff at or after the start
    of today, soonest first; ``recent`` = completed rows, newest first. Both are
    capped at ``limit`` and may be narrowed to one ``competition`` or one
    ``source_kind`` (e.g. all internationals). Pure navigation over the frozen
    index — never a forecast, never a computed number. When no forward fixtures
    exist in the snapshot the ``upcoming`` rail is honestly empty and the recent
    rail still fills.
    """
    import pandas as pd

    frame = _load_index()
    limit = max(1, min(int(limit), 100))
    if competition:
        frame = frame.loc[frame["competition"] == competition]
    if source_kind:
        frame = frame.loc[frame["source_kind"] == source_kind]

    played = frame["is_complete"].astype("boolean").fillna(False).astype(bool)
    ko = pd.to_datetime(frame["kickoff_utc"], utc=True)
    today = pd.Timestamp.now(tz="UTC").normalize()

    upcoming_sel = (
        frame.loc[(~played) & (ko >= today)]
        .assign(_ko=ko.loc[(~played) & (ko >= today)])
        .sort_values(by=["_ko", "match_id"], ascending=[True, True], kind="mergesort")
        .head(limit)
    )
    recent_sel = (
        frame.loc[played]
        .assign(_ko=ko.loc[played])
        .sort_values(by=["_ko", "match_id"], ascending=[False, True], kind="mergesort")
        .head(limit)
    )

    by_match_id, by_fixture = artifact_links(Path(forecasts_dir))

    def _rows(frame: Any) -> list[dict[str, Any]]:
        return [_row_to_dict(row, by_match_id, by_fixture) for _, row in frame.iterrows()]

    return {
        "schema_version": SCHEMA_VERSION,
        "upcoming": _rows(upcoming_sel),
        "recent": _rows(recent_sel),
    }


WINDOW_DAYS = {"week": 7, "month": 30}


def matches_window(
    window: str,
    limit: int = 200,
    *,
    forecasts_dir: Path,
) -> dict[str, Any]:
    """The Matchday home: matches within a time window, results-first.

    ``window``:
      * ``week`` / ``month`` — completed results in the 7 / 30 days ENDING at the
        freshest completed kickoff in the index (the "anchor"), not the calendar.
        When the snapshot is fresh the anchor is ~yesterday and this behaves like a
        calendar window; when the bundled snapshot is stale it degrades to "the most
        recent week/month of results in this data" and is never misleadingly empty.
        The UI labels the real range and flags staleness honestly.
      * ``upcoming`` — scheduled rows (no result) with a kickoff at or after the
        start of today, soonest first. Calendar-relative and honestly empty when the
        snapshot holds no forward fixtures.

    Grouping/curation is left to the UI (a product concern). ``competitions`` counts
    and ``total`` are computed over the FULL window, before the ``limit`` page cut,
    so the section headers are honest even when the page is truncated.
    """
    import pandas as pd

    frame = _load_index()
    limit = max(1, min(int(limit), 500))

    played = frame["is_complete"].astype("boolean").fillna(False).astype(bool)
    ko = pd.to_datetime(frame["kickoff_utc"], utc=True)
    today = pd.Timestamp.now(tz="UTC").normalize()

    played_ko = ko.loc[played]
    latest_result = played_ko.max() if not played_ko.empty else None
    latest_result_utc = _iso_utc(latest_result) if latest_result is not None else None

    if window == "upcoming":
        sel = frame.loc[(~played) & (ko >= today)].assign(_ko=ko.loc[(~played) & (ko >= today)])
        sel = sel.sort_values(by=["_ko", "match_id"], ascending=[True, True], kind="mergesort")
        window_start_utc = _iso_utc(today)
        window_end_utc = None
    elif window in WINDOW_DAYS:
        days = WINDOW_DAYS[window]
        if latest_result is None:
            sel = frame.iloc[0:0].assign(_ko=ko.iloc[0:0])
            window_start_utc = window_end_utc = None
        else:
            anchor_day = latest_result.normalize()
            start_day = anchor_day - pd.Timedelta(days=days - 1)
            ko_day = ko.dt.normalize()
            mask = played & (ko_day >= start_day) & (ko_day <= anchor_day)
            sel = frame.loc[mask].assign(_ko=ko.loc[mask])
            sel = sel.sort_values(by=["_ko", "match_id"], ascending=[False, True], kind="mergesort")
            window_start_utc = _iso_utc(start_day)
            window_end_utc = _iso_utc(anchor_day)
    else:  # defensive: the route validates, but never trust the caller blindly
        raise ValueError(f"unknown window: {window!r}")

    total = int(len(sel))
    competitions = _competition_counts(sel)

    page = sel.head(limit)
    by_match_id, by_fixture = artifact_links(Path(forecasts_dir))
    rows = [_row_to_dict(row, by_match_id, by_fixture) for _, row in page.iterrows()]

    return {
        "schema_version": SCHEMA_VERSION,
        "window": window,
        "window_start_utc": window_start_utc,
        "window_end_utc": window_end_utc,
        "latest_result_utc": latest_result_utc,
        "total": total,
        "matches": rows,
        "competitions": competitions,
    }


def _competition_counts(sel: Any) -> list[dict[str, Any]]:
    """(competition, source_kind, n_matches) over a selection, deterministically
    ordered (source_kind then competition). Empty selection -> empty list."""
    if len(sel) == 0:
        return []
    grouped = (
        sel.groupby(["competition", "source_kind"], dropna=False)
        .size()
        .reset_index(name="n_matches")
        .sort_values(by=["source_kind", "competition"], kind="mergesort")
    )
    return [
        {
            "competition": _str_or_none(rec["competition"]),
            "source_kind": _str_or_none(rec["source_kind"]),
            "n_matches": int(rec["n_matches"]),
        }
        for _, rec in grouped.iterrows()
    ]


def list_competitions() -> dict[str, Any]:
    """Distinct (competition, source_kind) with match counts, deterministically ordered."""
    frame = _load_index()
    grouped = (
        frame.groupby(["competition", "source_kind"], dropna=False)
        .size()
        .reset_index(name="n_matches")
        .sort_values(by=["source_kind", "competition"], kind="mergesort")
    )
    competitions = [
        {
            "competition": _str_or_none(rec["competition"]),
            "source_kind": _str_or_none(rec["source_kind"]),
            "n_matches": int(rec["n_matches"]),
        }
        for _, rec in grouped.iterrows()
    ]
    return {"schema_version": SCHEMA_VERSION, "competitions": competitions}


def _load_side_tables() -> tuple[Any, Any]:
    """(goalscorers, shootouts) parquet frames for the internationals notebook.

    Best-effort: a missing or unreadable side table becomes None, so the
    scorer/shootout templates simply do not run (no data is invented).
    """
    import pandas as pd

    def _read(path: Path) -> Any:
        try:
            return pd.read_parquet(path) if Path(path).exists() else None
        except Exception:  # noqa: BLE001 (missing side table => templates skip)
            return None

    return _read(GOALSCORERS_PATH), _read(SHOOTOUTS_PATH)


def _compute_notebook_on_demand(row: Any, frame: Any) -> dict[str, Any]:
    """Build the notebook for one index row at ``kickoff - 1s`` (leak-safe cutoff)."""
    import pandas as pd
    from golavo_core.facts import build_notebook

    kickoff = pd.Timestamp(row["kickoff_utc"])
    kickoff = kickoff.tz_localize("UTC") if kickoff.tzinfo is None else kickoff.tz_convert("UTC")
    as_of = kickoff - pd.Timedelta(seconds=1)

    goalscorers = shootouts = None
    if _str_or_none(row["source_kind"]) == "international":
        goalscorers, shootouts = _load_side_tables()

    source_id = _str_or_none(row["source_id"])
    source_ids = [source_id] if source_id else []

    # Scope the history to the fixture's own source before the team-name templates
    # run. A team string can be shared across sources ("Monaco" is both the
    # national side in the internationals pack and the Ligue 1 club in the club
    # pack); over the full mixed index a team-scoped fact would silently merge a
    # club's form into an international fixture (and vice versa) while citing only
    # this fixture's source. Restricting here mirrors the sealed path, which only
    # ever sees its own single-source pack.
    if source_id is not None:
        frame = frame.loc[frame["source_id"].astype("string") == source_id]

    notebook = build_notebook(
        matches=frame,
        home_team=_str_or_none(row["home_team"]) or "",
        away_team=_str_or_none(row["away_team"]) or "",
        competition=_str_or_none(row["competition"]) or "",
        neutral=bool(_bool_or_none(row["neutral"])),
        as_of_utc=as_of.isoformat(),
        kickoff_utc=kickoff.isoformat(),
        source_ids=source_ids,
        goalscorers=goalscorers,
        shootouts=shootouts,
        validate=True,
    )
    return {
        "available": True,
        "computed": "on_demand",
        "as_of_horizon": as_of.isoformat().replace("+00:00", "Z"),
        "notebook": notebook,
    }


def match_notebook(match_id: str, *, forecasts_dir: Path) -> dict[str, Any] | None:
    """The Commentator's Notebook for one match; None if the match is unknown.

    Prefers a precomputed ``notebooks/<artifact_id>.json`` next to a sealed
    forecast (byte-for-byte the horizon that forecast trained to). Otherwise
    computes on demand at ``kickoff - 1s`` — the same conservative cutoff the
    seal uses, so the fixture's own result and all later data are excluded. Any
    build/validate failure fails closed to an honest empty envelope rather than
    500-ing the whole page.
    """
    import json

    frame = _load_index()
    sel = frame.loc[frame["match_id"].astype("string") == str(match_id)]
    if sel.empty:
        return None
    row = sel.iloc[0]

    folder = Path(forecasts_dir)
    by_match_id, by_fixture = artifact_links(folder)
    linked, _linked_by = _links_for_row(row, by_match_id, by_fixture)
    for summary in linked:
        nb_path = folder / "notebooks" / f"{summary['artifact_id']}.json"
        if nb_path.is_file():
            try:
                notebook = json.loads(nb_path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                continue
            return {
                "available": True,
                "computed": "precomputed",
                "as_of_horizon": notebook.get("as_of_utc"),
                "notebook": notebook,
            }

    try:
        return _compute_notebook_on_demand(row, frame)
    except Exception:  # noqa: BLE001 (fail closed; never 500 the page)
        return {
            "available": False,
            "computed": None,
            "as_of_horizon": None,
            "notebook": None,
        }
