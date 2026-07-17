"""An in-memory, thread-safe job store, and the lanes that run work through it.

The client optionally passes a ``job_id`` (an idempotency key it generates), and
the sidecar records coarse stage progress against it so a separate
``GET .../jobs/{id}`` can drive a live progress UI. New clients also pass
``async_job=true``: the POST then returns 202 immediately and the same GET
supplies the final validated result. No ``job_id`` → no tracking, identical to
before.

The store is a process-local singleton guarded by one lock; finished jobs are
pruned after a short TTL, and there is a hard cap so a runaway client can't grow
it without bound. On app close the worker finishes and its job TTL-prunes —
nothing leaks.

A **lane** is a kind of tracked work: the AI read, the World Cup retrospective, a
model download. Each declares its own ordered stage vocabulary and its own job-id
prefix, and owns the start/progress/finish/fail wiring. The store deliberately
knows nothing about stages beyond storing one — it began as the AI read's own, and
when the retrospective reused it, an AI stage ("assembling_evidence") was what a
poller saw on a football backtest until the endpoint hand-stamped over it. A lane
is where that vocabulary belongs, so no caller has to patch a job's state to make
it honest.
"""

from __future__ import annotations

import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

JOB_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{7,63}$")
_TTL_SECONDS = 900.0  # finished/failed jobs pruned after 15 minutes
_MAX_JOBS = 64

# The ordered stages an AI read passes through. "researching" only appears on a
# web-research run; the UI tolerates a missing stage.
STAGES = ("assembling_evidence", "researching", "writing", "verifying", "done")


class JobConflict(Exception):
    """A job with this id is already running."""


@dataclass
class Job:
    job_id: str
    state: str = "running"  # running | done | failed | cancelled
    # Lane-neutral: a job's real first stage is its lane's, seeded by Lane.start().
    # This used to default to the AI read's "assembling_evidence", which is what a
    # poller saw on a retrospective backtest until its endpoint stamped over it.
    stage: str = "queued"
    detail: str | None = None
    counts: dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0
    updated_at: float = 0.0
    error: str | None = None
    # The final, already-guarded API envelope. Keeping it with the short-lived
    # job lets the UI collect a slow local-model result without holding one HTTP
    # request open for 5–8 minutes (WebViews may abandon such requests earlier).
    result: dict[str, Any] | None = None
    # Cancellation is cooperative: the public state becomes ``cancelled``
    # immediately, while the worker may still be unwinding.  Destructive
    # callers (notably research-history purge) must be able to distinguish
    # that interval from a worker that has actually returned.
    worker_active: bool = True

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
            if not job.worker_active and now - job.updated_at > _TTL_SECONDS
        ]
        for jid in stale:
            self._jobs.pop(jid, None)
        # Hard cap: drop the oldest finished jobs first.
        if len(self._jobs) > _MAX_JOBS:
            finished = sorted(
                (j for j in self._jobs.values() if not j.worker_active),
                key=lambda j: j.updated_at,
            )
            for job in finished[: len(self._jobs) - _MAX_JOBS]:
                self._jobs.pop(job.job_id, None)

    def start(
        self,
        job_id: str,
        *,
        stage: str | None = None,
        detail: str | None = None,
        counts: dict[str, Any] | None = None,
    ) -> Job:
        """Track a new job, already showing its opening state.

        Stage, detail and counts are published under the SAME lock that publishes
        the job, so the whole opening state is atomic: there is no window in which a
        poller can see another lane's stage, or a null detail, on a job that has
        only just started.
        """
        now = time.monotonic()
        with self._lock:
            self._prune_locked()
            existing = self._jobs.get(job_id)
            # A cancelled job stays active until its cooperative worker returns.
            # Reusing the id during that unwind would let the old worker finish
            # the replacement job, so active ownership—not public state—is the
            # conflict boundary.
            if existing is not None and existing.worker_active:
                raise JobConflict(job_id)
            job = Job(job_id=job_id, created_at=now, updated_at=now)
            if stage is not None:
                job.stage = stage
            if detail is not None:
                job.detail = detail
            if counts is not None:
                job.counts = counts
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
            if job is None:
                return False
            if job.state == "cancelled":
                # Preserve cancellation as the terminal public result, but
                # record that the cooperative worker has now exited.
                job.worker_active = False
                job.stage = "done"
                job.updated_at = time.monotonic()
                return False
            if job.state != "running":
                return False
            job.state = state
            job.worker_active = False
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
        """Return worker-active ids, including cooperative cancellation unwind."""
        with self._lock:
            self._prune_locked()
            return sorted(
                job_id
                for job_id, job in self._jobs.items()
                if job.worker_active and job_id.startswith(prefix)
            )


# Process-local singleton.
_STORE = JobStore()


def store() -> JobStore:
    return _STORE


@dataclass(frozen=True)
class Lane:
    """One kind of tracked work, with the vocabulary it speaks.

    A lane owns three things the store deliberately does not: which stages exist,
    which job ids belong to it, and the start/progress/finish/fail wiring around a
    unit of work. That keeps every lane's id space and stage set its own, so one
    lane's door can never stop another lane's job and a poller can never be shown a
    stage from a lane it is not watching.
    """

    prefix: str
    stages: tuple[str, ...]

    def mint(self, token: str) -> str:
        """This lane's job id for a client-supplied token."""
        return f"{self.prefix}-{token}"

    def owns(self, job_id: str) -> bool:
        """Whether ``job_id`` is a well-formed id in THIS lane's space."""
        return bool(JOB_ID_RE.match(job_id)) and job_id.startswith(f"{self.prefix}-")

    def start(
        self,
        job_id: str,
        *,
        detail: str | None = None,
        counts: dict[str, Any] | None = None,
        store: JobStore | None = None,
    ) -> Job:
        """Begin tracking, already in this lane's first stage.

        ``detail``/``counts`` are what a poller arriving before the first progress
        tick should be told — published atomically with the job itself.
        """
        return (store or _STORE).start(
            job_id, stage=self.stages[0], detail=detail, counts=counts
        )

    def progress(
        self,
        job_id: str | None,
        *,
        stage: str,
        detail: str | None = None,
        counts: dict[str, Any] | None = None,
        store: JobStore | None = None,
    ) -> None:
        """Record progress. An undeclared stage is a bug, not a UI's problem."""
        if stage not in self.stages:
            raise ValueError(f"{stage!r} is not a stage of the {self.prefix!r} lane")
        if job_id is None:
            return
        (store or _STORE).update(job_id, stage=stage, detail=detail, counts=counts)

    def is_cancelled(self, job_id: str | None, *, store: JobStore | None = None) -> bool:
        return job_id is not None and (store or _STORE).is_cancelled(job_id)

    def cancel(self, job_id: str, *, store: JobStore | None = None) -> bool:
        return (store or _STORE).cancel(job_id)

    def run(
        self,
        job_id: str | None,
        work: Callable[[], Any],
        *,
        store: JobStore | None = None,
    ) -> Any:
        """Run ``work``, keeping the job's terminal state honest either way.

        A raise fails the job and propagates: the caller still owns the HTTP
        answer. Cancellation arrives here as a raise too, and ``fail`` is a no-op on
        an already-cancelled job (:meth:`JobStore._terminate` keeps cancellation as
        the terminal public state), so a cancelled run is never relabelled failed.
        ``job_id`` of None means untracked — the work simply runs.
        """
        target = store or _STORE
        try:
            result = work()
        except Exception as exc:
            if job_id is not None:
                target.fail(job_id, str(exc)[:240])
            raise
        if job_id is not None:
            target.finish(job_id, result=result if isinstance(result, dict) else None)
        return result


def lane(prefix: str, stages: tuple[str, ...]) -> Lane:
    """Declare a lane. Its first stage is what a job starts in."""
    return Lane(prefix=prefix, stages=stages)


# The AI read's lane: the vocabulary the store used to hardcode as every job's
# default, now owned by the one lane that actually speaks it.
AI_LANE = lane("cl", STAGES)

# The World Cup retrospective: minutes of backtesting, its own id space and door.
RETROSPECTIVE_LANE = lane("rt", ("replaying", "done"))

# A user-requested pull of one curated local model.
MODEL_DOWNLOAD_LANE = lane("dl", ("downloading_model", "done"))
