"""Read-only match search + on-demand Commentator's Notebook over the frozen index.

Everything here reads either the verified immutable active generation or the
committed bundle (``data/index``), and never writes. Three honesty properties
hold end to end:

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

import json
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
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
    generation_index: Path | None = None
    if refreshed is not None:
        try:
            from golavo_server import refresh_state

            active, _using_previous = refresh_state.active_generation()
            if active is not None:
                generation_index = active / "index"
        except (OSError, RuntimeError, ValueError):
            generation_index = None
    candidate = generation_index or refreshed
    if candidate is not None and (candidate / "matches_index.parquet").exists():
        from golavo_core.ingest.match_index import MATCH_INDEX_SCHEMA_VERSION

        try:
            meta = json.loads((candidate / "matches_index.meta.json").read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            meta = {}
        if meta.get("schema_version") == MATCH_INDEX_SCHEMA_VERSION:
            return {
                "index": candidate / "matches_index.parquet",
                "meta": candidate / "matches_index.meta.json",
                "goalscorers": candidate / "goalscorers.parquet",
                "shootouts": candidate / "shootouts.parquet",
                "aliases": candidate / "aliases.json",
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
# (barring an explicit refresh), so it is loaded once and cached — once PER PATH:
# the cache records which of these it was read from and retires itself when they
# move, so repointing can never serve a frame from the previous index.
_paths = _resolve_index_paths()
INDEX_PATH = _paths["index"]
INDEX_META_PATH = _paths["meta"]
GOALSCORERS_PATH = _paths["goalscorers"]
SHOOTOUTS_PATH = _paths["shootouts"]
ALIASES_PATH = _paths["aliases"]

_CACHE: Any = None  # the loaded index DataFrame; reset_cache() clears it
_FINGERPRINT: str | None = None  # content hash of the index, for the analysis cache
# The (index, meta) pair ``_CACHE`` was read from, so the cache can recognise that
# it has been orphaned by a repoint. None while no attributable frame is cached.
_CACHE_PATHS: tuple[Path, Path] | None = None
_GENERATION_EPOCH = 0
_CACHE_LOCK = threading.RLock()

# Advisory warm-up state for the UI's staged splash / warming card. Mutated with
# the generation state under _CACHE_LOCK. index_status() reports it and NEVER
# triggers the (slow) load itself, so /api/v1/status answers in microseconds even
# mid-warmup.
_WARM: dict[str, Any] = {"state": "cold", "since_utc": None, "error": None}
_META_ROWS: Any = "unread"  # memoized row_count from meta.json: "unread" | int | None


@dataclass(frozen=True)
class IndexSnapshot:
    """One immutable association between an index frame and its provenance key.

    The DataFrame is treated as read-only after publication.  ``epoch`` prevents
    work that began on an older runtime generation from publishing into caches
    after a refresh repoints the module globals.
    """

    frame: Any
    fingerprint: str
    epoch: int
    goalscorers_path: Path | None = None
    shootouts_path: Path | None = None
    aliases_path: Path | None = None
    # Carried so a caller can read this frame's OWN provenance (which packs it was
    # built from) without re-reading the module global, which a concurrent repoint
    # may already have moved off this snapshot's generation.
    meta_path: Path | None = None


def _paths_are_current(epoch: int, index_path: Path, meta_path: Path) -> bool:
    return (
        epoch == _GENERATION_EPOCH
        and index_path == Path(INDEX_PATH)
        and meta_path == Path(INDEX_META_PATH)
    )


def _fingerprint_for(index_path: Path, meta_path: Path) -> str:
    import hashlib

    try:
        data = meta_path.read_bytes()
    except OSError:
        try:
            data = index_path.read_bytes()
        except OSError:
            data = b"unknown"
    return hashlib.sha256(data).hexdigest()


def _invalidate_cache_locked() -> None:
    global _CACHE, _CACHE_PATHS, _META_ROWS, _FINGERPRINT, _GENERATION_EPOCH
    _GENERATION_EPOCH += 1
    _CACHE = None
    _CACHE_PATHS = None
    _META_ROWS = "unread"
    _FINGERPRINT = None
    _WARM["state"] = "cold"
    _WARM["since_utc"] = None
    _WARM["error"] = None


def _reset_derivative_caches() -> None:
    # Called outside _CACHE_LOCK: an invalidator is cheap and idempotent, and a
    # derivative module may call back into this one during import.
    for invalidate in tuple(_INVALIDATORS):
        invalidate()


def _discard_retired_cache() -> None:
    """Drop a cached frame that was read from a path the module no longer names.

    ``_CACHE`` is only meaningful together with the ``INDEX_PATH`` it came from:
    reassigning the path leaves the frame describing a different file, and the
    fast-path cache hit in ``index_snapshot`` would go on serving it forever.
    ``repoint_to_refreshed`` invalidates explicitly, but a plain reassignment
    cannot — most sharply under ``monkeypatch``, which restores ``INDEX_PATH`` at
    teardown and has no way to restore the cache with it, so a test's fixture
    index used to outlive its own test and be served to every later one in the
    process. Binding the cache to its provenance makes that state unrepresentable
    rather than a rule each writer has to remember.

    A frame injected straight into ``_CACHE`` carries no recorded provenance and
    is left alone; it is attributed on its next publication.
    """
    with _CACHE_LOCK:
        if _CACHE_PATHS is None or _CACHE_PATHS == (Path(INDEX_PATH), Path(INDEX_META_PATH)):
            return
        _invalidate_cache_locked()
    # Outside the lock, for the same reason reset_cache() does it there.
    _reset_derivative_caches()


def repoint_to_refreshed() -> None:
    """Swing the module at the refreshed index and drop the cache.

    Called after a successful runtime refresh so the next search / notebook reads
    the fresh bytes. Idempotent, and a no-op when no refresh dir is present.
    """
    global INDEX_PATH, INDEX_META_PATH, GOALSCORERS_PATH, SHOOTOUTS_PATH, ALIASES_PATH
    p = _resolve_index_paths()
    with _CACHE_LOCK:
        INDEX_PATH, INDEX_META_PATH = p["index"], p["meta"]
        GOALSCORERS_PATH = p["goalscorers"]
        SHOOTOUTS_PATH = p["shootouts"]
        ALIASES_PATH = p["aliases"]
        _invalidate_cache_locked()
    _reset_derivative_caches()


class MatchIndexUnavailable(Exception):
    """The committed match index is missing or unreadable.

    The search surface fails closed with a 503 rather than serving a half-built
    page from a corrupt or absent index.
    """


def reset_cache() -> None:
    """Drop the cached index frame and every cache derived from it.

    Repointing ``INDEX_PATH`` no longer requires this — the cache notices that its
    provenance moved (see ``_discard_retired_cache``). It is still the way to force
    a re-read of the SAME path, e.g. after its bytes changed on disk.
    """
    with _CACHE_LOCK:
        _invalidate_cache_locked()
    # Every in-process derivative must move with the index cache. The analysis
    # disk cache remains safe because it is keyed by the snapshot fingerprint.
    _reset_derivative_caches()


def index_snapshot() -> IndexSnapshot:
    """Load one epoch-bound frame + fingerprint pair, retrying across repoints.

    Lazy on purpose: pandas/pyarrow cost ~25s to import from the frozen bundle,
    so the first search pays it (the sidecar warms it in the background) while
    /health and the forecast surface stay light. Drives the advisory ``_WARM``
    state machine (cold -> warming -> ready|error) so the UI splash can show
    honest, real-stage progress instead of a pure fake curve.

    The expensive Parquet read is deliberately outside ``_CACHE_LOCK``. Before
    publishing, the captured epoch and paths are rechecked. A read that started
    before refresh activation is discarded and retried against the new paths,
    so it can never repopulate ``_CACHE`` with the retired generation.
    """
    global _CACHE, _CACHE_PATHS, _FINGERPRINT
    import pandas as pd

    while True:
        _discard_retired_cache()
        with _CACHE_LOCK:
            if _CACHE is not None and _FINGERPRINT is not None:
                return IndexSnapshot(
                    _CACHE,
                    _FINGERPRINT,
                    _GENERATION_EPOCH,
                    Path(GOALSCORERS_PATH),
                    Path(SHOOTOUTS_PATH),
                    Path(ALIASES_PATH),
                    Path(INDEX_META_PATH),
                )
            epoch = _GENERATION_EPOCH
            index_path = Path(INDEX_PATH)
            meta_path = Path(INDEX_META_PATH)
            cached_frame = _CACHE
            if _WARM["state"] == "cold":
                _WARM["state"] = "warming"
                _WARM["since_utc"] = datetime.now(UTC).isoformat()

        if cached_frame is None:
            if not index_path.exists():
                with _CACHE_LOCK:
                    if not _paths_are_current(epoch, index_path, meta_path):
                        continue
                    _WARM["state"] = "error"
                    _WARM["error"] = f"match index not found at {index_path}"
                raise MatchIndexUnavailable(f"match index not found at {index_path}")
            try:
                frame = pd.read_parquet(index_path)
            except Exception as exc:  # noqa: BLE001 (any read/parse failure => unavailable)
                with _CACHE_LOCK:
                    if not _paths_are_current(epoch, index_path, meta_path):
                        continue
                    _WARM["state"] = "error"
                    _WARM["error"] = f"match index unreadable: {exc}"
                raise MatchIndexUnavailable(f"match index unreadable: {exc}") from exc
        else:
            # Compatibility with tests that inject a preloaded frame directly.
            frame = cached_frame

        fingerprint = _fingerprint_for(index_path, meta_path)
        with _CACHE_LOCK:
            if not _paths_are_current(epoch, index_path, meta_path):
                continue
            if _CACHE is None:
                _CACHE = frame
                _FINGERPRINT = fingerprint
                _CACHE_PATHS = (index_path, meta_path)
            elif _CACHE is cached_frame and _FINGERPRINT is None:
                _FINGERPRINT = fingerprint
                _CACHE_PATHS = (index_path, meta_path)
            # Another loader may have won publication for this same epoch. Use
            # its frame and fingerprint rather than replacing an equal-generation
            # object while callers are already reading it.
            assert _CACHE is not None and _FINGERPRINT is not None
            _WARM["state"] = "ready"
            _WARM["error"] = None
            return IndexSnapshot(
                _CACHE,
                _FINGERPRINT,
                _GENERATION_EPOCH,
                Path(GOALSCORERS_PATH),
                Path(SHOOTOUTS_PATH),
                Path(ALIASES_PATH),
                Path(INDEX_META_PATH),
            )


def _load_index() -> Any:
    """Compatibility view of :func:`index_snapshot` for read-only consumers."""
    return index_snapshot().frame


def snapshot_is_current(snapshot: IndexSnapshot) -> bool:
    """Whether ``snapshot`` still names the published active generation."""
    with _CACHE_LOCK:
        return (
            snapshot.epoch == _GENERATION_EPOCH
            and snapshot.frame is _CACHE
            and snapshot.fingerprint == _FINGERPRINT
        )


def apply_if_snapshot_current(snapshot: IndexSnapshot, operation: Callable[[], None]) -> bool:
    """Run a small cache-publication operation only for the active generation."""
    with _CACHE_LOCK:
        if not (
            snapshot.epoch == _GENERATION_EPOCH
            and snapshot.frame is _CACHE
            and snapshot.fingerprint == _FINGERPRINT
        ):
            return False
        operation()
        return True


# Refresh activation is infrequent and serialized, so three generation retries are
# ample while keeping a pathological repoint loop fail-closed.
_MAX_ATTEMPTS = 3


class _GenerationMoved(Exception):
    """Internal retry signal: the active generation changed inside the window."""


def _generation_status() -> dict[str, Any]:
    # Local import: refresh_jobs imports this module, and this module is loaded
    # at sidecar boot.
    from golavo_server import refresh_jobs

    return refresh_jobs.status()


def _generation_id(status: dict[str, Any]) -> str | None:
    active = status.get("active_generation") or {}
    return active.get("generation_id")


@dataclass(frozen=True)
class StableGeneration:
    """One index generation, proven not to have moved while work ran on it."""

    snapshot: IndexSnapshot
    status: dict[str, Any]
    generation_id: str | None

    @property
    def sources(self) -> dict[str, dict[str, Any]]:
        """Per-source refresh status, keyed by source id."""
        return {
            item["source_id"]: item
            for item in self.status.get("sources", [])
            if item.get("source_id") is not None
        }

    def require_stable(self) -> None:
        """Assert the generation has not moved since this window opened.

        Call it after reading from ``snapshot`` and before writing anything, so
        the check brackets the read — a refresh activating while a match was
        being looked up must invalidate the window, which is why the status is
        re-read here rather than captured once up front. It raises the retry
        signal rather than returning a flag so a caller cannot read the answer
        and forget to act on it.
        """
        if _generation_id(_generation_status()) != self.generation_id:
            raise _GenerationMoved
        if not snapshot_is_current(self.snapshot):
            raise _GenerationMoved

    def commit(self, operation: Callable[[], None]) -> bool:
        """Publish a small cache operation, but only for this generation."""
        return apply_if_snapshot_current(self.snapshot, operation)


async def run_on_stable_generation(
    work: Callable[[StableGeneration], Any],
    *,
    detail: str,
    attempts: int = _MAX_ATTEMPTS,
) -> Any:
    """Run ``work`` against an index generation that provably did not move.

    The read path has had this since ``SnapshotReader``; the write path did not,
    so following a match, reconciling follows and proposing a correction each
    hand-inlined the same loop — read the refresh status, take a snapshot, read
    the status again, compare generation ids, retry if they moved. Three copies
    of a concurrency guard is three chances for one of them to drift, and the
    only way to exercise any of them was to stand up the whole app.

    ``work`` is retried when it calls ``require_stable()`` on a window that has
    moved, and when it raises a store failure whose ``reason_code`` is
    ``index_generation_changed`` — the same race losing at write time instead of
    check time. Every other failure propagates untouched. Exhausting the
    attempts raises ``MatchIndexUnavailable`` so the route fails closed with a
    503 rather than spinning or half-writing.
    """
    from starlette.concurrency import run_in_threadpool

    for _attempt in range(attempts):
        snapshot = await run_in_threadpool(index_snapshot)
        status = _generation_status()
        stable = StableGeneration(
            snapshot=snapshot,
            status=status,
            generation_id=_generation_id(status),
        )
        try:
            return await work(stable)
        except _GenerationMoved:
            continue
        except Exception as exc:  # noqa: BLE001 (re-raised unless it is the race)
            if getattr(exc, "reason_code", None) == "index_generation_changed":
                continue
            raise
    raise MatchIndexUnavailable(detail)

# Everything to drop when the index repoints. A SnapshotReader joins at
# construction, so this module never needs to know the name of a single derivative
# module to invalidate it — the failure it used to invite was a new cached read
# quietly missing from a hardcoded tuple, serving a retired generation's work
# after a refresh and looking exactly like fresh work.
_INVALIDATORS: list[Callable[[], None]] = []
_READERS: list[SnapshotReader] = []


def on_repoint(invalidate: Callable[[], None]) -> None:
    """Register a cache to drop whenever the index repoints.

    For state that moves with the index but is not itself a
    :class:`SnapshotReader` memo (the context pack's fingerprint-stamped
    capability report). A reader registers itself; nothing else has to remember to.
    """
    _INVALIDATORS.append(invalidate)


class RetryGeneration(Exception):
    """``compute`` raising this says: my snapshot is retired, try the next one.

    For work that discovers mid-compute that the frame under it has been repointed
    (a fit that failed on a half-retired generation, say). Nothing is published and
    the attempt does not count as an answer.
    """


class SnapshotReader:
    """One derived read over the active index generation — memoized and honest.

    The whole dance every derived read needs, owned once: load a snapshot, key the
    memo by ``(caller key..., fingerprint, epoch)``, recheck the generation before
    trusting a hit, stamp the fingerprint into the result's provenance, and publish
    only under the lock that guards the epoch bump — so work begun on a generation
    a refresh has since retired can never enter the cache. Callers supply only the
    part that is theirs: what to compute.

    Registration is the point of the class, not an implementation detail: a reader
    cannot be built without becoming invalidatable.
    """

    def __init__(
        self, name: str, *, max_entries: int = 32, stamps_provenance: bool = False
    ) -> None:
        self.name = name
        self._max_entries = max_entries
        # Whether this read's envelope carries a ``provenance.index_sha256``. Only
        # the reader can stamp it honestly — it alone knows which snapshot the
        # result was actually computed on, rather than which one the module global
        # names by the time the answer is serialized. Off by default: an envelope
        # that does not declare provenance (the conditions pack stamps its own
        # ``snapshot_sha256``; an analysis envelope carries none) must not have a
        # field invented on it.
        self._stamps_provenance = stamps_provenance
        self._entries: dict[tuple[Any, ...], Any] = {}
        self._order: list[tuple[Any, ...]] = []
        _READERS.append(self)
        on_repoint(self.reset)

    def reset(self) -> None:
        """Drop this reader's memo (tests / after an index repoint)."""
        self._entries.clear()
        self._order.clear()

    def entries(self) -> dict[tuple[Any, ...], Any]:
        """The live memo — for tests and diagnostics, never for serving."""
        return self._entries

    def _publish(self, key: tuple[Any, ...], value: Any) -> None:
        self._entries[key] = value
        self._order.append(key)
        while len(self._order) > self._max_entries:
            self._entries.pop(self._order.pop(0), None)

    def read(
        self,
        compute: Callable[[IndexSnapshot], Any],
        *,
        key: tuple[Any, ...] | Callable[[], tuple[Any, ...]] = (),
    ) -> Any:
        """``compute(snapshot)``'s result for the active generation, memoized.

        ``key`` names what else the result depends on (a competition id, an as-of
        minute). Pass a callable when the key itself must be resolved per attempt —
        the retrospective's active pack can move under an unchanged index, and its
        memo has to self-invalidate when it does.

        Raises ``MatchIndexUnavailable`` when a repoint outruns every attempt: there
        is no settled generation left to describe, and stale work is worse than none.
        """
        for _attempt in range(_MAX_ATTEMPTS):
            snapshot = index_snapshot()
            extra = key() if callable(key) else key
            full_key = (*extra, snapshot.fingerprint, snapshot.epoch)

            cached = self._entries.get(full_key)
            if cached is not None:
                if snapshot_is_current(snapshot):
                    return cached
                continue  # a repoint raced us; retry against the new generation

            try:
                result = compute(snapshot)
            except RetryGeneration:
                continue
            # The fingerprint is read from THIS snapshot, never the module global a
            # concurrent repoint may already have moved.
            if self._stamps_provenance and isinstance(result, dict):
                provenance = result.setdefault("provenance", {})
                if isinstance(provenance, dict):
                    provenance["index_sha256"] = snapshot.fingerprint

            if apply_if_snapshot_current(
                snapshot, lambda key=full_key, result=result: self._publish(key, result)
            ):
                return result
        raise MatchIndexUnavailable(
            f"verified match index changed during {self.name}; retry"
        )


def registered_readers() -> tuple[SnapshotReader, ...]:
    """Every reader that will be invalidated on a repoint."""
    return tuple(_READERS)


def _meta_row_count() -> int | None:
    """Row count from the index meta.json, memoized. Cheap: a small JSON read, no
    pandas/pyarrow — safe to call during warmup. Any failure -> None."""
    global _META_ROWS
    while True:
        with _CACHE_LOCK:
            if _META_ROWS != "unread":
                return _META_ROWS
            epoch = _GENERATION_EPOCH
            meta_path = Path(INDEX_META_PATH)
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            value = meta.get("row_count")
            rows = int(value) if value is not None else None
        except Exception:  # noqa: BLE001 (missing/corrupt meta -> unknown count)
            rows = None
        with _CACHE_LOCK:
            if epoch != _GENERATION_EPOCH or meta_path != Path(INDEX_META_PATH):
                continue
            _META_ROWS = rows
            return _META_ROWS


def index_fingerprint() -> str:
    """A content hash of the active index, for content-addressed caches.

    Prefers the index meta.json (it embeds every pack's ``manifest_sha256``, so any
    refresh/rebuild changes it) and falls back to hashing the parquet bytes. Any
    change to the index bytes changes the fingerprint, so a cache keyed on it can
    never serve an analysis fitted on a different index. Memoized; reset with the
    frame in ``reset_cache``/``repoint_to_refreshed``.
    """
    global _FINGERPRINT
    while True:
        with _CACHE_LOCK:
            if _FINGERPRINT is not None:
                return _FINGERPRINT
            epoch = _GENERATION_EPOCH
            index_path = Path(INDEX_PATH)
            meta_path = Path(INDEX_META_PATH)
        fingerprint = _fingerprint_for(index_path, meta_path)
        with _CACHE_LOCK:
            if not _paths_are_current(epoch, index_path, meta_path):
                continue
            if _FINGERPRINT is None:
                _FINGERPRINT = fingerprint
            return _FINGERPRINT


def index_status() -> dict[str, Any]:
    """Live warm-up status for the UI. Reports only; never triggers the load."""
    # Dropping a retired frame is not a load: it keeps this from reporting "ready"
    # on behalf of an index the module has already been pointed away from.
    _discard_retired_cache()
    with _CACHE_LOCK:
        ready = _CACHE is not None
        warm_state = _WARM["state"]
        warming_since = _WARM["since_utc"]
    return {
        "index_ready": ready,
        "index_state": "ready" if ready else warm_state,
        "index_rows": _meta_row_count(),
        "warming_since": warming_since,
    }


def _normalize(text: Any) -> str:
    """Fold a query to the index's search key.

    Delegates to the one fold in ``golavo_core.identity``. Imported inside the
    function, not at module scope, because that module pulls pandas and this one
    is imported at sidecar boot (see the module docstring).
    """
    from golavo_core.identity import normalize

    return normalize(text)


def _load_aliases(path: Path | None = None) -> dict[str, list[str]]:
    """Former-name -> canonical display names map (keys already normalized)."""
    import json

    try:
        raw = json.loads(Path(path or ALIASES_PATH).read_text(encoding="utf-8"))
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

    from golavo_core.identity import fixture_key

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
            key = fixture_key(kickoff, home, away)
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
    from golavo_core.identity import fixture_key

    match_id = str(row["match_id"])
    if match_id in by_match_id:
        return by_match_id[match_id], "match_id"

    date_value = row["date"]
    if not _isna(date_value):
        key = fixture_key(date_value, row["home_norm"], row["away_norm"])
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
    provenance_columns = {
        "identity": "identity_source_id",
        "result": "result_source_id",
        "kickoff": "kickoff_source_id",
        "venue": "venue_source_id",
        "training": "training_source_id",
    }
    provenance = {
        label: _str_or_none(row[column])
        for label, column in provenance_columns.items()
        if column in row.index
    }
    return {
        "match_id": str(row["match_id"]),
        "kickoff_utc": _iso_utc(row["kickoff_utc"]),
        "kickoff_precision": (
            _str_or_none(row["kickoff_precision"]) if "kickoff_precision" in row.index else "day"
        ),
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
        "provenance": provenance,
        "upstream_fixture_key": (
            _str_or_none(row["upstream_fixture_key"])
            if "upstream_fixture_key" in row.index
            else None
        ),
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
    ledger dir only. A blank query deliberately starts from the whole directory;
    the HTTP boundary permits that mode only when a status or competition filter
    is active, so it remains bounded and intentional rather than becoming an
    accidental 100,000-row browse.
    """
    import pandas as pd

    snapshot = index_snapshot()
    frame = snapshot.frame
    nq = _normalize(q)
    limit = max(1, min(int(limit), 100))
    offset = max(0, int(offset))

    home_norm = frame["home_norm"].fillna("")
    away_norm = frame["away_norm"].fillna("")
    comp_norm = frame["competition"].fillna("").str.casefold()

    aliases = _load_aliases(snapshot.aliases_path)

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
        mask = pd.Series(True, index=frame.index)
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


def get_match(
    match_id: str,
    *,
    forecasts_dir: Path,
    snapshot: IndexSnapshot | None = None,
) -> dict[str, Any] | None:
    """One match by id -> MatchDetailResponse, or None if absent (route -> 404)."""
    frame = snapshot.frame if snapshot is not None else _load_index()
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


def _load_side_tables(
    goalscorers_path: Path | None = None,
    shootouts_path: Path | None = None,
) -> tuple[Any, Any]:
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

    return _read(goalscorers_path or GOALSCORERS_PATH), _read(
        shootouts_path or SHOOTOUTS_PATH
    )


def _load_worldcup_history() -> Any:
    """Best-effort isolated World Cup history; missing pack means templates skip."""
    try:
        from golavo_core.facts import load_wc_history

        return load_wc_history()
    except (OSError, ValueError):
        return None


def _compute_notebook_on_demand(
    row: Any,
    frame: Any,
    *,
    goalscorers_path: Path | None = None,
    shootouts_path: Path | None = None,
) -> dict[str, Any]:
    """Build the notebook for one index row at ``kickoff - 1s`` (leak-safe cutoff)."""
    from golavo_core.facts import build_notebook
    from golavo_core.ingest.snapshot import leak_safe_cutoff, to_utc

    kickoff = to_utc(row["kickoff_utc"])
    as_of = leak_safe_cutoff(kickoff)

    goalscorers = shootouts = wc_history = None
    if _str_or_none(row["source_kind"]) == "international":
        if goalscorers_path is None and shootouts_path is None:
            goalscorers, shootouts = _load_side_tables()
        else:
            goalscorers, shootouts = _load_side_tables(goalscorers_path, shootouts_path)
        if _str_or_none(row["competition"]) == "FIFA World Cup":
            wc_history = _load_worldcup_history()

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
        wc_history=wc_history,
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

    snapshot = index_snapshot()
    frame = snapshot.frame
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
        return _compute_notebook_on_demand(
            row,
            frame,
            goalscorers_path=snapshot.goalscorers_path,
            shootouts_path=snapshot.shootouts_path,
        )
    except Exception:  # noqa: BLE001 (fail closed; never 500 the page)
        return {
            "available": False,
            "computed": None,
            "as_of_horizon": None,
            "notebook": None,
        }
