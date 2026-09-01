from __future__ import annotations

import json

import pytest

from scripts import release_inventory

SOURCE_SHA = "a" * 40
TARGET = "aarch64-apple-darwin"


def _repo(tmp_path):
    for relative in release_inventory.LOCK_INPUTS:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"locked:{relative}\n", encoding="utf-8")
    return tmp_path


def _packages() -> list[dict[str, str]]:
    return [
        {"name": name, "version": "1.0.0"}
        for name in sorted(release_inventory.REQUIRED_PACKAGES)
    ]


def _sbom(repo, packages=None):
    path = repo / f"release-sbom-{TARGET}.cdx.json"
    path.write_text(
        json.dumps(
            {
                "bomFormat": "CycloneDX",
                "specVersion": "1.5",
                "components": [
                    {"type": "library", "name": entry["name"], "version": entry["version"]}
                    for entry in (packages or _packages())
                ],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return path


def _payload(repo, sbom):
    return {
        "schema_version": release_inventory.SCHEMA_VERSION,
        "source_sha": SOURCE_SHA,
        "target": TARGET,
        "python": "3.12.14",
        "locks": release_inventory.lock_inventory(repo),
        "sbom": release_inventory.sbom_identity(sbom, target=TARGET),
        "packages": _packages(),
    }


def _validate(payload, repo, sbom):
    release_inventory.validate_inventory(
        payload, repo, source_sha=SOURCE_SHA, target=TARGET, sbom=sbom
    )


def test_release_inventory_binds_source_target_locks_sbom_and_packages(tmp_path) -> None:
    repo = _repo(tmp_path)
    sbom = _sbom(repo)

    _validate(_payload(repo, sbom), repo, sbom)


def test_build_inventory_proves_installed_environment_matches_sbom(
    tmp_path, monkeypatch
) -> None:
    repo = _repo(tmp_path)
    sbom = _sbom(repo)
    monkeypatch.setattr(release_inventory, "package_inventory", _packages)
    monkeypatch.setattr(release_inventory.platform, "python_version", lambda: "3.12.14")

    payload = release_inventory.build_inventory(
        repo, source_sha=SOURCE_SHA, target=TARGET, sbom=sbom
    )

    _validate(payload, repo, sbom)


def test_build_inventory_rejects_installed_environment_sbom_mismatch(
    tmp_path, monkeypatch
) -> None:
    repo = _repo(tmp_path)
    sbom = _sbom(repo)
    installed = _packages()
    installed[0]["version"] = "9.9.9"
    monkeypatch.setattr(release_inventory, "package_inventory", lambda: installed)
    monkeypatch.setattr(release_inventory.platform, "python_version", lambda: "3.12.14")

    with pytest.raises(ValueError, match="does not match the release SBOM"):
        release_inventory.build_inventory(
            repo, source_sha=SOURCE_SHA, target=TARGET, sbom=sbom
        )


def test_release_inventory_rejects_input_drift(tmp_path) -> None:
    repo = _repo(tmp_path)
    sbom = _sbom(repo)
    payload = _payload(repo, sbom)
    (repo / release_inventory.LOCK_INPUTS[0]).write_text("changed\n", encoding="utf-8")

    with pytest.raises(ValueError, match="release inputs changed"):
        _validate(payload, repo, sbom)


def test_release_inventory_normalizes_checkout_line_endings(tmp_path) -> None:
    repo = _repo(tmp_path)
    sbom = _sbom(repo)
    payload = _payload(repo, sbom)
    for relative in release_inventory.LOCK_INPUTS:
        path = repo / relative
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))

    _validate(payload, repo, sbom)


def test_release_inventory_rejects_sbom_artifact_drift(tmp_path) -> None:
    repo = _repo(tmp_path)
    sbom = _sbom(repo)
    payload = _payload(repo, sbom)
    sbom.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="SBOM identity changed"):
        _validate(payload, repo, sbom)


def test_release_inventory_rejects_package_sbom_mismatch(tmp_path) -> None:
    repo = _repo(tmp_path)
    sbom = _sbom(repo)
    payload = _payload(repo, sbom)
    payload["packages"][0]["version"] = "9.9.9"

    with pytest.raises(ValueError, match="does not match the release SBOM"):
        _validate(payload, repo, sbom)


def test_sbom_inventory_applies_target_platform_markers(tmp_path) -> None:
    path = tmp_path / f"release-sbom-{TARGET}.cdx.json"
    path.write_text(
        json.dumps(
            {
                "bomFormat": "CycloneDX",
                "specVersion": "1.5",
                "components": [
                    {
                        "type": "library",
                        "name": "mac-only",
                        "version": "1",
                        "properties": [
                            {"name": "uv:package:marker", "value": "sys_platform == 'darwin'"}
                        ],
                    },
                    {
                        "type": "library",
                        "name": "windows-only",
                        "version": "1",
                        "properties": [
                            {"name": "uv:package:marker", "value": "sys_platform == 'win32'"}
                        ],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    assert release_inventory.sbom_inventory(
        path, target=TARGET, python_version="3.12.14"
    ) == [{"name": "mac-only", "version": "1"}]


def test_release_inventory_rejects_missing_required_package(tmp_path) -> None:
    repo = _repo(tmp_path)
    sbom = _sbom(repo)
    payload = _payload(repo, sbom)
    payload["packages"] = payload["packages"][1:]

    with pytest.raises(ValueError, match="incomplete"):
        _validate(payload, repo, sbom)
