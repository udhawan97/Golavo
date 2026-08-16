from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent


def _load_gate():
    spec = importlib.util.spec_from_file_location(
        "validate_license_isolation", SCRIPTS / "validate_license_isolation.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gate = _load_gate()


def _write_isolated_adapters(root: Path, sportmonks_source: str = "# isolated adapter\n") -> None:
    for relative in gate.ODBL_MODULES:
        adapter = root / relative
        adapter.parent.mkdir(parents=True, exist_ok=True)
        adapter.write_text("# isolated adapter\n", encoding="utf-8")
    provider = root / gate.SPORTMONKS_MODULE
    provider.parent.mkdir(parents=True, exist_ok=True)
    provider.write_text(sportmonks_source, encoding="utf-8")


def test_committed_odbl_policy_imports_and_packaging_are_isolated() -> None:
    gate.validate_policy()
    gate.validate_registries()
    gate.validate_forbidden_sinks()
    gate.validate_import_boundaries()
    gate.validate_packaging()


def test_index_contamination_canary_fails(tmp_path: Path) -> None:
    index = tmp_path / "data" / "index"
    index.mkdir(parents=True)
    (index / "matches_index.meta.json").write_text(
        json.dumps({"built_from": [{"source_id": "openligadb", "license": "ODbL-1.0"}]}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="ODbL source marker|non-CC0"):
        gate.validate_forbidden_sinks(tmp_path)


def test_parquet_provenance_contamination_canary_fails(tmp_path: Path) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    index = tmp_path / "data" / "index"
    index.mkdir(parents=True)
    pq.write_table(
        pa.table({"match_id": ["m_1"], "source_id": ["openligadb"]}),
        index / "matches_index.parquet",
    )
    with pytest.raises(ValueError, match="contains restricted provenance"):
        gate.validate_forbidden_sinks(tmp_path)


def test_sportmonks_artifact_contamination_canary_fails(tmp_path: Path) -> None:
    artifacts = tmp_path / "data" / "artifacts"
    artifacts.mkdir(parents=True)
    (artifacts / "provider.json").write_text(
        json.dumps({"source_id": "sportmonks-v3", "data": []}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Sportmonks source marker"):
        gate.validate_forbidden_sinks(tmp_path)


@pytest.mark.parametrize(
    "provenance",
    [
        {"source_ids": [["sportmonks-v3"]]},
        {"provenance": [{"source_id": "sportmonks-v3"}]},
    ],
)
def test_sportmonks_parquet_artifact_and_package_canaries_fail(
    tmp_path: Path,
    provenance: dict,
) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    artifact = tmp_path / "data" / "artifacts" / "provider.parquet"
    artifact.parent.mkdir(parents=True)
    pq.write_table(
        pa.table({**provenance, "fixture_id": [42]}),
        artifact,
    )
    with pytest.raises(ValueError, match="contains restricted provenance"):
        gate.validate_forbidden_sinks(tmp_path)
    with pytest.raises(ValueError, match="contains restricted provider data"):
        gate.validate_package_tree(tmp_path)


def test_model_and_forecast_sink_cannot_import_overlay(tmp_path: Path) -> None:
    sink = tmp_path / "server" / "golavo_server" / "seal.py"
    sink.parent.mkdir(parents=True)
    sink.write_text("from golavo_server import openligadb_overlay\n", encoding="utf-8")
    _write_isolated_adapters(tmp_path)
    (tmp_path / "core").mkdir()
    (tmp_path / "scripts").mkdir()
    with pytest.raises(ValueError, match="imports the ODbL runtime adapter"):
        gate.validate_import_boundaries(tmp_path)


def test_model_and_forecast_sink_cannot_import_sportmonks(tmp_path: Path) -> None:
    sink = tmp_path / "server" / "golavo_server" / "seal.py"
    sink.parent.mkdir(parents=True)
    sink.write_text("from golavo_server import sportmonks\n", encoding="utf-8")
    _write_isolated_adapters(tmp_path)
    (tmp_path / "core").mkdir()
    (tmp_path / "scripts").mkdir()
    with pytest.raises(ValueError, match="imports the Sportmonks runtime adapter"):
        gate.validate_import_boundaries(tmp_path)


def test_sportmonks_connector_cannot_import_model_sink(tmp_path: Path) -> None:
    _write_isolated_adapters(
        tmp_path,
        sportmonks_source="from golavo_server import seal\n",
    )
    (tmp_path / "core").mkdir()
    (tmp_path / "scripts").mkdir()
    with pytest.raises(ValueError, match="imports forbidden sink"):
        gate.validate_import_boundaries(tmp_path)


def test_release_tree_rejects_database_but_allows_adapter_code(tmp_path: Path) -> None:
    code = tmp_path / "golavo_server" / "openligadb_overlay.py"
    code.parent.mkdir(parents=True)
    code.write_text("# adapter code is allowed\n", encoding="utf-8")
    gate.validate_package_tree(tmp_path)
    database = tmp_path / "Application Support" / "overlays" / "openligadb" / "overlay.sqlite3"
    database.parent.mkdir(parents=True)
    database.write_bytes(b"not really sqlite")
    with pytest.raises(ValueError, match="contains restricted provider data"):
        gate.validate_package_tree(tmp_path)


def test_release_tree_rejects_sportmonks_artifact(tmp_path: Path) -> None:
    artifact = tmp_path / "data" / "artifacts" / "provider.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text('{"source_id":"sportmonks-v3"}', encoding="utf-8")
    with pytest.raises(ValueError, match="contains restricted provider data"):
        gate.validate_package_tree(tmp_path)
