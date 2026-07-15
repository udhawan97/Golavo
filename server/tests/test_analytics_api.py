from __future__ import annotations

from fastapi.testclient import TestClient
from golavo_server import analytics
from golavo_server import main as server_main


def test_competition_analytics_route_preserves_typed_unavailable_states(monkeypatch) -> None:
    monkeypatch.setattr(
        analytics,
        "get_competition_analytics",
        lambda competition_id, as_of_utc=None: {
            "schema_version": "0.1.0",
            "competition_id": competition_id,
            "as_of_utc": as_of_utc,
            "strength_trends": {"status": "available", "teams": []},
            "rest_congestion": {"status": "available", "teams": []},
            "schedule_difficulty": {"status": "blocked", "reason": "fixtures incomplete"},
        },
    )
    response = TestClient(server_main.app).get(
        "/api/v1/analytics/competitions/england-premier-league",
        params={"as_of_utc": "2025-04-15T00:00:00Z"},
    )
    assert response.status_code == 200
    assert response.json()["competition_id"] == "england-premier-league"
    assert response.json()["schedule_difficulty"]["status"] == "blocked"


def test_competition_analytics_route_maps_unknown_ids_to_404(monkeypatch) -> None:
    def fail(_competition_id: str, *, as_of_utc: str | None = None) -> dict:
        del as_of_utc
        raise ValueError("unknown competition_id: missing")

    monkeypatch.setattr(analytics, "get_competition_analytics", fail)
    response = TestClient(server_main.app).get("/api/v1/analytics/competitions/missing")
    assert response.status_code == 404
