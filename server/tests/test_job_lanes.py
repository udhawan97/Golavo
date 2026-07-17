"""Job lanes: each lane owns its own stage vocabulary and id prefix.

The store began as the AI read's own, so its ``Job`` defaulted to an AI stage
("assembling_evidence"). When the World Cup retrospective reused it, both ends of
the app had to patch around that: the endpoint hand-stamped ``stage="replaying"``
immediately after ``start()`` to close the window where a poller would see an AI
stage on a football backtest, and the UI rewrote the AI helper's ``cl-`` job id to
``rt-`` with a regex. A lane makes the vocabulary the caller's to declare, so
there is nothing left to patch around.
"""

from __future__ import annotations

import pytest
from golavo_server import jobs


def test_a_lane_starts_a_job_in_its_own_first_stage() -> None:
    """The leak the retrospective endpoint used to hand-stamp shut: a poller that
    arrives before the first progress tick must never see another lane's stage."""
    lane = jobs.lane("rt", ("replaying", "done"))
    store = jobs.JobStore()

    job = lane.start("rt-abcdef12", store=store)

    assert job.stage == "replaying"
    assert store.get("rt-abcdef12").stage == "replaying"


def test_the_ai_lane_keeps_its_own_first_stage() -> None:
    lane = jobs.AI_LANE
    store = jobs.JobStore()

    job = lane.start("cl-abcdef12", store=store)

    assert job.stage == "assembling_evidence"


def test_a_lane_rejects_an_id_that_is_not_its_own() -> None:
    """A retrospective's cancel door must not stop an AI read that happens to
    share the id space."""
    lane = jobs.lane("rt", ("replaying", "done"))

    assert lane.owns("rt-abcdef12") is True
    assert lane.owns("cl-abcdef12") is False


def test_a_lane_rejects_a_malformed_id() -> None:
    lane = jobs.lane("rt", ("replaying", "done"))

    assert lane.owns("rt-ab") is False  # under the 8-character floor
    assert lane.owns("../etc/passwd") is False


def test_a_lane_mints_ids_in_its_own_space() -> None:
    lane = jobs.lane("rt", ("replaying", "done"))

    minted = lane.mint("abcdef123456")

    assert minted == "rt-abcdef123456"
    assert lane.owns(minted)


def test_a_lane_only_reports_progress_in_its_declared_stages() -> None:
    """A stage outside the lane's vocabulary is a programming error, not a
    silently-published state a UI would have to tolerate."""
    lane = jobs.lane("rt", ("replaying", "done"))
    store = jobs.JobStore()
    lane.start("rt-abcdef12", store=store)

    with pytest.raises(ValueError, match="not a stage"):
        lane.progress("rt-abcdef12", stage="writing", store=store)


def test_lane_progress_updates_stage_detail_and_counts() -> None:
    lane = jobs.lane("rt", ("replaying", "done"))
    store = jobs.JobStore()
    lane.start("rt-abcdef12", store=store)

    lane.progress(
        "rt-abcdef12",
        stage="replaying",
        detail="Backtesting match 3 of 9",
        counts={"completed": 3, "total": 9},
        store=store,
    )

    job = store.get("rt-abcdef12")
    assert job.stage == "replaying"
    assert job.detail == "Backtesting match 3 of 9"
    assert job.counts == {"completed": 3, "total": 9}


def test_run_tracked_finishes_the_job_with_its_result() -> None:
    lane = jobs.lane("rt", ("replaying", "done"))
    store = jobs.JobStore()
    lane.start("rt-abcdef12", store=store)

    returned = lane.run("rt-abcdef12", lambda: {"value": 7}, store=store)

    job = store.get("rt-abcdef12")
    assert returned == {"value": 7}
    assert job.state == "done"
    assert job.to_dict()["result"] == {"value": 7}


def test_run_tracked_fails_the_job_and_reraises() -> None:
    lane = jobs.lane("rt", ("replaying", "done"))
    store = jobs.JobStore()
    lane.start("rt-abcdef12", store=store)

    def boom() -> dict:
        raise RuntimeError("the fit exploded")

    with pytest.raises(RuntimeError):
        lane.run("rt-abcdef12", boom, store=store)

    job = store.get("rt-abcdef12")
    assert job.state == "failed"
    assert "the fit exploded" in job.to_dict()["error"]


def test_run_tracked_never_relabels_a_cancelled_job_as_failed() -> None:
    """Cancellation is cooperative: the worker unwinds by raising, and that raise
    must not overwrite the terminal state the user asked for."""
    lane = jobs.lane("rt", ("replaying", "done"))
    store = jobs.JobStore()
    lane.start("rt-abcdef12", store=store)
    store.cancel("rt-abcdef12")

    def cancelled_unwind() -> dict:
        raise RuntimeError("cancelled")

    with pytest.raises(RuntimeError):
        lane.run("rt-abcdef12", cancelled_unwind, store=store)

    assert store.get("rt-abcdef12").state == "cancelled"


def test_run_tracked_without_a_job_still_returns_the_work() -> None:
    """No job_id means no tracking — the work still runs, exactly as before."""
    lane = jobs.lane("rt", ("replaying", "done"))
    store = jobs.JobStore()

    assert lane.run(None, lambda: {"value": 7}, store=store) == {"value": 7}


def test_is_cancelled_is_false_without_a_job() -> None:
    lane = jobs.lane("rt", ("replaying", "done"))
    store = jobs.JobStore()

    assert lane.is_cancelled(None, store=store) is False
