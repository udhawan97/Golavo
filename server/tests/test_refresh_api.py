from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from golavo_server import main as server_main
from jsonschema import Draft202012Validator, FormatChecker


class FakeCoordinator:
    def __init__(self) -> None:
        self.started = None
        self.job = {
            "schema_version": "0.1.0",
            "job_id": "rj_" + "1" * 32,
            "state": "queued",
            "stage": "queued",
            "mode": "check",
            "trigger": "manual",
            "source_ids": ["martj42-international-results"],
            "created_at_utc": "2026-07-15T00:00:00Z",
            "updated_at_utc": "2026-07-15T00:00:00Z",
            "cancel_requested": False,
            "progress": {},
            "result": None,
            "error": None,
        }

    def start(self, **kwargs):
        self.started = kwargs
        return self.job, False

    def get(self, job_id=None):
        return self.job if job_id in (None, self.job["job_id"]) else None

    def cancel(self, job_id):
        if job_id != self.job["job_id"]:
            return None
        return {**self.job, "cancel_requested": True}


def test_refresh_job_routes(monkeypatch) -> None:
    fake = FakeCoordinator()
    monkeypatch.setattr(server_main.refresh_jobs, "coordinator", lambda: fake)
    client = TestClient(server_main.app)
    started = client.post(
        "/api/v1/data/refresh",
        json={
            "mode": "check",
            "trigger": "manual",
            "source_ids": ["martj42-international-results"],
        },
    )
    assert started.status_code == 202
    job_id = started.json()["job_id"]
    assert client.get(f"/api/v1/data/refresh/{job_id}").status_code == 200
    cancelled = client.post(f"/api/v1/data/refresh/{job_id}/cancel")
    assert cancelled.json()["cancel_requested"] is True
    assert client.get("/api/v1/data/refresh/not-found").status_code == 404


def test_refresh_route_passes_followed_scope_without_client_source_ids(monkeypatch) -> None:
    fake = FakeCoordinator()
    monkeypatch.setattr(server_main.refresh_jobs, "coordinator", lambda: fake)
    response = TestClient(server_main.app).post(
        "/api/v1/data/refresh",
        json={"mode": "refresh", "trigger": "periodic", "scope": "followed"},
    )
    assert response.status_code == 202
    assert fake.started == {
        "mode": "refresh",
        "source_ids": None,
        "trigger": "periodic",
        "scope": "followed",
    }

    invalid = TestClient(server_main.app).post(
        "/api/v1/data/refresh",
        json={
            "mode": "check",
            "scope": "followed",
            "source_ids": ["openfootball-worldcup-json"],
        },
    )
    assert invalid.status_code == 422


def test_refresh_route_rejects_unapproved_source(monkeypatch) -> None:
    class Rejecting(FakeCoordinator):
        def start(self, **kwargs):
            raise ValueError("unapproved source_ids")

    monkeypatch.setattr(server_main.refresh_jobs, "coordinator", lambda: Rejecting())
    response = TestClient(server_main.app).post(
        "/api/v1/data/refresh", json={"source_ids": ["paid-api"]}
    )
    assert response.status_code == 422


def test_rollback_route(monkeypatch) -> None:
    monkeypatch.setattr(
        server_main.refresh_jobs,
        "rollback",
        lambda: {"schema_version": "0.1.0", "active_generation_id": "g_" + "1" * 64},
    )
    response = TestClient(server_main.app).post("/api/v1/data/rollback")
    assert response.status_code == 200
    assert response.json()["active_generation_id"].startswith("g_")


def test_refresh_status_matches_published_contract() -> None:
    schema_path = (
        Path(__file__).resolve().parents[2] / "docs/contracts/data_refresh_api.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    payload = TestClient(server_main.app).get("/api/v1/data/status").json()
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(payload)
