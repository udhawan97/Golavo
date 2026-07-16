"""Structured correction isolation rejects model and package contamination."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "validate_correction_isolation.py"
SPEC = importlib.util.spec_from_file_location("validate_correction_isolation", SCRIPT)
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def test_committed_correction_boundaries_are_valid() -> None:
    validator.validate_registry()
    validator.validate_import_boundaries()
    validator.validate_packaging()
    validator.validate_repository_sinks()


def test_package_tree_rejects_user_database_and_export(tmp_path: Path) -> None:
    database = tmp_path / "corrections" / "core-cc0" / "queue.sqlite3"
    database.parent.mkdir(parents=True)
    database.write_bytes(b"private")
    with pytest.raises(ValueError, match="user correction data"):
        validator.validate_package_tree(tmp_path)

    database.unlink()
    export = tmp_path / "data" / "sample.golavo-correction.json"
    export.parent.mkdir(parents=True)
    export.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="user correction data"):
        validator.validate_package_tree(tmp_path)


def test_structured_authoritative_sink_rejects_correction_fields(tmp_path: Path) -> None:
    artifact = tmp_path / "data/fixtures/sample_artifacts/sample.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text('{"match":{"proposal_id":"cp_bad"}}', encoding="utf-8")
    with pytest.raises(ValueError, match="correction field"):
        validator.validate_repository_sinks(tmp_path)
