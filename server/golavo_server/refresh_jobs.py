"""Single-writer approved-source refresh coordinator.

Jobs run only after an API call from the visible UI.  The worker thread is a
daemon so closing Golavo stops it; incomplete staging is ignored and cleaned on
the next run, while the active pointer always continues to reference verified
last-known-good bytes.
"""

from __future__ import annotations

import os
import shutil
import threading
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from golavo_server import matches, refresh, refresh_sources, refresh_state, runtime

JOB_SCHEMA_VERSION = "0.1.0"
_BACKOFF_SECONDS = (15 * 60, 60 * 60, 6 * 60 * 60, 24 * 60 * 60)


def _parse_utc(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(UTC)


def _now_z() -> str:
    return refresh_sources.utc_z()


def _sync_state_to_generation(
    state: dict[str, Any], manifest: dict[str, Any], activated_at_utc: str | None
) -> None:
    """Reconcile source stamps from the immutable active manifest.

    The active pointer is the atomic commit. If the process closes immediately
    after that swap, this derivation keeps status honest on the next launch and
    also repairs source stamps after an explicit rollback.
    """
    active_refs = {
        str(snapshot["source_id"]): str(snapshot["upstream_ref"])
        for snapshot in manifest.get("source_snapshots", [])
        if isinstance(snapshot, dict)
        and isinstance(snapshot.get("source_id"), str)
        and isinstance(snapshot.get("upstream_ref"), str)
    }
    for source_id in refresh_sources.APPROVED_SOURCE_IDS:
        source = state.setdefault("sources", {}).setdefault(source_id, {})
        active_ref = active_refs.get(source_id)
        source["active_ref"] = active_ref
        if active_ref is not None:
            source["last_activated_at_utc"] = activated_at_utc
        if source.get("error") is None:
            if source.get("observed_ref") == active_ref and active_ref is not None:
                source["health"] = "current"
            elif active_ref is not None and source.get("health") in ("current", "unchanged"):
                source["health"] = "stale"


def _source_from_state(
    source_id: str, value: dict[str, Any]
) -> refresh_sources.SourceObservation | None:
    ref = value.get("observed_ref") or value.get("active_ref")
    if not isinstance(ref, str) or len(ref) != 40:
        return None
    return refresh_sources.SourceObservation(
        source_id=source_id,
        ref=ref,
        committed_at_utc=str(value.get("upstream_committed_at_utc") or ""),
        etag=str(value["etag"]) if value.get("etag") else None,
        checked_at_utc=str(value.get("last_checked_at_utc") or _now_z()),
        changed=False,
        capability=str(value.get("capability") or "available"),
        season=str(value["season"]) if value.get("season") else None,
        current_paths=tuple(str(path) for path in value.get("current_paths", [])),
    )


class RefreshCoordinator:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._cancel: threading.Event | None = None
        self._job: dict[str, Any] | None = None

    def _persist_job(self) -> None:
        state = refresh_state.load_state()
        state["job"] = self._job
        refresh_state.save_state(state)

    def _update_job(self, **updates: Any) -> None:
        with self._lock:
            if self._job is None:
                return
            self._job.update(updates)
            self._job["updated_at_utc"] = _now_z()
            self._persist_job()

    def start(
        self,
        *,
        mode: str,
        source_ids: list[str] | None,
        trigger: str,
        fetcher: refresh_sources.Fetcher | None = None,
    ) -> tuple[dict[str, Any], bool]:
        if mode not in ("check", "refresh"):
            raise ValueError("mode must be check or refresh")
        if trigger not in ("manual", "launch", "periodic"):
            raise ValueError("trigger must be manual, launch, or periodic")
        selected = list(source_ids or refresh_sources.APPROVED_SOURCE_IDS)
        if not selected or len(selected) != len(set(selected)):
            raise ValueError("source_ids must be a non-empty unique array")
        unknown = sorted(set(selected) - set(refresh_sources.APPROVED_SOURCE_IDS))
        if unknown:
            raise ValueError(f"unapproved source_ids: {unknown}")
        if mode == "refresh" and set(selected) != set(refresh_sources.APPROVED_SOURCE_IDS):
            raise ValueError("refresh mode requires the complete approved source set")
        if runtime.refresh_dir() is None:
            raise RuntimeError("refresh is unavailable without a writable application data path")
        with self._lock:
            if self._thread is not None and self._thread.is_alive() and self._job is not None:
                return {**self._job, "deduplicated": True}, True
            job_id = "rj_" + uuid.uuid4().hex
            now = _now_z()
            self._cancel = threading.Event()
            self._job = {
                "schema_version": JOB_SCHEMA_VERSION,
                "job_id": job_id,
                "state": "queued",
                "stage": "queued",
                "mode": mode,
                "trigger": trigger,
                "source_ids": selected,
                "created_at_utc": now,
                "updated_at_utc": now,
                "cancel_requested": False,
                "progress": {},
                "result": None,
                "error": None,
            }
            self._persist_job()
            self._thread = threading.Thread(
                target=self._run,
                args=(mode, selected, trigger, fetcher),
                name=f"golavo-refresh-{job_id[-8:]}",
                daemon=True,
            )
            self._thread.start()
            return dict(self._job), False

    def get(self, job_id: str | None = None) -> dict[str, Any] | None:
        with self._lock:
            if self._job is not None and (job_id is None or self._job["job_id"] == job_id):
                return dict(self._job)
        persisted = refresh_state.load_state().get("job")
        if isinstance(persisted, dict) and (job_id is None or persisted.get("job_id") == job_id):
            if persisted.get("state") in ("queued", "running"):
                return {
                    **persisted,
                    "state": "failed",
                    "stage": "done",
                    "error": {
                        "code": "interrupted",
                        "message": (
                            "the previous refresh stopped when Golavo closed; "
                            "active data was unchanged"
                        ),
                        "retryable": True,
                    },
                }
            return persisted
        return None

    def cancel(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            if self._job is None or self._job.get("job_id") != job_id:
                return None
            if self._job.get("state") not in ("queued", "running"):
                return dict(self._job)
            if self._cancel is not None:
                self._cancel.set()
            self._job["cancel_requested"] = True
            self._persist_job()
            return dict(self._job)

    def _due(self, source_state: dict[str, Any], trigger: str) -> bool:
        error = source_state.get("error")
        rate_limited = isinstance(error, dict) and error.get("code") == "rate_limited"
        if trigger == "manual" and not rate_limited:
            return True
        next_check = _parse_utc(source_state.get("next_check_after_utc"))
        return next_check is None or datetime.now(UTC) >= next_check

    def _source_success(
        self, state: dict[str, Any], observation: refresh_sources.SourceObservation
    ) -> None:
        previous = state.setdefault("sources", {}).get(observation.source_id, {})
        value = {**previous, **observation.as_state()}
        if value.get("quarantined_ref") != observation.ref:
            value.pop("quarantined_ref", None)
        if not observation.changed:
            value["last_changed_at_utc"] = previous.get("last_changed_at_utc")
        elif previous.get("active_ref") != observation.ref:
            value["health"] = "stale"
        value["failure_count"] = 0
        value["next_check_after_utc"] = refresh_sources.utc_z(
            datetime.now(UTC)
            + timedelta(seconds=refresh_sources.source_interval_seconds(observation.source_id))
        )
        state["sources"][observation.source_id] = value

    def _source_failure(
        self, state: dict[str, Any], source_id: str, error: refresh_sources.RefreshSourceError
    ) -> None:
        previous = state.setdefault("sources", {}).get(source_id, {})
        failures = int(previous.get("failure_count") or 0) + 1
        delay = _BACKOFF_SECONDS[min(failures - 1, len(_BACKOFF_SECONDS) - 1)]
        state["sources"][source_id] = {
            **previous,
            "source_id": source_id,
            "health": "backoff" if error.retryable else "invalid",
            "failure_count": failures,
            "last_checked_at_utc": _now_z(),
            "next_check_after_utc": refresh_sources.utc_z(
                datetime.now(UTC) + timedelta(seconds=delay)
            ),
            "error": {"code": error.code, "message": str(error), "retryable": error.retryable},
        }

    def _run(
        self,
        mode: str,
        selected: list[str],
        trigger: str,
        fetcher: refresh_sources.Fetcher | None,
    ) -> None:
        try:
            with refresh_state.refresh_job_lock():
                self._run_locked(mode, selected, trigger, fetcher)
        except (OSError, RuntimeError) as exc:
            self._fail("refresh_locked", str(exc), retryable=True)

    def _run_locked(
        self,
        mode: str,
        selected: list[str],
        trigger: str,
        fetcher: refresh_sources.Fetcher | None,
    ) -> None:
        assert self._job is not None and self._cancel is not None
        job_id = str(self._job["job_id"])
        staging = refresh_state.staging_dir() / job_id
        try:
            refresh_state.staging_dir().mkdir(parents=True, exist_ok=True)
            # With the cross-process job lock held, any older staging directory
            # came from an interrupted process and can never be active.
            for old in refresh_state.staging_dir().iterdir():
                if old != staging and old.is_dir():
                    shutil.rmtree(old, ignore_errors=True)
            shutil.rmtree(staging, ignore_errors=True)
            staging.mkdir(parents=True)
            self._update_job(state="running", stage="checking")
            state = refresh_state.load_state()
            observations: dict[str, refresh_sources.SourceObservation] = {}
            failures: dict[str, refresh_sources.RefreshSourceError] = {}
            for source_id in selected:
                previous = state.setdefault("sources", {}).get(source_id, {})
                if not self._due(previous, trigger):
                    saved = _source_from_state(source_id, previous)
                    if saved is not None:
                        observations[source_id] = saved
                    continue
                try:
                    observation = refresh_sources.check_source(
                        source_id,
                        previous,
                        fetcher=fetcher,
                        cancel=self._cancel,
                    )
                except refresh_sources.RefreshSourceError as exc:
                    failures[source_id] = exc
                    self._source_failure(state, source_id, exc)
                else:
                    observations[source_id] = observation
                    self._source_success(state, observation)
                refresh_state.save_state(state)
                self._update_job(
                    progress={
                        "checked": len(observations) + len(failures),
                        "total": len(selected),
                        "failures": sorted(failures),
                    }
                )
            if self._cancel.is_set():
                raise refresh_sources.RefreshCancelled()
            if mode == "check":
                self._finish(
                    {
                        "activated": False,
                        "observed": {key: value.ref for key, value in observations.items()},
                        "failures": sorted(failures),
                    }
                )
                refresh_state.clean_staging(staging)
                return

            # Activation is all-or-nothing. Check-only jobs may report partial
            # source failures, but a generation always carries evidence for the
            # complete approved set, including a pinned tree proving club absence.
            for dependency in refresh_sources.APPROVED_SOURCE_IDS:
                if dependency not in observations:
                    previous = state.setdefault("sources", {}).get(dependency, {})
                    try:
                        observation = refresh_sources.check_source(
                            dependency,
                            previous,
                            fetcher=fetcher,
                            cancel=self._cancel,
                        )
                    except refresh_sources.RefreshSourceError as exc:
                        self._source_failure(state, dependency, exc)
                        refresh_state.save_state(state)
                        raise exc
                    observations[dependency] = observation
                    self._source_success(state, observation)
                    refresh_state.save_state(state)
            football = observations.get(refresh_sources.FOOTBALL)
            active_path, _ = refresh_state.active_generation()
            active_manifest = refresh_state.verify_generation(active_path) if active_path else None
            active_refs = {
                str(item.get("source_id")): str(item.get("upstream_ref"))
                for item in (active_manifest or {}).get("source_snapshots", [])
                if isinstance(item, dict)
            }
            blocked = [
                source_id
                for source_id, observation in observations.items()
                if state.get("sources", {}).get(source_id, {}).get("quarantined_ref")
                == observation.ref
            ]
            if blocked:
                self._finish(
                    {
                        "activated": False,
                        "reason": "quarantined_ref_unchanged",
                        "sources": sorted(blocked),
                        "active_generation_id": active_path.name if active_path else None,
                    }
                )
                refresh_state.clean_staging(staging)
                return
            changed = any(
                active_refs.get(source_id) != observation.ref
                for source_id, observation in observations.items()
                if source_id != refresh_sources.FOOTBALL or observation.current_paths
            )
            if active_path is not None and not changed:
                self._finish(
                    {
                        "activated": False,
                        "reason": "unchanged",
                        "active_generation_id": active_path.name,
                        "failures": sorted(failures),
                    }
                )
                refresh_state.clean_staging(staging)
                return

            self._update_job(stage="downloading")
            snapshots: list[dict[str, Any]] = []
            for source_id in (refresh_sources.MARTJ42, refresh_sources.WORLDCUP):
                snapshots.append(
                    refresh_sources.download_source_snapshot(
                        observations[source_id],
                        staging / "raw",
                        fetcher=fetcher,
                        cancel=self._cancel,
                    )
                )
            if football is not None:
                snapshots.append(
                    refresh_sources.download_source_snapshot(
                        football, staging / "raw", fetcher=fetcher, cancel=self._cancel
                    )
                )
            if self._cancel.is_set():
                raise refresh_sources.RefreshCancelled()

            self._update_job(stage="validating")
            martj = observations[refresh_sources.MARTJ42]
            worldcup = observations[refresh_sources.WORLDCUP]
            refresh.build_international_runtime_pack(
                staging / "raw",
                martj_ref=martj.ref,
                martj_committed_at=martj.committed_at_utc,
                worldcup_ref=worldcup.ref,
                worldcup_committed_at=worldcup.committed_at_utc,
                retrieved_at_utc=martj.checked_at_utc,
                output_dir=staging / "packs" / "internationals",
            )
            club_packs: list[Path] = []
            capabilities: list[dict[str, Any]] = []
            if football is not None:
                if football.current_paths:
                    club_packs, capabilities = refresh.build_club_runtime_packs(
                        staging / "raw",
                        football_ref=football.ref,
                        football_committed_at=football.committed_at_utc,
                        season=str(football.season),
                        current_paths=football.current_paths,
                        retrieved_at_utc=football.checked_at_utc,
                        output_root=staging / "packs" / "clubs",
                        as_of_utc=_now_z(),
                    )
                else:
                    capabilities = [
                        {
                            "source_id": refresh_sources.FOOTBALL,
                            "season": football.season,
                            "upstream_ref": football.ref,
                            "checked_at_utc": football.checked_at_utc,
                            "capability": "absent",
                            "reason": "the approved source has not published current-season files",
                        }
                    ]

            self._update_job(stage="building")
            base_index = Path(matches.INDEX_PATH)
            season_start = (
                f"{football.season[:4]}-07-01" if football and football.season else "9999-07-01"
            )
            candidate = refresh.merge_refresh_generation(
                staging / "packs" / "internationals",
                club_packs,
                base_index,
                staging / "index",
                season_start=season_start,
            )
            change_summary = refresh.assert_safe_change(base_index, candidate, runtime.data_dir())
            manifest = refresh.write_generation_manifest(
                staging,
                source_snapshots=snapshots,
                capabilities=capabilities,
                change_summary=change_summary,
                created_at_utc=_now_z(),
            )
            if self._cancel.is_set():
                raise refresh_sources.RefreshCancelled()

            self._update_job(stage="activating")
            installed = refresh_state.install_generation(staging, str(manifest["generation_id"]))
            pointer = refresh_state.activate_generation(installed.name, activated_at_utc=_now_z())
            matches.repoint_to_refreshed()
            final_state = refresh_state.load_state()
            import pandas as pd

            activated_frame = pd.read_parquet(installed / "index" / "matches_index.parquet")
            _sync_state_to_generation(final_state, manifest, pointer["activated_at_utc"])
            for source_id in observations:
                source = final_state.setdefault("sources", {}).setdefault(source_id, {})
                provenance_columns = [
                    column
                    for column in (
                        "identity_source_id",
                        "result_source_id",
                        "kickoff_source_id",
                        "venue_source_id",
                        "training_source_id",
                    )
                    if column in activated_frame.columns
                ]
                mask = activated_frame["source_id"].astype("string").eq(source_id)
                for column in provenance_columns:
                    mask = mask | activated_frame[column].astype("string").eq(source_id)
                data_dates = pd.to_datetime(activated_frame.loc[mask, "kickoff_utc"], utc=True)
                source["data_through_utc"] = (
                    data_dates.max().isoformat().replace("+00:00", "Z")
                    if not data_dates.empty and data_dates.notna().any()
                    else None
                )
            if football is not None:
                football_state = final_state.setdefault("sources", {}).setdefault(
                    refresh_sources.FOOTBALL, {}
                )
                football_state["competitions"] = capabilities
                if football.current_paths:
                    football_state["capability"] = (
                        "complete"
                        if len(football.current_paths) == len(refresh_sources.LEAGUE_CODES)
                        and all(item.get("capability") == "complete" for item in capabilities)
                        else "partial"
                    )
            refresh_state.save_state(final_state)
            self._finish(
                {
                    "activated": True,
                    "active_generation_id": installed.name,
                    "previous_generation_id": pointer.get("previous_generation_id"),
                    "change_summary": change_summary,
                    "capabilities": capabilities,
                    "failures": sorted(failures),
                }
            )
        except refresh_sources.RefreshCancelled:
            refresh_state.clean_staging(staging)
            self._update_job(state="cancelled", stage="done", error=None)
        except refresh.RefreshConflict as exc:
            quarantine = refresh_state.quarantine_dir() / job_id
            quarantine.parent.mkdir(parents=True, exist_ok=True)
            if staging.exists():
                os.replace(staging, quarantine)
            state = refresh_state.load_state()
            for source_id, observation in locals().get("observations", {}).items():
                source = state.setdefault("sources", {}).setdefault(source_id, {})
                if observation.changed:
                    source["health"] = "conflict"
                    source["quarantined_ref"] = observation.ref
                    source["error"] = {
                        "code": "source_conflict",
                        "message": str(exc),
                        "retryable": False,
                    }
            refresh_state.save_state(state)
            self._fail("source_conflict", str(exc), retryable=False)
        except refresh_sources.RefreshSourceError as exc:
            refresh_state.clean_staging(staging)
            self._fail(exc.code, str(exc), retryable=exc.retryable)
        except (OSError, ValueError, RuntimeError, refresh.RefreshError) as exc:
            refresh_state.clean_staging(staging)
            code = (
                "disk_full"
                if isinstance(exc, OSError) and getattr(exc, "errno", None) == 28
                else "refresh_failed"
            )
            self._fail(code, str(exc), retryable=True)

    def _finish(self, result: dict[str, Any]) -> None:
        self._update_job(state="done", stage="done", result=result, error=None)

    def _fail(self, code: str, message: str, *, retryable: bool) -> None:
        state = refresh_state.load_state()
        state["last_error"] = {"code": code, "message": message, "retryable": retryable}
        refresh_state.save_state(state)
        self._update_job(
            state="failed",
            stage="done",
            error={"code": code, "message": message, "retryable": retryable},
        )


_COORDINATOR = RefreshCoordinator()


def coordinator() -> RefreshCoordinator:
    return _COORDINATOR


def status() -> dict[str, Any]:
    supported = runtime.refresh_dir() is not None
    active, using_previous = refresh_state.active_generation() if supported else (None, False)
    pointer = refresh_state.load_pointer() if supported else None
    manifest = refresh_state.verify_generation(active) if active is not None else None
    state = refresh_state.load_state() if supported else refresh_state.default_state()
    if manifest is not None:
        _sync_state_to_generation(state, manifest, (pointer or {}).get("activated_at_utc"))
    source_rows: list[dict[str, Any]] = []
    for source_id in refresh_sources.APPROVED_SOURCE_IDS:
        value = state.get("sources", {}).get(source_id, {})
        source_rows.append(
            {
                "source_id": source_id,
                "health": value.get("health", "unavailable"),
                "capability": value.get("capability", "unavailable"),
                "active_ref": value.get("active_ref"),
                "observed_ref": value.get("observed_ref"),
                "etag": value.get("etag"),
                "last_checked_at_utc": value.get("last_checked_at_utc"),
                "last_changed_at_utc": value.get("last_changed_at_utc"),
                "last_activated_at_utc": value.get("last_activated_at_utc"),
                "data_through_utc": value.get("data_through_utc"),
                "next_check_after_utc": value.get("next_check_after_utc"),
                "season": value.get("season"),
                "current_paths": value.get("current_paths", []),
                "competitions": value.get("competitions", []),
                "error": value.get("error"),
            }
        )
    active_payload = None
    if active is not None and manifest is not None:
        index_entry = next(
            entry
            for entry in manifest["artifacts"]
            if entry["path"] == "index/matches_index.parquet"
        )
        active_payload = {
            "generation_id": active.name,
            "activated_at_utc": (pointer or {}).get("activated_at_utc"),
            "index_sha256": index_entry["sha256"],
            "rollback_available": bool((pointer or {}).get("previous_generation_id")),
            "using_previous_generation": using_previous,
            "using_bundled_fallback": False,
        }
    return {
        "schema_version": "0.1.0",
        "refresh_supported": supported,
        "active_generation": active_payload,
        "using_bundled_fallback": active is None,
        "sources": source_rows,
        "job": coordinator().get() if supported else None,
        "last_error": state.get("last_error"),
    }


def rollback() -> dict[str, Any]:
    pointer = refresh_state.rollback(activated_at_utc=_now_z())
    active = refresh_state.generation_dir(str(pointer["active_generation_id"]))
    manifest = refresh_state.verify_generation(active)
    state = refresh_state.load_state()
    _sync_state_to_generation(state, manifest, str(pointer["activated_at_utc"]))
    refresh_state.save_state(state)
    matches.repoint_to_refreshed()
    return {"schema_version": "0.1.0", **pointer}
