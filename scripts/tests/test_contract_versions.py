"""Every envelope version, agreed across the three places it is written down.

The sidecar-to-UI contract is stated three times by hand. docs/contracts/*.json
is the declared canon; a Python constant is what the sidecar actually stamps on
a response; ui/src/lib/contract.ts is what the UI accepts, under a header
promising it mirrors the canon "EXACTLY". Nothing checked that promise, and
contract.ts is the most-churned source file in the repo.

A version bumped in one encoding and not the others is the drift that header was
guarding against, and it fails at runtime — a guard rejecting a response the
sidecar considers current. These tests make it fail here instead.

The table is deliberately explicit. It is the one place the correspondence
between a schema, the code that stamps it and the type that consumes it is
written down, and a new schema with no entry fails the coverage test rather than
being silently unchecked.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "core"))
sys.path.insert(0, str(REPO_ROOT / "server"))

CONTRACTS = REPO_ROOT / "docs/contracts"
CONTRACT_TS = REPO_ROOT / "ui/src/lib/contract.ts"

# schema stem -> (python "module:CONSTANT" that stamps it, contract.ts constant)
# A None python owner means the schema pins a shape the sidecar never stamps a
# version onto itself; a None TS constant means the UI has no version gate for it.
OWNERS: dict[str, tuple[str | None, str | None]] = {
    "candidate_fact": ("golavo_server.research.store:SCHEMA_VERSION", None),
    "competition_catalog": ("golavo_core.competitions:CATALOG_SCHEMA_VERSION", None),
    "conditions_snapshot": ("golavo_server.conditions:SCHEMA_VERSION", None),
    "context_entity_registry": (None, None),
    "context_pack": (None, None),
    "context_resolution": (None, None),
    "correction_api": ("golavo_server.correction_store:SCHEMA_VERSION", None),
    "correction_event": ("golavo_server.correction_store:SCHEMA_VERSION", None),
    "correction_export": ("golavo_server.correction_store:SCHEMA_VERSION", None),
    "correction_proposal": ("golavo_server.correction_store:SCHEMA_VERSION", None),
    "data_generation": ("golavo_server.refresh_state:GENERATION_SCHEMA_VERSION", None),
    "data_refresh_api": ("golavo_server.refresh_jobs:JOB_SCHEMA_VERSION", None),
    "data_refresh_state": ("golavo_server.refresh_state:STATE_SCHEMA_VERSION", None),
    "evidence_bundle": ("golavo_core.evidence:MATCH_EVIDENCE_SCHEMA_VERSION", None),
    "facts": ("golavo_core.facts.engine:NOTEBOOK_SCHEMA_VERSION", None),
    "forecast_artifact": ("golavo_core.artifacts:SCHEMA_VERSION", "SCHEMA_VERSION"),
    "match_analysis": ("golavo_core.analysis:ANALYSIS_SCHEMA_VERSION", "ANALYSIS_SCHEMA_VERSION"),
    "openligadb_overlay_api": ("golavo_server.openligadb_jobs:JOB_SCHEMA_VERSION", None),
    "research_api": ("golavo_server.research.store:SCHEMA_VERSION", None),
    "research_capture": ("golavo_server.research.store:SCHEMA_VERSION", None),
    "research_run": ("golavo_server.research.store:SCHEMA_VERSION", None),
    "research_team_analytics": ("golavo_server.research.store:SCHEMA_VERSION", None),
    "season_outlook": ("golavo_core.season_outlook:SEASON_OUTLOOK_SCHEMA_VERSION", None),
    "source_snapshot": (None, None),
    "tournament_outlook": ("golavo_core.outlook:OUTLOOK_SCHEMA_VERSION", None),
    "tournament_retrospective": ("golavo_core.retrospective:RETROSPECTIVE_SCHEMA_VERSION", None),
    # Pins no schema_version of its own; carried inside other envelopes.
    "ai_narration": (None, None),
    "followed_match": ("golavo_server.follows:SCHEMA_VERSION", "FOLLOW_SCHEMA_VERSION"),
    "user_pick": ("golavo_core.picks:PICK_SCHEMA_VERSION", "PICK_SCHEMA_VERSION"),
}


def _schema_versions(stem: str) -> list[str] | None:
    """Every version this schema pins, or None if it pins none.

    Walks the whole document rather than the top level: the follow and pick
    contracts describe several envelopes under ``$defs``, each pinning its own
    ``schema_version``, and a check reading only the root would see nothing and
    pass vacuously.
    """
    schema = json.loads((CONTRACTS / f"{stem}.schema.json").read_text(encoding="utf-8"))
    found: set[str] = set()

    def walk(node: object) -> None:
        if isinstance(node, dict):
            version = node.get("schema_version")
            if isinstance(version, dict):
                pinned = version.get("const") or version.get("enum") or version.get("default")
                if isinstance(pinned, str):
                    found.add(pinned)
                elif isinstance(pinned, list):
                    found.update(str(item) for item in pinned)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(schema)
    return sorted(found) or None


def _python_version(reference: str) -> str:
    import importlib

    module_name, _, constant = reference.partition(":")
    return str(getattr(importlib.import_module(module_name), constant))


def _ts_version(constant: str) -> list[str]:
    source = CONTRACT_TS.read_text(encoding="utf-8")
    single = re.search(rf'export const {constant} = "([^"]+)" as const;', source)
    if single:
        return [single.group(1)]
    listed = re.search(rf"export const {constant} = \[([^\]]+)\] as const;", source)
    if listed:
        return re.findall(r'"([^"]+)"', listed.group(1))
    raise AssertionError(f"contract.ts declares no constant {constant}")


def test_every_schema_has_an_entry() -> None:
    """A new contract cannot be added without saying who stamps and consumes it."""
    on_disk = {path.name.replace(".schema.json", "") for path in CONTRACTS.glob("*.schema.json")}
    assert on_disk == set(OWNERS), {
        "unlisted schemas": sorted(on_disk - set(OWNERS)),
        "listed but absent": sorted(set(OWNERS) - on_disk),
    }


@pytest.mark.parametrize(
    "stem", sorted(stem for stem, (python, _ts) in OWNERS.items() if python is not None)
)
def test_the_sidecar_stamps_the_version_its_schema_pins(stem: str) -> None:
    pinned = _schema_versions(stem)
    if pinned is None:
        pytest.skip(f"{stem} pins no schema_version")
    assert _python_version(OWNERS[stem][0] or "") in pinned, (
        f"{stem}: the sidecar stamps a version its own schema does not allow"
    )


@pytest.mark.parametrize(
    "stem", sorted(stem for stem, (_python, ts) in OWNERS.items() if ts is not None)
)
def test_the_ui_accepts_the_version_its_schema_pins(stem: str) -> None:
    pinned = _schema_versions(stem)
    assert pinned is not None, f"{stem} pins no schema_version for the UI to accept"
    accepted = _ts_version(OWNERS[stem][1] or "")
    assert set(accepted) & set(pinned), (
        f"{stem}: contract.ts accepts {accepted}, the schema pins {pinned}"
    )


def test_the_ui_accepts_every_artifact_version_the_schema_allows() -> None:
    """The artifact envelope is additive; the UI must keep accepting the old one."""
    source = CONTRACT_TS.read_text(encoding="utf-8")
    accepted = re.findall(
        r'"([^"]+)"', re.search(r"ACCEPTED_SCHEMA_VERSIONS = \[([^\]]+)\]", source).group(1)
    )
    assert set(_schema_versions("forecast_artifact") or []) <= set(accepted)
