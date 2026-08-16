#!/usr/bin/env python3
"""Structured ODbL and proprietary-provider isolation gate.

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
FORBIDDEN_TEXT = ("openligadb", "odbl-1.0", "sportmonks-v3", "sportmonks")
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
SPORTMONKS_SOURCE_ID = "sportmonks-v3"
SPORTMONKS_MODULE = "server/golavo_server/sportmonks.py"


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
        if any(
            item.get("source_id") == SPORTMONKS_SOURCE_ID
            for item in payload.get("snapshots", [])
        ):
            raise ValueError(f"{relative}: Sportmonks response bytes must not be vendored")
    sportmonks = [
        item for item in registry["sources"] if item.get("source_id") == SPORTMONKS_SOURCE_ID
    ]
    if len(sportmonks) != 1:
        raise ValueError("source registry must contain exactly one Sportmonks entry")
    provider = sportmonks[0]
    if (
        provider.get("classification") != "per-user-context"
        or provider.get("license") != "PROPRIETARY-SUBSCRIPTION"
    ):
        raise ValueError("Sportmonks registry entry weakens the proprietary-data boundary")


def _forbidden_source_marker(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8").casefold()
    except (OSError, UnicodeDecodeError):
        return None
    return next((token for token in FORBIDDEN_TEXT if token in text), None)


def _contains_forbidden_text(path: Path) -> bool:
    return _forbidden_source_marker(path) is not None


def _parquet_restricted_provenance(path: Path) -> str | None:
    try:
        import pyarrow as pa
        import pyarrow.parquet as parquet
    except ImportError as exc:  # pragma: no cover - release/test environments ship pyarrow
        raise ValueError("pyarrow is required to inspect Parquet provenance") from exc
    parquet_file = parquet.ParquetFile(path)
    def provenance_name(name: str) -> bool:
        folded = name.casefold()
        return (
            folded in {
                "source",
                "sources",
                "source_id",
                "source_ids",
                "license",
                "licenses",
                "license_id",
                "license_ids",
            }
            or folded.endswith(("_source_id", "_source_ids", "_license_id", "_license_ids"))
            or "provenance" in folded
        )

    def type_has_provenance(value: pa.DataType) -> bool:
        if pa.types.is_struct(value):
            return any(
                provenance_name(field.name) or type_has_provenance(field.type)
                for field in value
            )
        if (
            pa.types.is_list(value)
            or pa.types.is_large_list(value)
            or pa.types.is_fixed_size_list(value)
        ):
            field = value.value_field
            return provenance_name(field.name) or type_has_provenance(field.type)
        if pa.types.is_map(value):
            return (
                provenance_name(value.key_field.name)
                or provenance_name(value.item_field.name)
                or type_has_provenance(value.key_type)
                or type_has_provenance(value.item_type)
            )
        return False

    provenance_columns = [
        field.name
        for field in parquet_file.schema_arrow
        if provenance_name(field.name) or type_has_provenance(field.type)
    ]
    if not provenance_columns:
        return None
    restricted = FORBIDDEN_TEXT + ("proprietary-subscription",)

    def contains_restricted(value: Any) -> bool:
        if isinstance(value, str):
            folded = value.casefold()
            return any(marker in folded for marker in restricted)
        if isinstance(value, bytes):
            try:
                return contains_restricted(value.decode("utf-8"))
            except UnicodeDecodeError:
                return False
        if isinstance(value, dict):
            return any(contains_restricted(item) for item in value.values())
        if isinstance(value, (list, tuple)):
            return any(contains_restricted(item) for item in value)
        return False

    table = parquet_file.read(columns=provenance_columns)
    for name in provenance_columns:
        if any(contains_restricted(value) for value in table.column(name).to_pylist()):
            return name
    return None


def validate_forbidden_sinks(root: Path = REPO_ROOT) -> None:
    for relative in ("data/index", "data/artifacts", "packs/core-cc0"):
        folder = root / relative
        if not folder.is_dir():
            continue
        for path in folder.rglob("*"):
            if not path.is_file() or path.suffix.casefold() in {".md", ".pyc"}:
                continue
            if path.suffix.casefold() == ".parquet":
                column = _parquet_restricted_provenance(path)
                if column is not None:
                    raise ValueError(
                        f"{path.relative_to(root)} contains restricted provenance in {column}"
                    )
                continue
            marker = _forbidden_source_marker(path)
            if marker is not None:
                label = "Sportmonks" if "sportmonks" in marker else "ODbL"
                raise ValueError(
                    f"{path.relative_to(root)} contains a {label} source marker"
                )
    meta = root / "data/index/matches_index.meta.json"
    if meta.is_file():
        payload = _load(meta)
        for built in payload.get("built_from", []):
            if built.get("license") != "CC0-1.0" or built.get("source_id") in {
                SOURCE_ID,
                SPORTMONKS_SOURCE_ID,
            }:
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
        if SPORTMONKS_SOURCE_ID in text or "sportmonks" in text:
            raise ValueError(f"{path.relative_to(root)} references the Sportmonks adapter")
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
    sportmonks_path = root / SPORTMONKS_MODULE
    if not sportmonks_path.is_file():
        raise ValueError(f"missing isolated module {SPORTMONKS_MODULE}")
    for imported in _imports(sportmonks_path):
        if any(
            imported == item or imported.startswith(item + ".")
            for item in FORBIDDEN_ODBL_IMPORTS
        ):
            raise ValueError(f"{SPORTMONKS_MODULE} imports forbidden sink {imported}")
    provider_text = sportmonks_path.read_text(encoding="utf-8")
    for marker in ("runtime.data_dir(", "data/artifacts", "data/index", "match_index"):
        if marker in provider_text:
            raise ValueError(
                f"{SPORTMONKS_MODULE} references forbidden sink marker {marker!r}"
            )
    for relative in FORBIDDEN_SINK_MODULES:
        path = root / relative
        if not path.is_file():
            continue
        imports = _imports(path)
        if any(name.startswith("golavo_server.openligadb") for name in imports):
            raise ValueError(f"{relative} imports the ODbL runtime adapter")
        if any(name.startswith("golavo_server.sportmonks") for name in imports):
            raise ValueError(f"{relative} imports the Sportmonks runtime adapter")
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
    if "providers/sportmonks" in spec or "sportmonks-response" in spec:
        raise ValueError("PyInstaller spec attempts to bundle Sportmonks data")


def validate_package_tree(package_root: Path) -> None:
    """Optional release-tree canary: reject ODbL and proprietary provider data."""
    for path in package_root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(package_root).as_posix().casefold()
        if (
            relative.endswith("overlay.sqlite3")
            or "/overlays/openligadb/" in f"/{relative}/"
            or "/raw/openligadb/" in f"/{relative}/"
            or "/providers/sportmonks/" in f"/{relative}/"
            or "/raw/sportmonks/" in f"/{relative}/"
            or (
                relative.startswith(
                    ("data/index/", "data/artifacts/", "packs/core-cc0/")
                )
                and _contains_forbidden_text(path)
            )
        ):
            raise ValueError(f"packaged release contains restricted provider data: {relative}")
        restricted_sink = relative.startswith(
            ("data/index/", "data/artifacts/", "packs/core-cc0/")
        )
        if (
            restricted_sink
            and path.suffix.casefold() == ".parquet"
            and _parquet_restricted_provenance(path) is not None
        ):
            raise ValueError(f"packaged release contains restricted provider data: {relative}")


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
    print(
        "structured license isolation: OK "
        "(ODbL/Sportmonks data cannot enter CC0/model sinks)"
    )


if __name__ == "__main__":
    main()
