"""Governance checks for vendored, license-isolated data packs."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent


def _load_validate_sources():
    spec = importlib.util.spec_from_file_location(
        "validate_sources", SCRIPTS / "validate_sources.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validate_sources = _load_validate_sources()
validate_isolated_packs = validate_sources.validate_isolated_packs


def _fixture(tmp_path: Path, *, license_id: str = "CC-BY-SA-4.0") -> tuple[dict, Path, Path]:
    pack = tmp_path / "packs" / "isolated-pack"
    pack.mkdir(parents=True)
    payload = b"key,value\n1,history\n"
    (pack / "data.csv").write_bytes(payload)
    manifest = {
        "files": [{"name": "data.csv", "sha256": hashlib.sha256(payload).hexdigest()}],
        "license": license_id,
        "source_id": "isolated-source",
        "upstream_ref": "abc1234",
    }
    manifest_bytes = (json.dumps(manifest, sort_keys=True) + "\n").encode()
    (pack / "manifest.json").write_bytes(manifest_bytes)
    isolated = tmp_path / "packs" / "isolated.json"
    isolated.write_text(
        json.dumps(
            {
                "schema_version": "0.1.0",
                "snapshots": [
                    {
                        "pack": "packs/isolated-pack",
                        "source_id": "isolated-source",
                        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    snapshots = tmp_path / "packs" / "snapshots.json"
    snapshots.write_text('{"schema_version":"0.1.0","snapshots":[]}', encoding="utf-8")
    by_id = {
        "isolated-source": {
            "classification": "by-sa-pack",
            "license": "CC-BY-SA-4.0",
        }
    }
    return by_id, isolated, snapshots


def _validate(tmp_path: Path, by_id: dict, isolated: Path, snapshots: Path) -> None:
    validate_isolated_packs(
        by_id,
        isolated_path=isolated,
        snapshots_path=snapshots,
        repo_root=tmp_path,
    )


def test_isolated_pack_accepts_matching_class_license_and_hashes(tmp_path: Path) -> None:
    by_id, isolated, snapshots = _fixture(tmp_path)
    _validate(tmp_path, by_id, isolated, snapshots)


def test_isolated_pack_rejects_bundleable_class(tmp_path: Path) -> None:
    by_id, isolated, snapshots = _fixture(tmp_path)
    by_id["isolated-source"]["classification"] = "core"
    with pytest.raises(ValueError, match="not isolated-pack safe"):
        _validate(tmp_path, by_id, isolated, snapshots)


def test_isolated_pack_rejects_license_or_hash_drift(tmp_path: Path) -> None:
    by_id, isolated, snapshots = _fixture(tmp_path, license_id="ODbL-1.0")
    with pytest.raises(ValueError, match="manifest license"):
        _validate(tmp_path, by_id, isolated, snapshots)

    by_id, isolated, snapshots = _fixture(tmp_path / "hash")
    (tmp_path / "hash" / "packs" / "isolated-pack" / "data.csv").write_text(
        "changed", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="sha256 mismatch"):
        _validate(tmp_path / "hash", by_id, isolated, snapshots)


def test_isolated_pack_must_be_absent_from_snapshots(tmp_path: Path) -> None:
    by_id, isolated, snapshots = _fixture(tmp_path)
    snapshots.write_text(
        '{"schema_version":"0.1.0","snapshots":[{"pack":"packs/isolated-pack"}]}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="also present in snapshots"):
        _validate(tmp_path, by_id, isolated, snapshots)


def test_committed_fjelstul_pack_is_hash_valid() -> None:
    repo = Path(__file__).resolve().parents[2]
    validate_isolated_packs(validate_sources.validate_registry(), repo_root=repo)
