from __future__ import annotations

from fastapi.testclient import TestClient
from golavo_server import main as server_main
from golavo_server import runtime


def test_capabilities_exposes_honest_phase_zero_contract() -> None:
    response = TestClient(server_main.app).get("/api/v1/capabilities")
    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "0.1.0"
    by_id = {item["competition_id"]: item for item in body["competitions"]}
    ucl = by_id["uefa-champions-league"]
    assert ucl["capabilities"]["results"]["status"] == "planned"
    assert ucl["capabilities"]["simulation"]["status"] == "blocked"
    assert body["refresh_policy"]["byok_api"] == "blocked"
    assert "football-data.org" in body["refresh_policy"]["byok_reason"]


def test_capabilities_is_launch_token_gated() -> None:
    import os

    previous = os.environ.get("GOLAVO_TOKEN")
    os.environ["GOLAVO_TOKEN"] = "phase-zero-token"
    try:
        client = TestClient(server_main.app)
        assert client.get("/api/v1/capabilities").status_code == 401
        response = client.get(
            "/api/v1/capabilities",
            headers={runtime.TOKEN_HEADER: "phase-zero-token"},
        )
        assert response.status_code == 200
    finally:
        if previous is None:
            os.environ.pop("GOLAVO_TOKEN", None)
        else:
            os.environ["GOLAVO_TOKEN"] = previous
