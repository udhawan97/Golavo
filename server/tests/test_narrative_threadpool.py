"""A1 regression: the forecast-narrative route must run its blocking AI work off
the event loop (``run_in_threadpool``), so an in-flight narration can never freeze
``/health`` or the rest of the API.

The test parks a stubbed narration inside the threadpool (a slow gateway blocked on
a ``threading.Event``) and asserts ``/health`` still answers promptly and the
narration itself returns a correct envelope once released. Mirrors the sealing
setup used by ``test_ai_gateway`` so the whole route runs for real, no live model.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from golavo_core.artifacts import seal_forecast
from golavo_server import ai_gateway
from golavo_server import main as server_main

REPO_ROOT = Path(__file__).resolve().parents[2]
T0_PACK = REPO_ROOT / "packs/martj42-internationals-273c731492df"


@pytest.fixture
def sealed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    ledger = tmp_path / "ledger"
    path = seal_forecast(
        pack_dir=T0_PACK,
        output_dir=ledger,
        date="2026-07-09",
        home_team="France",
        away_team="Morocco",
        as_of_utc="2026-07-08T00:00:00Z",
    )
    monkeypatch.setattr(server_main, "ARTIFACT_DIR", ledger)
    return str(json.loads(path.read_text())["artifact_id"])


def test_health_stays_responsive_while_a_narration_is_in_flight(
    sealed: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    started = threading.Event()
    release = threading.Event()
    real_generate = ai_gateway.generate_narration

    def _slow_generate(bundle, config, **kwargs):  # runs in the threadpool worker
        started.set()
        assert release.wait(timeout=10), "test never released the stubbed narration"
        return real_generate(bundle, config, **kwargs)

    monkeypatch.setattr(ai_gateway, "generate_narration", _slow_generate)

    async def _scenario() -> httpx.Response:
        transport = httpx.ASGITransport(app=server_main.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            narration = asyncio.create_task(
                ac.post(f"/api/v1/forecasts/{sealed}/narrative", json={"provider": "off"})
            )
            # Wait — WITHOUT blocking the loop — until the narration is parked in
            # the threadpool. If the route ran it inline, the loop would be stuck
            # here and this poll would spin out.
            for _ in range(200):
                if started.is_set():
                    break
                await asyncio.sleep(0.02)
            assert started.is_set(), "narration never reached the (stubbed) gateway"

            # The narration is now blocking a threadpool worker. With the fix the
            # event loop is free, so /health answers at once; if the blocking call
            # were still inline, this await could not complete until release.
            t0 = time.monotonic()
            health = await ac.get("/health")
            elapsed = time.monotonic() - t0
            assert health.status_code == 200
            assert health.json()["status"] == "ok"
            assert elapsed < 2.0, f"/health blocked {elapsed:.2f}s during an in-flight narration"

            release.set()
            return await narration

    response = asyncio.run(_scenario())
    # The narration still returns a correct envelope through the threadpool path.
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "disabled"
    assert body["artifact_id"] == sealed


def test_forecast_narrative_async_job_exposes_final_result(sealed: str) -> None:
    client = TestClient(server_main.app)
    job_id = "cl-forecastresult123"
    response = client.post(
        f"/api/v1/forecasts/{sealed}/narrative",
        json={"provider": "off", "job_id": job_id, "async_job": True},
    )
    assert response.status_code == 202
    assert response.json() == {"job_id": job_id, "state": "running"}
    completed = client.get(f"/api/v1/ai/jobs/{job_id}").json()
    assert completed["state"] == "done"
    assert completed["result"]["status"] == "disabled"
    assert completed["result"]["artifact_id"] == sealed
