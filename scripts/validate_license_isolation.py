#!/usr/bin/env python3
"""Structured ODbL isolation gate.

The older shell guard remains a cheap first pass.  This gate loads the source
policy, parses Python imports, inspects registries/manifests/index metadata and
audits the PyInstaller data list so an ODbL response or database cannot reach a
CC0/model/artifact/export sink merely by avoiding a grep spelling.
"""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = "openligadb"
LICENSE_ID = "ODbL-1.0"
FORBIDDEN_TEXT = ("openligadb", "odbl-1.0")
ODBL_MODULES = (
    "server/golavo_server/openligadb_source.py",
    "server/golavo_server/openligadb_state.py",
    "server/golavo_server/openligadb_overlay.py",
    "server/golavo_server/openligadb_jobs.py",
)
FORBIDDEN_ODBL_IMPORTS = (
    "golavo_core",
    "golavo_server.matches",
    "golavo_server.seal",
    "golavo_server.settlement",
    "golavo_server.analytics",
    "golavo_server.analysis",
    "golavo_server.outlook",
    "golavo_server.picks",
    "golavo_server.refresh",
)
FORBIDDEN_SINK_MODULES = (
    "server/golavo_server/matches.py",
    "server/golavo_server/seal.py",
    "server/golavo_server/settlement.py",
    "server/golavo_server/analytics.py",
    "server/golavo_server/analysis.py",
    "server/golavo_server/outlook.py",
    "server/golavo_server/picks.py",
    "server/golavo_server/refresh.py",
)


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_policy(root: Path = REPO_ROOT) -> None:
    policy = _load(root / "packs/overlay-odbl/policy.json")
    if (
        policy.get("source_id") != SOURCE_ID
        or policy.get("license") != LICENSE_ID
        or policy.get("classification") != "odbl-pack"
    ):
        raise ValueError("OpenLigaDB policy source/license classification is invalid")
    distribution = policy.get("distribution") or {}
    if (
        distribution.get("bundled_response_bytes") is not False
        or distribution.get("fetch_per_user") is not True
        or distribution.get("redistributable_export") is not False
    ):
        raise ValueError("OpenLigaDB policy must remain per-user and non-bundled")
    runtime = policy.get("runtime") or {}
    if (
        runtime.get("storage_boundary") != "overlays/openligadb"
        or runtime.get("host") != "api.openligadb.de"
        or runtime.get("methods") != ["GET"]
        or set(runtime.get("competition_shortcuts") or []) != {"bl1", "bl2", "bl3", "dfb"}
    ):
        raise ValueError("OpenLigaDB runtime allowlist drifted")
    forbidden = set(policy.get("forbidden_sinks") or [])
    required = {
        "data/index",
        "data/artifacts",
        "packs/core-cc0",
        "model-training",
        "calibration",
        "forecast-sealing",
        "forecast-settlement",
        "redistributable-export",
    }
    if not required.issubset(forbidden):
        raise ValueError(
            f"OpenLigaDB policy is missing forbidden sinks: {sorted(required - forbidden)}"
        )


def validate_registries(root: Path = REPO_ROOT) -> None:
    registry = _load(root / "data/sources/registry.json")
    matches = [item for item in registry["sources"] if item.get("source_id") == SOURCE_ID]
    if len(matches) != 1:
        raise ValueError("source registry must contain exactly one OpenLigaDB entry")
    entry = matches[0]
    if (
        entry.get("classification") != "odbl-pack"
        or entry.get("license") != LICENSE_ID
        or entry.get("share_alike") is not True
        or (entry.get("overlay") or {}).get("bundled_data") is not False
        or (entry.get("overlay") or {}).get("display_only") is not True
    ):
        raise ValueError("OpenLigaDB registry entry weakens the ODbL boundary")
    for relative in ("packs/snapshots.json", "packs/enrichment.json", "packs/isolated.json"):
        path = root / relative
        if not path.is_file():
            continue
        payload = _load(path)
        if any(item.get("source_id") == SOURCE_ID for item in payload.get("snapshots", [])):
            raise ValueError(f"{relative}: OpenLigaDB response bytes must not be vendored")


def _contains_forbidden_text(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8").casefold()
    except (OSError, UnicodeDecodeError):
        return False
    return any(token in text for token in FORBIDDEN_TEXT)


def validate_forbidden_sinks(root: Path = REPO_ROOT) -> None:
    for relative in ("data/index", "data/artifacts", "packs/core-cc0"):
        folder = root / relative
        if not folder.is_dir():
            continue
        for path in folder.rglob("*"):
            if not path.is_file() or path.suffix.casefold() in {".md", ".parquet", ".pyc"}:
                continue
            if _contains_forbidden_text(path):
                raise ValueError(f"{path.relative_to(root)} contains an ODbL source marker")
    matches_index = root / "data/index/matches_index.parquet"
    if matches_index.is_file():
        try:
            import pyarrow.parquet as parquet
        except ImportError as exc:  # pragma: no cover - release/test environments ship pyarrow
            raise ValueError("pyarrow is required to inspect match-index provenance") from exc
        parquet_file = parquet.ParquetFile(matches_index)
        provenance_columns = [
            name
            for name in parquet_file.schema_arrow.names
            if name == "source_id"
            or name.endswith("_source_id")
            or name in {"license", "license_id"}
        ]
        table = parquet_file.read(columns=provenance_columns)
        for name in provenance_columns:
            values = {
                str(value).casefold()
                for value in table.column(name).to_pylist()
                if value is not None
            }
            if SOURCE_ID in values or LICENSE_ID.casefold() in values:
                raise ValueError(
                    f"data/index/matches_index.parquet contains ODbL provenance in {name}"
                )
    meta = root / "data/index/matches_index.meta.json"
    if meta.is_file():
        payload = _load(meta)
        for built in payload.get("built_from", []):
            if built.get("license") != "CC0-1.0" or built.get("source_id") == SOURCE_ID:
                raise ValueError("match index metadata contains a non-CC0 source")


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
            result.update(f"{node.module}.{alias.name}" for alias in node.names)
    return result


def validate_import_boundaries(root: Path = REPO_ROOT) -> None:
    for path in (root / "core").rglob("*.py"):
        text = path.read_text(encoding="utf-8").casefold()
        if SOURCE_ID in text or "openligadb_" in text:
            raise ValueError(f"{path.relative_to(root)} references the ODbL adapter")
    for relative in ODBL_MODULES:
        path = root / relative
        if not path.is_file():
            raise ValueError(f"missing isolated module {relative}")
        for imported in _imports(path):
            if any(
                imported == item or imported.startswith(item + ".")
                for item in FORBIDDEN_ODBL_IMPORTS
            ):
                raise ValueError(f"{relative} imports forbidden sink {imported}")
        text = path.read_text(encoding="utf-8")
        for marker in ("runtime.data_dir(", "data/artifacts", "data/index", "match_index"):
            if marker in text:
                raise ValueError(f"{relative} references forbidden sink marker {marker!r}")
    for relative in FORBIDDEN_SINK_MODULES:
        path = root / relative
        if not path.is_file():
            continue
        imports = _imports(path)
        if any(name.startswith("golavo_server.openligadb") for name in imports):
            raise ValueError(f"{relative} imports the ODbL runtime adapter")
        text = path.read_text(encoding="utf-8").casefold()
        if "openligadb_" in text or "openligadb." in text:
            raise ValueError(f"{relative} references the ODbL runtime adapter")
    for path in (root / "scripts").glob("build_*.py"):
        imports = _imports(path)
        if any(name.startswith("golavo_server.openligadb") for name in imports):
            raise ValueError(f"{path.relative_to(root)} imports the ODbL runtime adapter")


def validate_packaging(root: Path = REPO_ROOT) -> None:
    spec = (root / "packaging/golavo-sidecar.spec").read_text(encoding="utf-8").casefold()
    forbidden = ("packs/overlay-odbl", "overlays/openligadb", "overlay.sqlite3")
    if any(marker in spec for marker in forbidden):
        raise ValueError("PyInstaller spec attempts to bundle OpenLigaDB data")


def validate_package_tree(package_root: Path) -> None:
    """Optional release-tree canary: reject ODbL databases/raw response files."""
    for path in package_root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(package_root).as_posix().casefold()
        if (
            relative.endswith("overlay.sqlite3")
            or "/overlays/openligadb/" in f"/{relative}/"
            or "/raw/openligadb/" in f"/{relative}/"
            or (relative.startswith("data/index/") and _contains_forbidden_text(path))
        ):
            raise ValueError(f"packaged release contains OpenLigaDB data: {relative}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-root", type=Path)
    args = parser.parse_args()
    validate_policy()
    validate_registries()
    validate_forbidden_sinks()
    validate_import_boundaries()
    validate_packaging()
    if args.package_root:
        validate_package_tree(args.package_root)
    print("structured license isolation: OK (ODbL overlay cannot enter CC0/model sinks)")


if __name__ == "__main__":
    main()
