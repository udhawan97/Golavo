"""Consent-gated, single-writer refresh coordinator for the ODbL overlay."""

from __future__ import annotations

import os
import shutil
import sqlite3
import threading
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from golavo_server import (
    openligadb_overlay,
    openligadb_source,
    openligadb_state,
    runtime,
)

JOB_SCHEMA_VERSION = "0.1.0"
_BACKOFF_SECONDS = (15 * 60, 60 * 60, 6 * 60 * 60, 24 * 60 * 60)


def _parse_utc(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


class OpenLigaDBCoordinator:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._cancel: threading.Event | None = None
        self._job: dict[str, Any] | None = None

    def _persist(self) -> None:
        state = openligadb_state.load_state()
        state["job"] = self._job
        openligadb_state.save_state(state)

    def _update(self, **updates: Any) -> None:
        with self._lock:
            if self._job is None:
                return
            self._job.update(updates)
            self._job["updated_at_utc"] = openligadb_source.utc_z()
            self._persist()

    def start(
        self,
        *,
        trigger: str,
        fetcher: openligadb_source.ApiFetcher | None = None,
    ) -> tuple[dict[str, Any], bool]:
        if trigger not in ("manual", "launch", "periodic"):
            raise ValueError("trigger must be manual, launch, or periodic")
        if runtime.openligadb_dir() is None:
            raise RuntimeError("OpenLigaDB overlay is unavailable without Application Support")
        settings = openligadb_state.load_settings()
        if not settings["enabled"]:
            raise PermissionError("OpenLigaDB overlay is disabled")
        if trigger != "manual" and settings["refresh_policy"] != "while_open":
            raise PermissionError("automatic OpenLigaDB refresh is not enabled")
        with self._lock:
            if self._thread is not None and self._thread.is_alive() and self._job is not None:
                return {**self._job, "deduplicated": True}, True
            job_id = "olj_" + uuid.uuid4().hex
            now = openligadb_source.utc_z()
            self._cancel = threading.Event()
            self._job = {
                "schema_version": JOB_SCHEMA_VERSION,
                "job_id": job_id,
                "state": "queued",
                "stage": "queued",
                "trigger": trigger,
                "created_at_utc": now,
                "updated_at_utc": now,
                "cancel_requested": False,
                "progress": {},
                "result": None,
                "error": None,
            }
            self._persist()
            self._thread = threading.Thread(
                target=self._run,
                args=(settings, trigger, fetcher),
                name=f"golavo-openligadb-{job_id[-8:]}",
                daemon=True,
            )
            self._thread.start()
            return dict(self._job), False

    def get(self, job_id: str | None = None) -> dict[str, Any] | None:
        with self._lock:
            if self._job is not None and (job_id is None or self._job.get("job_id") == job_id):
                return dict(self._job)
        if runtime.openligadb_dir() is None:
            return None
        persisted = openligadb_state.load_state().get("job")
        if isinstance(persisted, dict) and (job_id is None or persisted.get("job_id") == job_id):
            if persisted.get("state") in ("queued", "running"):
                return {
                    **persisted,
                    "state": "failed",
                    "stage": "done",
                    "error": {
                        "code": "interrupted",
                        "message": (
                            "the previous OpenLigaDB refresh stopped when Golavo closed; "
                            "active overlay data was unchanged"
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
            self._persist()
            return dict(self._job)

    def running(self) -> bool:
        with self._lock:
            return bool(self._thread is not None and self._thread.is_alive())

    def _run(
        self,
        settings: dict[str, Any],
        trigger: str,
        fetcher: openligadb_source.ApiFetcher | None,
    ) -> None:
        try:
            with openligadb_state.job_lock():
                self._run_locked(settings, trigger, fetcher)
        except (OSError, RuntimeError) as exc:
            self._fail("refresh_locked", str(exc), retryable=True)

    def _run_locked(
        self,
        settings: dict[str, Any],
        trigger: str,
        fetcher: openligadb_source.ApiFetcher | None,
    ) -> None:
        assert self._job is not None and self._cancel is not None
        job_id = str(self._job["job_id"])
        staging = openligadb_state.staging_dir() / job_id
        state = openligadb_state.load_state()
        try:
            next_check = _parse_utc(state.get("next_check_after_utc"))
            if trigger != "manual" and next_check is not None and datetime.now(UTC) < next_check:
                self._finish(
                    {
                        "activated": False,
                        "reason": "not_due",
                        "next_check_after_utc": state["next_check_after_utc"],
                    }
                )
                return
            openligadb_state.staging_dir().mkdir(parents=True, exist_ok=True)
            for old in openligadb_state.staging_dir().iterdir():
                if old != staging and old.is_dir():
                    shutil.rmtree(old, ignore_errors=True)
            shutil.rmtree(staging, ignore_errors=True)
            staging.mkdir(parents=True)
            state["health"] = "refreshing"
            state["last_error"] = None
            openligadb_state.save_state(state)
            self._update(state="running", stage="downloading", progress={"responses": 0})
            active_path, _ = openligadb_state.active_generation()
            snapshot = openligadb_source.capture_snapshot(
                staging / "raw",
                settings["selected_competitions"],
                fetcher=fetcher,
                cancel=self._cancel,
                reuse_from=active_path,
            )
            if self._cancel.is_set():
                raise openligadb_source.OpenLigaDBCancelled()
            self._update(
                stage="validating",
                progress={"responses": len(snapshot["receipts"])},
            )
            active_manifest = (
                openligadb_state.verify_generation(active_path) if active_path is not None else None
            )
            if (
                active_manifest is not None
                and active_manifest.get("content_revision") == snapshot["content_revision"]
                and active_manifest.get("selected_competitions")
                == snapshot["selected_competitions"]
            ):
                openligadb_state.clean_staging(staging)
                self._record_success(state, snapshot, activated=False)
                self._finish(
                    {
                        "activated": False,
                        "reason": "unchanged",
                        "active_generation_id": active_path.name,
                        "content_revision": snapshot["content_revision"],
                    }
                )
                return
            self._update(stage="building")
            manifest = openligadb_overlay.write_generation(staging, snapshot)
            if self._cancel.is_set():
                raise openligadb_source.OpenLigaDBCancelled()
            self._update(stage="activating")
            installed = openligadb_state.install_generation(staging, manifest["generation_id"])
            pointer = openligadb_state.activate_generation(
                installed.name, activated_at_utc=openligadb_source.utc_z()
            )
            self._record_success(state, snapshot, activated=True)
            self._finish(
                {
                    "activated": True,
                    "active_generation_id": installed.name,
                    "previous_generation_id": pointer.get("previous_generation_id"),
                    "content_revision": snapshot["content_revision"],
                    "capabilities": snapshot["capabilities"],
                }
            )
        except openligadb_source.OpenLigaDBCancelled:
            openligadb_state.clean_staging(staging)
            state["health"] = "ready" if openligadb_state.active_database() else "unavailable"
            openligadb_state.save_state(state)
            self._update(state="cancelled", stage="done", error=None)
        except openligadb_source.OpenLigaDBConflict as exc:
            quarantine = openligadb_state.quarantine_dir() / job_id
            quarantine.parent.mkdir(parents=True, exist_ok=True)
            if staging.exists():
                os.replace(staging, quarantine)
            self._record_failure(state, exc)
            self._fail(exc.code, str(exc), retryable=False)
        except openligadb_source.OpenLigaDBError as exc:
            openligadb_state.clean_staging(staging)
            self._record_failure(state, exc)
            self._fail(exc.code, str(exc), retryable=exc.retryable)
        except (OSError, ValueError, sqlite3.Error) as exc:
            openligadb_state.clean_staging(staging)
            code = "disk_full" if isinstance(exc, OSError) and exc.errno == 28 else "refresh_failed"
            wrapped = openligadb_source.OpenLigaDBError(code, str(exc))
            self._record_failure(state, wrapped)
            self._fail(code, str(exc), retryable=True)

    def _record_success(
        self, state: dict[str, Any], snapshot: dict[str, Any], *, activated: bool
    ) -> None:
        state["health"] = "ready"
        state["last_checked_at_utc"] = snapshot["captured_at_utc"]
        if activated:
            state["last_activated_at_utc"] = openligadb_source.utc_z()
        state["next_check_after_utc"] = openligadb_source.utc_z(
            datetime.now(UTC) + timedelta(seconds=openligadb_source.DEFAULT_INTERVAL_SECONDS)
        )
        state["failure_count"] = 0
        state["capabilities"] = snapshot["capabilities"]
        state["content_revision"] = snapshot["content_revision"]
        state["last_error"] = None
        openligadb_state.save_state(state)

    def _record_failure(
        self, state: dict[str, Any], error: openligadb_source.OpenLigaDBError
    ) -> None:
        failures = int(state.get("failure_count") or 0) + 1
        delay = _BACKOFF_SECONDS[min(failures - 1, len(_BACKOFF_SECONDS) - 1)]
        state["health"] = "conflict" if error.code == "source_conflict" else "backoff"
        state["failure_count"] = failures
        state["next_check_after_utc"] = openligadb_source.utc_z(
            datetime.now(UTC) + timedelta(seconds=delay)
        )
        state["last_error"] = {
            "code": error.code,
            "message": str(error),
            "retryable": error.retryable,
        }
        openligadb_state.save_state(state)

    def _finish(self, result: dict[str, Any]) -> None:
        self._update(state="done", stage="done", result=result, error=None)

    def _fail(self, code: str, message: str, *, retryable: bool) -> None:
        self._update(
            state="failed",
            stage="done",
            error={"code": code, "message": message, "retryable": retryable},
        )


_COORDINATOR = OpenLigaDBCoordinator()


def coordinator() -> OpenLigaDBCoordinator:
    return _COORDINATOR


def configure(body: dict[str, Any]) -> dict[str, Any]:
    allowed = {"enabled", "refresh_policy", "selected_competitions", "accept_odbl"}
    unknown = sorted(set(body) - allowed)
    if unknown:
        raise ValueError(f"unknown OpenLigaDB settings fields: {unknown}")
    if coordinator().running():
        raise RuntimeError("cancel the running OpenLigaDB refresh before changing settings")
    current = openligadb_state.load_settings()
    enabled = body.get("enabled", current["enabled"])
    if not isinstance(enabled, bool):
        raise ValueError("enabled must be boolean")
    policy = body.get("refresh_policy", current["refresh_policy"])
    selected = body.get("selected_competitions", current["selected_competitions"])
    accepted = current["license_accepted_at_utc"]
    if enabled and accepted is None:
        if body.get("accept_odbl") is not True:
            raise PermissionError("accept_odbl=true is required before enabling OpenLigaDB")
        accepted = openligadb_source.utc_z()
    saved = openligadb_state.save_settings(
        {
            "enabled": enabled,
            "refresh_policy": policy,
            "selected_competitions": selected,
            "license_accepted_at_utc": accepted,
        }
    )
    state = openligadb_state.load_state()
    if not enabled:
        state["health"] = "disabled"
    elif selected != current["selected_competitions"]:
        state["health"] = "stale"
    elif state["health"] == "disabled":
        state["health"] = "ready" if openligadb_state.active_database() else "unavailable"
    openligadb_state.save_state(state)
    return saved


def status() -> dict[str, Any]:
    supported = runtime.openligadb_dir() is not None
    settings = (
        openligadb_state.load_settings() if supported else openligadb_state.default_settings()
    )
    state = openligadb_state.load_state() if supported else openligadb_state.default_state()
    active, using_previous = openligadb_state.active_generation() if supported else (None, False)
    manifest = openligadb_state.verify_generation(active) if active is not None else None
    pointer = openligadb_state.load_pointer() if supported else None
    health = "disabled" if not settings["enabled"] else state.get("health", "unavailable")
    job = coordinator().get() if supported else None
    if (
        health == "refreshing"
        and isinstance(job, dict)
        and isinstance(job.get("error"), dict)
        and job["error"].get("code") == "interrupted"
    ):
        health = "ready" if active is not None else "unavailable"
    active_payload = None
    if active is not None and manifest is not None:
        active_payload = {
            "generation_id": active.name,
            "created_at_utc": manifest["created_at_utc"],
            "activated_at_utc": (pointer or {}).get("activated_at_utc"),
            "season": manifest["season"],
            "content_revision": manifest["content_revision"],
            "database_sha256": manifest["database_sha256"],
            "rollback_available": bool((pointer or {}).get("previous_generation_id")),
            "using_previous_generation": using_previous,
        }
    return {
        "schema_version": "0.1.0",
        "source_id": openligadb_source.SOURCE_ID,
        "overlay_supported": supported,
        "enabled": settings["enabled"],
        "refresh_policy": settings["refresh_policy"],
        "selected_competitions": settings["selected_competitions"],
        "health": health,
        "display_only": True,
        "license": {
            "id": openligadb_source.LICENSE_ID,
            "url": openligadb_source.LICENSE_URL,
            "attribution": openligadb_source.ATTRIBUTION,
            "accepted_at_utc": settings["license_accepted_at_utc"],
        },
        "usage": {
            "display": True,
            "model_training": False,
            "forecast_sealing": False,
            "forecast_settlement": False,
            "calibration": False,
            "exports": False,
        },
        "active_generation": active_payload,
        "capabilities": state.get("capabilities", []),
        "last_checked_at_utc": state.get("last_checked_at_utc"),
        "last_activated_at_utc": state.get("last_activated_at_utc"),
        "next_check_after_utc": state.get("next_check_after_utc"),
        "last_error": state.get("last_error"),
        "job": job,
        "storage_bytes": openligadb_state.storage_bytes() if supported else 0,
    }


def rollback() -> dict[str, Any]:
    pointer = openligadb_state.rollback(activated_at_utc=openligadb_source.utc_z())
    state = openligadb_state.load_state()
    state["health"] = "ready"
    state["last_activated_at_utc"] = pointer["activated_at_utc"]
    state["last_error"] = None
    openligadb_state.save_state(state)
    return {"schema_version": "0.1.0", **pointer}


def delete_all() -> dict[str, Any]:
    if coordinator().running():
        raise RuntimeError("cancel the running OpenLigaDB refresh before deleting data")
    openligadb_state.delete_overlay_data()
    with coordinator()._lock:
        coordinator()._job = None
        coordinator()._thread = None
        coordinator()._cancel = None
    return {
        "schema_version": "0.1.0",
        "deleted": True,
        "source_id": openligadb_source.SOURCE_ID,
    }
