"""An in-memory, thread-safe job store for AI-read progress.

The client optionally passes a ``job_id`` (an idempotency key it generates), and
the sidecar records coarse stage progress against it so a separate
``GET /ai/jobs/{id}`` can drive a live progress UI. New clients also pass
``async_job=true``: the POST then returns 202 immediately and the same GET
supplies the final validated result. No ``job_id`` → no tracking, identical to
before.

The store is a process-local singleton guarded by one lock; finished jobs are
pruned after a short TTL, and there is a hard cap so a runaway client can't grow
it without bound. On app close the worker finishes and its job TTL-prunes —
nothing leaks.
"""

from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any

JOB_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{7,63}$")
_TTL_SECONDS = 900.0  # finished/failed jobs pruned after 15 minutes
_MAX_JOBS = 64

# The ordered stages a read passes through. "researching" only appears on a
# web-research run; the UI tolerates a missing stage.
STAGES = ("assembling_evidence", "researching", "writing", "verifying", "done")


class JobConflict(Exception):
    """A job with this id is already running."""


@dataclass
class Job:
    job_id: str
    state: str = "running"  # running | done | failed | cancelled
    stage: str = "assembling_evidence"
    detail: str | None = None
    counts: dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0
    updated_at: float = 0.0
    error: str | None = None
    # The final, already-guarded API envelope. Keeping it with the short-lived
    # job lets the UI collect a slow local-model result without holding one HTTP
    # request open for 5–8 minutes (WebViews may abandon such requests earlier).
    result: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "job_id": self.job_id,
            "state": self.state,
            "stage": self.stage,
            "detail": self.detail,
            "counts": self.counts,
            "elapsed_s": round(max(0.0, time.monotonic() - self.created_at), 3),
        }
        if self.state == "done" and self.result is not None:
            payload["result"] = self.result
        if self.state == "failed" and self.error:
            payload["error"] = self.error
        return payload


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def _prune_locked(self) -> None:
        now = time.monotonic()
        stale = [
            jid
            for jid, job in self._jobs.items()
            if job.state != "running" and now - job.updated_at > _TTL_SECONDS
        ]
        for jid in stale:
            self._jobs.pop(jid, None)
        # Hard cap: drop the oldest finished jobs first.
        if len(self._jobs) > _MAX_JOBS:
            finished = sorted(
                (j for j in self._jobs.values() if j.state != "running"),
                key=lambda j: j.updated_at,
            )
            for job in finished[: len(self._jobs) - _MAX_JOBS]:
                self._jobs.pop(job.job_id, None)

    def start(self, job_id: str) -> Job:
        now = time.monotonic()
        with self._lock:
            self._prune_locked()
            existing = self._jobs.get(job_id)
            if existing is not None and existing.state == "running":
                raise JobConflict(job_id)
            job = Job(job_id=job_id, created_at=now, updated_at=now)
            self._jobs[job_id] = job
            return job

    def update(
        self,
        job_id: str,
        *,
        stage: str | None = None,
        detail: str | None = None,
        counts: dict[str, Any] | None = None,
    ) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.state != "running":
                return  # unknown or already terminal (e.g. cancelled) → no-op
            if stage is not None:
                job.stage = stage
            if detail is not None:
                job.detail = detail
            if counts is not None:
                job.counts = counts
            job.updated_at = time.monotonic()

    def _terminate(
        self,
        job_id: str,
        state: str,
        error: str | None = None,
        result: dict[str, Any] | None = None,
    ) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.state != "running":
                return False
            job.state = state
            job.stage = "done"
            job.error = error
            job.result = result
            job.updated_at = time.monotonic()
            return True

    def finish(self, job_id: str, result: dict[str, Any] | None = None) -> bool:
        return self._terminate(job_id, "done", result=result)

    def fail(self, job_id: str, error: str) -> bool:
        return self._terminate(job_id, "failed", error)

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.state != "running":
                return False
            job.state = "cancelled"
            job.updated_at = time.monotonic()
            return True

    def is_cancelled(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            return job is not None and job.state == "cancelled"

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            self._prune_locked()
            return self._jobs.get(job_id)

    def running_ids(self, *, prefix: str = "") -> list[str]:
        with self._lock:
            self._prune_locked()
            return sorted(
                job_id
                for job_id, job in self._jobs.items()
                if job.state == "running" and job_id.startswith(prefix)
            )


# Process-local singleton.
_STORE = JobStore()


def store() -> JobStore:
    return _STORE
