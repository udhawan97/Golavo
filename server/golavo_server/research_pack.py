"""Read-only access to isolated historical team research artifacts."""

from __future__ import annotations

import json
from typing import Any

from golavo_core import resources
from jsonschema import Draft202012Validator

_SUPPORTED = frozenset(
    {
        "england-premier-league",
        "spain-la-liga",
        "germany-bundesliga",
        "italy-serie-a",
        "france-ligue-1",
        "uefa-euro",
        "fifa-world-cup",
    }
)


def team_analytics(competition_id: str) -> dict[str, Any]:
    """Load and validate one competition-era aggregate; never join it to core."""
    if competition_id not in _SUPPORTED:
        raise ValueError(f"no historical research pack for competition_id {competition_id!r}")
    artifact_path = resources.wyscout_research_pack_path() / f"{competition_id}.json"
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    schema = json.loads(
        resources.research_team_analytics_schema_path().read_text(encoding="utf-8")
    )
    Draft202012Validator(schema).validate(artifact)
    if artifact["competition_id"] != competition_id:
        raise ValueError("research artifact competition identity mismatch")
    return artifact
