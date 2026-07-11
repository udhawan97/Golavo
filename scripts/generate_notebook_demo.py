#!/usr/bin/env python3
"""Generate one real-fixture demo artifact + its Commentator's Notebook.

The eight synthetic contract fixtures use invented teams, so they have no history
to compute facts from. This script seals ONE real fixture (France v Morocco from
the retained martj42 snapshot) and computes its deterministic notebook, so the UI
and docs can show the panel over genuine, source-backed facts.

The seal's ``code_git_sha`` is pinned to zeros so the demo artifact id is stable
across commits (mirroring generate_sample_artifacts.py). Outputs go to the UI
mock fixtures and to data/fixtures/notebook_demo/ for reference.
"""

from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "core"))

from golavo_core.artifacts import (  # noqa: E402
    canonical_bytes,
    payload_sha256,
    seal_forecast,
    validate_artifact,
)
from golavo_core.facts import load_side_tables, notebook_for_artifact  # noqa: E402
from golavo_core.ingest import load_matches  # noqa: E402

PACK = REPO_ROOT / "packs/martj42-internationals-273c731492df"
REFERENCE_DIR = REPO_ROOT / "data/fixtures/notebook_demo"
UI_FORECAST_MOCKS = REPO_ROOT / "ui/src/mocks/forecasts"
UI_NOTEBOOK_MOCKS = REPO_ROOT / "ui/src/mocks/notebooks"


def _pin_code_sha(artifact: dict) -> dict:
    """Re-id an artifact after zeroing code_git_sha so the demo id is reproducible."""
    artifact = copy.deepcopy(artifact)
    artifact["model"]["code_git_sha"] = "0000000"
    stable = copy.deepcopy(artifact)
    stable.pop("artifact_id")
    stable["provenance"].pop("payload_sha256")
    artifact["artifact_id"] = f"fa_{hashlib.sha256(canonical_bytes(stable)).hexdigest()[:20]}"
    artifact["provenance"]["payload_sha256"] = payload_sha256(artifact)
    validate_artifact(artifact)
    return artifact


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        sealed_path = seal_forecast(
            pack_dir=PACK,
            output_dir=Path(tmp),
            date="2026-07-09",
            home_team="France",
            away_team="Morocco",
            as_of_utc="2026-07-08T00:00:00Z",
            horizon="T-24h",
        )
        sealed = json.loads(sealed_path.read_text(encoding="utf-8"))

    artifact = _pin_code_sha(sealed)
    artifact_id = artifact["artifact_id"]

    matches = load_matches(PACK)
    goalscorers, shootouts = load_side_tables(PACK)
    notebook = notebook_for_artifact(
        artifact, matches, goalscorers=goalscorers, shootouts=shootouts
    )

    artifact_bytes = canonical_bytes(artifact) + b"\n"
    notebook_text = json.dumps(notebook, indent=2, sort_keys=True) + "\n"

    for directory in (REFERENCE_DIR, UI_FORECAST_MOCKS, UI_NOTEBOOK_MOCKS):
        directory.mkdir(parents=True, exist_ok=True)

    # Reference copies.
    (REFERENCE_DIR / f"{artifact_id}.json").write_bytes(artifact_bytes)
    (REFERENCE_DIR / f"{artifact_id}.notebook.json").write_text(notebook_text, encoding="utf-8")

    # UI mocks. The forecast mock is named with a non-`fa_` prefix so
    # generate_sample_artifacts.py (which wipes fa_*.json) never deletes it.
    (UI_FORECAST_MOCKS / f"notebook_demo_{artifact_id}.json").write_bytes(artifact_bytes)
    (UI_NOTEBOOK_MOCKS / f"{artifact_id}.json").write_text(notebook_text, encoding="utf-8")

    print(f"demo artifact: {artifact_id}")
    print(f"facts: {len(notebook['facts'])}, suppressed: {len(notebook['suppressed'])}")


if __name__ == "__main__":
    main()
