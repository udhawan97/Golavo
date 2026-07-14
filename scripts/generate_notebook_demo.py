#!/usr/bin/env python3
"""Generate one real-fixture demo artifact + its Commentator's Notebook.

The eight synthetic contract fixtures use invented teams, so they have no history
to compute facts from. This script rebuilds the notebook for ONE canonical real
fixture (France v Morocco) from its checked-in, hash-valid demo artifact. Keeping
that artifact as the identity anchor prevents unrelated model evolution from
silently changing the mock route while every fact is regenerated from current
code and pinned packs.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "core"))

from golavo_core.artifacts import canonical_bytes, validate_artifact  # noqa: E402
from golavo_core.facts import load_side_tables, load_wc_history, notebook_for_artifact  # noqa: E402
from golavo_core.ingest import load_matches  # noqa: E402

PACK = REPO_ROOT / "packs/martj42-internationals-273c731492df"
REFERENCE_DIR = REPO_ROOT / "data/fixtures/notebook_demo"
UI_FORECAST_MOCKS = REPO_ROOT / "ui/src/mocks/forecasts"
UI_NOTEBOOK_MOCKS = REPO_ROOT / "ui/src/mocks/notebooks"
DEMO_ARTIFACT_ID = "fa_b44892255616a50d59bb"


def main() -> None:
    artifact = json.loads(
        (REFERENCE_DIR / f"{DEMO_ARTIFACT_ID}.json").read_text(encoding="utf-8")
    )
    validate_artifact(artifact)
    artifact_id = artifact["artifact_id"]

    matches = load_matches(PACK)
    goalscorers, shootouts = load_side_tables(PACK)
    notebook = notebook_for_artifact(
        artifact,
        matches,
        goalscorers=goalscorers,
        shootouts=shootouts,
        wc_history=load_wc_history(),
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
