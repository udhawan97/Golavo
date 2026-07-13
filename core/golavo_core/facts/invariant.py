"""The machine-checked guarantee that a fact never touches a number.

Phase 7's whole point is that a fact can inform a reader but must never change a
forecast, probability, or calibration value. That is enforced two ways, both
checkable by a test rather than by discipline:

1. Isolation (static). ``assert_facts_isolated`` parses every module in this
   package and asserts none imports the forecast, model, calibration, or
   artifact-writer code. No code path *can* reach a writer.
2. Immutability (runtime). ``verify_notebook_pipeline_pure`` runs the whole
   notebook + AI-fold pipeline over a real artifact and asserts the artifact's
   forecast/evaluation bytes are unchanged and that folding notebook facts into
   an evidence bundle only *appends* — every engine number keeps its exact value.
"""

from __future__ import annotations

import ast
import copy
import json
from pathlib import Path
from typing import Any

import pandas as pd

# Modules that produce or persist a probability, forecast, or calibration number.
# The facts package must never import any of them.
FORBIDDEN_IMPORT_PREFIXES = (
    "golavo_core.models",
    "golavo_core.calibration",
    "golavo_core.evaluation",
    "golavo_core.artifacts",
)


def _imported_modules(source: str) -> set[str]:
    tree = ast.parse(source)
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module)
    return modules


def assert_facts_isolated(package_dir: Path | None = None) -> None:
    """Fail if any facts module imports a forecast/model/calibration writer."""
    package_dir = package_dir or Path(__file__).resolve().parent
    offenders: list[str] = []
    for path in sorted(package_dir.glob("*.py")):
        for module in _imported_modules(path.read_text(encoding="utf-8")):
            if any(module == p or module.startswith(p + ".") for p in FORBIDDEN_IMPORT_PREFIXES):
                offenders.append(f"{path.name} imports {module}")
    if offenders:
        raise AssertionError(
            "facts package is not isolated from the forecast engine: " + "; ".join(offenders)
        )


def _numbers_view(artifact: dict[str, Any]) -> bytes:
    view = {"forecast": artifact.get("forecast"), "evaluation": artifact.get("evaluation")}
    return json.dumps(view, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def assert_no_number_written(before: dict[str, Any], after: dict[str, Any]) -> None:
    """Fail if the forecast/evaluation numbers changed between two artifact states."""
    if _numbers_view(before) != _numbers_view(after):
        raise AssertionError("a facts code path mutated a forecast/evaluation number")


def verify_notebook_pipeline_pure(
    artifact: dict[str, Any],
    matches: pd.DataFrame,
    *,
    goalscorers: pd.DataFrame | None = None,
    shootouts: pd.DataFrame | None = None,
) -> bool:
    """Run the full notebook + fold pipeline and prove it wrote no engine number."""
    from golavo_core.evidence import build_evidence_bundle

    from .engine import notebook_for_artifact
    from .evidence import notebook_to_evidence

    before = copy.deepcopy(artifact)
    notebook = notebook_for_artifact(
        artifact, matches, goalscorers=goalscorers, shootouts=shootouts
    )
    # The input artifact must be untouched by building the notebook.
    assert_no_number_written(before, artifact)

    # Sealed path keeps base pack ids (its bundle sources carry richer snapshot
    # metadata under the base id); per-dataset scoping is the match-bundle's job.
    extra_facts, extra_numbers, _extra_sources = notebook_to_evidence(
        notebook, scope_datasets=False
    )
    base = build_evidence_bundle(before)
    folded = build_evidence_bundle(before, extra_facts=extra_facts, extra_numbers=extra_numbers)

    # Folding notebook facts only appends: the forecast summary is unchanged and
    # every engine number keeps its id, value, and display exactly.
    if folded["forecast_summary"] != base["forecast_summary"]:
        raise AssertionError("folding notebook facts changed the forecast summary")
    base_numbers = {n["id"]: n for n in base["allowed_numbers"]}
    base_order = [n["id"] for n in base["allowed_numbers"]]
    folded_order = [n["id"] for n in folded["allowed_numbers"]]
    if folded_order[: len(base_order)] != base_order:
        raise AssertionError("folding reordered or dropped an engine number")
    for number in folded["allowed_numbers"]:
        if number["id"] in base_numbers and number != base_numbers[number["id"]]:
            raise AssertionError(f"folding altered engine number {number['id']!r}")
        if number["id"] not in base_numbers and not number["id"].startswith("nb_"):
            raise AssertionError(f"folded number {number['id']!r} is not namespaced")
    return True
