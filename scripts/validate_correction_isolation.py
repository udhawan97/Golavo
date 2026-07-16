#!/usr/bin/env python3
"""Structured gate preventing local correction claims from becoming source facts."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORRECTION_MODULE_PREFIX = "golavo_server.correction"
FORBIDDEN_SINKS = (
    "core/golavo_core/artifacts.py",
    "core/golavo_core/calibration.py",
    "core/golavo_core/ingest/match_index.py",
    "server/golavo_server/seal.py",
    "server/golavo_server/settlement.py",
    "server/golavo_server/analysis.py",
    "server/golavo_server/analytics.py",
    "server/golavo_server/outlook.py",
    "server/golavo_server/matches.py",
    "scripts/generate_sample_artifacts.py",
)
CORRECTION_MODULES = (
    "server/golavo_server/correction_policy.py",
    "server/golavo_server/correction_sanitize.py",
    "server/golavo_server/correction_store.py",
    "server/golavo_server/correction_validation.py",
    "server/golavo_server/correction_exports.py",
)
FORBIDDEN_CORRECTION_IMPORTS = (
    "golavo_core.artifacts",
    "golavo_core.calibration",
    "golavo_core.models",
    "golavo_server.seal",
    "golavo_server.settlement",
    "golavo_server.analysis",
    "golavo_server.analytics",
    "golavo_server.outlook",
    "golavo_server.openligadb_overlay",
    "golavo_server.openligadb_state",
)
FORBIDDEN_DATA_FIELDS = {
    "correction",
    "corrections",
    "correction_type",
    "proposal_id",
    "local_annotation",
    "license_namespace",
    "verification_level",
}
CORRECTION_ID_PREFIXES = ("cp_", "ce_", "ev_", "cx_")


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    values: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            values.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            values.add(node.module)
            values.update(f"{node.module}.{alias.name}" for alias in node.names)
    return values


def validate_registry(root: Path = ROOT) -> None:
    registry = _load(root / "data/sources/registry.json")
    policies = [item for item in registry["sources"] if isinstance(item.get("corrections"), dict)]
    if not policies:
        raise ValueError("source registry has no correction policies")
    for source in policies:
        policy = source["corrections"]
        if source["license"] == "ODbL-1.0":
            if policy["license_namespace"] != "overlay-odbl-1.0":
                raise ValueError("ODbL correction policy left its isolated namespace")
            if policy["redistributable_export"] is not False:
                raise ValueError("ODbL correction export must remain disabled")
        elif policy["license_namespace"] == "overlay-odbl-1.0":
            raise ValueError("a non-ODbL source entered the ODbL namespace")


def validate_import_boundaries(root: Path = ROOT) -> None:
    for path in (root / "core").rglob("*.py"):
        if any(name.startswith(CORRECTION_MODULE_PREFIX) for name in _imports(path)):
            raise ValueError(f"{path.relative_to(root)} imports local correction state")
    for relative in FORBIDDEN_SINKS:
        path = root / relative
        if not path.is_file():
            continue
        imports = _imports(path)
        if any(name.startswith(CORRECTION_MODULE_PREFIX) for name in imports):
            raise ValueError(f"{relative} imports local correction state")
    for relative in CORRECTION_MODULES:
        path = root / relative
        if not path.is_file():
            raise ValueError(f"missing correction boundary module: {relative}")
        for imported in _imports(path):
            if any(
                imported == forbidden or imported.startswith(forbidden + ".")
                for forbidden in FORBIDDEN_CORRECTION_IMPORTS
            ):
                raise ValueError(f"{relative} imports authoritative/model sink {imported}")


def validate_packaging(root: Path = ROOT) -> None:
    spec = (root / "packaging/golavo-sidecar.spec").read_text(encoding="utf-8")
    build = (root / "packaging/build.sh").read_text(encoding="utf-8")
    for name in (
        "correction_proposal.schema.json",
        "correction_event.schema.json",
        "correction_export.schema.json",
        "correction_api.schema.json",
    ):
        if name not in spec:
            raise ValueError(f"frozen sidecar omits {name}")
    for marker in ("queue.sqlite3", ".golavo-correction.json", "corrections/evidence"):
        if marker in spec:
            raise ValueError(f"PyInstaller spec attempts to bundle correction data: {marker}")
    if "python scripts/validate_correction_isolation.py" not in build:
        raise ValueError("release build does not enforce correction isolation before freezing")


def _validate_structured_value(value: Any, *, relative: str) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).casefold()
            if normalized in FORBIDDEN_DATA_FIELDS or normalized.startswith("correction_"):
                raise ValueError(
                    f"authoritative/bundled sink has correction field: {relative}:{key}"
                )
            _validate_structured_value(item, relative=relative)
    elif isinstance(value, list):
        for item in value:
            _validate_structured_value(item, relative=relative)
    elif isinstance(value, str) and value.casefold().startswith(CORRECTION_ID_PREFIXES):
        raise ValueError(f"authoritative/bundled sink has correction identity: {relative}")


def _validate_match_index(root: Path) -> None:
    parquet = root / "data/index/matches_index.parquet"
    registry_path = root / "data/sources/registry.json"
    if not parquet.is_file() or not registry_path.is_file():
        return
    import pyarrow.parquet as pq

    registry = _load(registry_path)
    allowed_sources = {
        str(item["source_id"])
        for item in registry["sources"]
        if item.get("classification") == "core" and item.get("license") == "CC0-1.0"
    }
    file = pq.ParquetFile(parquet)
    forbidden_columns = {
        name
        for name in file.schema.names
        if name.casefold() in FORBIDDEN_DATA_FIELDS or name.casefold().startswith("correction_")
    }
    if forbidden_columns:
        raise ValueError(f"match index has correction columns: {sorted(forbidden_columns)}")
    source_columns = [name for name in file.schema.names if name.endswith("source_id")]
    table = pq.read_table(parquet, columns=source_columns)
    for column in source_columns:
        observed = {str(value.as_py()) for value in table[column].unique() if value.as_py()}
        unexpected = observed - allowed_sources
        if unexpected:
            raise ValueError(
                f"match index {column} contains non-core source identities: {sorted(unexpected)}"
            )


def validate_repository_sinks(root: Path = ROOT) -> None:
    for relative in ("packs/core-cc0", "data/index", "data/fixtures/sample_artifacts"):
        folder = root / relative
        if not folder.is_dir():
            continue
        for path in folder.rglob("*"):
            if not path.is_file():
                continue
            lowered = path.name.casefold()
            if lowered == "queue.sqlite3" or lowered.endswith(".golavo-correction.json"):
                raise ValueError(f"authoritative/bundled sink contains correction data: {path}")
            if path.suffix.casefold() == ".json":
                _validate_structured_value(
                    _load(path), relative=path.relative_to(root).as_posix()
                )
    _validate_match_index(root)


def validate_package_tree(package_root: Path) -> None:
    for path in package_root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(package_root).as_posix().casefold()
        if (
            relative.endswith("queue.sqlite3")
            or relative.endswith(".golavo-correction.json")
            or "/corrections/evidence/" in f"/{relative}/"
        ):
            raise ValueError(f"packaged release contains user correction data: {relative}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-root", type=Path)
    args = parser.parse_args()
    validate_registry()
    validate_import_boundaries()
    validate_packaging()
    validate_repository_sinks()
    if args.package_root:
        validate_package_tree(args.package_root)
    print("correction isolation: OK (local claims cannot enter authoritative/model sinks)")


if __name__ == "__main__":
    main()
