"""The AI-read progress job store: lifecycle, cancel, TTL, and the routes."""

from __future__ import annotations

import pytest

from golavo_server import jobs
from golavo_server.jobs import JobConflict, JobStore


def test_lifecycle_running_to_done() -> None:
    store = JobStore()
    job = store.start("cl-abcdef12")
    assert job.state == "running"
    store.update("cl-abcdef12", stage="writing", detail="writing", counts={"tokens": 5})
    got = store.get("cl-abcdef12")
    assert got.stage == "writing" and got.counts["tokens"] == 5
    assert store.finish("cl-abcdef12") is True
    assert store.get("cl-abcdef12").state == "done"


def test_running_collision_conflicts() -> None:
    store = JobStore()
    store.start("cl-abcdef12")
    with pytest.raises(JobConflict):
        store.start("cl-abcdef12")
    # After it finishes, the same id may start again.
    store.finish("cl-abcdef12")
    assert store.start("cl-abcdef12").state == "running"


def test_cancel_flags_and_update_is_noop_after() -> None:
    store = JobStore()
    store.start("cl-abcdef12")
    assert store.cancel("cl-abcdef12") is True
    assert store.is_cancelled("cl-abcdef12") is True
    # Updates after cancellation are dropped (terminal state).
    store.update("cl-abcdef12", stage="writing")
    assert store.get("cl-abcdef12").stage != "writing"


def test_id_regex() -> None:
    assert jobs.JOB_ID_RE.match("cl-abcdef12")
    assert not jobs.JOB_ID_RE.match("short")
    assert not jobs.JOB_ID_RE.match("has space 1234")


# ---- routes ----------------------------------------------------------------


def _client(monkeypatch, tmp_path):
    import golavo_server.main as server_main
    from fastapi.testclient import TestClient

    return TestClient(server_main.app)


def test_progress_route_404_unknown(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    assert client.get("/api/v1/ai/jobs/cl-doesnotexist1").status_code == 404
    assert client.get("/api/v1/ai/jobs/bad").status_code == 400


def test_cancel_route_reports_missing(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    body = client.post("/api/v1/ai/jobs/cl-missing12345/cancel").json()
    assert body["cancelled"] is False
