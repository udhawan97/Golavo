from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from golavo_server.main import app
from jsonschema import Draft202012Validator, FormatChecker


def test_world_cup_history_serves_both_isolated_categories() -> None:
    response = TestClient(app).get("/api/v1/tournaments/world-cup/history")
    assert response.status_code == 200
    body = response.json()
    root = Path(__file__).resolve().parents[2]
    schema = json.loads(
        (root / "docs/contracts/world_cup_history.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(body)

    women, men = body["categories"]
    assert (women["id"], women["tournament_count"], women["first_year"], women["last_year"]) == (
        "women",
        8,
        1991,
        2019,
    )
    assert (men["id"], men["tournament_count"], men["first_year"], men["last_year"]) == (
        "men",
        22,
        1930,
        2022,
    )
    usa = next(row for row in women["pedigree"] if row["team_name"] == "United States")
    assert usa["titles"] == 4
    assert usa["title_years"] == [1991, 1999, 2015, 2019]
    assert women["tournaments"][0]["standings"][0]["team_name"] == "United States"
    assert women["tournaments"][0]["ended_on"] == "2019-07-07"
    assert "ended_at_utc" not in women["tournaments"][0]
    assert body["source"]["upstream_ref"] == "f942c6b"
    assert body["source"]["copyright_notice"] == "© 2022 Joshua C. Fjelstul, Ph.D."
