from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from golavo_server import refresh_state


def _generation(root: Path, digit: str) -> str:
    generation_id = "g_" + digit * 64
    folder = root / "generations" / generation_id
    index = folder / "index"
    index.mkdir(parents=True)
    parquet = b"parquet-" + digit.encode()
    files = {
        "index/matches_index.parquet": parquet,
        "index/matches_index.meta.json": json.dumps(
            {"parquet_sha256": hashlib.sha256(parquet).hexdigest()}
        ).encode(),
        f"raw/martj42-international-results/{digit * 40}/results.csv": b"results",
        f"raw/openfootball-worldcup-json/{digit * 40}/2026/worldcup.json": b"{}",
    }
    artifacts = []
    for relative, payload in files.items():
        path = folder / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        artifacts.append(
            {"path": relative, "sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload)}
        )
    (folder / "generation.json").write_text(
        json.dumps(
            {
                "schema_version": "0.1.0",
                "generation_id": generation_id,
                "created_at_utc": "2026-07-15T00:00:00Z",
                "source_snapshots": [
                    {
                        "schema_version": "0.1.0",
                        "source_id": "martj42-international-results",
                        "repository": "martj42/international_results",
                        "branch": "master",
                        "upstream_ref": digit * 40,
                        "upstream_committed_at_utc": "2026-07-15T00:00:00Z",
                        "retrieved_at_utc": "2026-07-15T00:00:00Z",
                        "etag": None,
                        "license": "CC0-1.0",
                        "files": [
                            {
                                "path": "results.csv",
                                "pinned_url": "https://raw.githubusercontent.com/example",
                                "sha256": hashlib.sha256(b"results").hexdigest(),
                                "bytes": 7,
                                "content_type": "text/csv",
                            }
                        ],
                    },
                    {
                        "schema_version": "0.1.0",
                        "source_id": "openfootball-worldcup-json",
                        "repository": "openfootball/worldcup.json",
                        "branch": "master",
                        "upstream_ref": digit * 40,
                        "upstream_committed_at_utc": "2026-07-15T00:00:00Z",
                        "retrieved_at_utc": "2026-07-15T00:00:00Z",
                        "etag": None,
                        "license": "CC0-1.0",
                        "files": [
                            {
                                "path": "2026/worldcup.json",
                                "pinned_url": "https://raw.githubusercontent.com/example",
                                "sha256": hashlib.sha256(b"{}").hexdigest(),
                                "bytes": 2,
                                "content_type": "application/json",
                            }
                        ],
                    },
                ],
                "capabilities": [],
                "change_summary": {},
                "artifacts": artifacts,
            }
        ),
        encoding="utf-8",
    )
    return generation_id


def _rewrite_artifact_receipt(folder: Path, relative: str) -> None:
    manifest_path = folder / "generation.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload = (folder / relative).read_bytes()
    for entry in manifest["artifacts"]:
        if entry["path"] == relative:
            entry["sha256"] = hashlib.sha256(payload).hexdigest()
            entry["bytes"] = len(payload)
            break
    else:
        raise AssertionError(f"missing artifact receipt: {relative}")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


def test_two_generation_activation_rollback_and_corruption_fallback(
    monkeypatch, tmp_path: Path
) -> None:
    ledger = tmp_path / "app" / "ledger"
    ledger.mkdir(parents=True)
    monkeypatch.setenv("GOLAVO_DATA_DIR", str(ledger))
    root = tmp_path / "app" / "refresh"
    first = _generation(root, "1")
    second = _generation(root, "2")
    refresh_state.activate_generation(first, activated_at_utc="2026-07-15T00:00:00Z")
    pointer = refresh_state.activate_generation(second, activated_at_utc="2026-07-15T01:00:00Z")
    assert pointer["previous_generation_id"] == first
    active, using_previous = refresh_state.active_generation()
    assert active is not None and active.name == second
    assert using_previous is False

    (root / "generations" / second / "index" / "matches_index.parquet").write_bytes(b"corrupt")
    active, using_previous = refresh_state.active_generation()
    assert active is not None and active.name == first
    assert using_previous is True

    rolled = refresh_state.rollback(activated_at_utc="2026-07-15T02:00:00Z")
    assert rolled["active_generation_id"] == first


def test_activation_rejects_parquet_resealed_only_in_generation_manifest(
    monkeypatch, tmp_path: Path
) -> None:
    ledger = tmp_path / "app" / "ledger"
    ledger.mkdir(parents=True)
    monkeypatch.setenv("GOLAVO_DATA_DIR", str(ledger))
    root = tmp_path / "app" / "refresh"
    generation_id = _generation(root, "3")
    folder = root / "generations" / generation_id
    parquet = folder / "index" / "matches_index.parquet"
    parquet.write_bytes(b"coordinated-parquet-tamper")
    _rewrite_artifact_receipt(folder, "index/matches_index.parquet")

    with pytest.raises(ValueError, match="does not match index metadata"):
        refresh_state.activate_generation(
            generation_id, activated_at_utc="2026-07-15T00:00:00Z"
        )
    assert refresh_state.load_pointer() is None


def test_generation_rejects_meta_resealed_only_in_generation_manifest(
    monkeypatch, tmp_path: Path
) -> None:
    ledger = tmp_path / "app" / "ledger"
    ledger.mkdir(parents=True)
    monkeypatch.setenv("GOLAVO_DATA_DIR", str(ledger))
    root = tmp_path / "app" / "refresh"
    generation_id = _generation(root, "4")
    folder = root / "generations" / generation_id
    meta = folder / "index" / "matches_index.meta.json"
    meta.write_text(json.dumps({"parquet_sha256": "0" * 64}), encoding="utf-8")
    _rewrite_artifact_receipt(folder, "index/matches_index.meta.json")

    with pytest.raises(ValueError, match="does not match index metadata"):
        refresh_state.verify_generation(folder)


def test_meta_cross_check_reuses_the_generation_parquet_hash(
    monkeypatch, tmp_path: Path
) -> None:
    ledger = tmp_path / "app" / "ledger"
    ledger.mkdir(parents=True)
    monkeypatch.setenv("GOLAVO_DATA_DIR", str(ledger))
    root = tmp_path / "app" / "refresh"
    generation_id = _generation(root, "5")
    folder = root / "generations" / generation_id
    parquet = folder / "index" / "matches_index.parquet"
    real_sha256 = refresh_state._sha256
    hashed: list[Path] = []

    def recording_sha256(path: Path) -> str:
        hashed.append(path)
        return real_sha256(path)

    monkeypatch.setattr(refresh_state, "_sha256", recording_sha256)
    refresh_state.verify_generation(folder)
    assert hashed.count(parquet) == 1
