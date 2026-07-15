from __future__ import annotations

from scripts.build_wyscout_research_pack import build_competition


def event(event_id: int, team: int, kind: str, start: int, end: int, *tags: int):
    return {
        "id": event_id,
        "matchId": 1,
        "teamId": team,
        "eventName": kind,
        "subEventName": "Simple pass" if kind == "Pass" else "Shot",
        "positions": [{"x": start, "y": 50}, {"x": end, "y": 50}],
        "tags": [{"id": tag} for tag in tags],
    }


def test_team_only_artifact_has_disclosed_metrics_and_no_players() -> None:
    artifact = build_competition(
        [
            event(1, 10, "Pass", 10, 40, 1801),
            event(2, 10, "Pass", 40, 60, 1801),
            event(3, 10, "Shot", 80, 100, 101),
            event(4, 20, "Pass", 10, 15),
        ],
        [{"teamsData": {"10": {}, "20": {}}}],
        {10: "Alpha", 20: "Beta"},
        competition_id="test-league",
        competition_name="Test League",
        era="2017/18",
    )
    assert artifact["team_scope"] == "team_aggregate_only"
    assert artifact["coverage"] == {"matches": 1, "events": 4, "teams": 2}
    alpha = artifact["teams"][0]
    assert alpha["team"] == "Alpha"
    assert alpha["progressive_passes_per_match"] == 2
    assert alpha["shots_per_match"] == 1
    assert alpha["goals_per_match"] == 1
    assert all("player" not in key for row in artifact["teams"] for key in row)
