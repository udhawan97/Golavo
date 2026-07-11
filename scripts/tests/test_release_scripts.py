"""Tests for the release tooling: version sync + updater manifest assembly."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bump_version = _load("bump_version")
make_update_manifest = _load("make_update_manifest")


# --- bump_version ------------------------------------------------------------


@pytest.fixture()
def fake_repo(tmp_path: Path) -> Path:
    """A miniature repo containing every version spot the script maintains."""
    v = "0.1.0"
    files = {
        "desktop/src-tauri/tauri.conf.json": f'{{\n  "version": "{v}",\n  "x": 1\n}}\n',
        "desktop/src-tauri/Cargo.toml": (
            f'[package]\nname = "golavo-desktop"\nversion = "{v}"\n\n'
            '[dependencies]\ntauri = { version = "2" }\n'
        ),
        "desktop/src-tauri/Cargo.lock": (
            '[[package]]\nname = "tauri"\nversion = "2.11.5"\n\n'
            f'[[package]]\nname = "golavo-desktop"\nversion = "{v}"\n'
        ),
        "desktop/package.json": f'{{\n  "version": "{v}"\n}}\n',
        "ui/package.json": f'{{\n  "version": "{v}"\n}}\n',
        "docs-site/package.json": f'{{\n  "version": "{v}"\n}}\n',
        "core/pyproject.toml": f'[project]\nversion = "{v}"\ndev = ["pytest==9.1.1"]\n',
        "server/pyproject.toml": f'[project]\nversion = "{v}"\n',
        "core/golavo_core/__init__.py": f'__version__ = "{v}"\n',
        "server/golavo_server/__init__.py": f'__version__ = "{v}"\n',
        # cff-version reproduces the header line the version template must NOT match.
        "CITATION.cff": f'cff-version: 1.2.0\nversion: {v}\ndate-released: "2020-01-01"\n',
    }
    for rel, content in files.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return tmp_path


def test_bump_rewrites_every_spot_and_recheck_passes(fake_repo: Path) -> None:
    assert bump_version.main(["0.2.0", "--root", str(fake_repo)]) == 0
    versions = bump_version.read_versions(fake_repo)
    assert set(versions.values()) == {"0.2.0"}
    # Dependency pins must be untouched.
    assert 'tauri = { version = "2" }' in (fake_repo / "desktop/src-tauri/Cargo.toml").read_text()
    assert 'version = "2.11.5"' in (fake_repo / "desktop/src-tauri/Cargo.lock").read_text()
    assert "pytest==9.1.1" in (fake_repo / "core/pyproject.toml").read_text()
    # The release date follows the bump.
    assert 'date-released: "2020-01-01"' not in (fake_repo / "CITATION.cff").read_text()
    assert bump_version.main(["--check", "v0.2.0", "--root", str(fake_repo)]) == 0


def test_check_fails_when_one_spot_disagrees(fake_repo: Path) -> None:
    spot = fake_repo / "ui/package.json"
    spot.write_text(spot.read_text().replace("0.1.0", "0.0.9"), encoding="utf-8")
    with pytest.raises(SystemExit, match="disagree"):
        bump_version.main(["--check", "--root", str(fake_repo)])


def test_check_fails_on_tag_mismatch(fake_repo: Path) -> None:
    with pytest.raises(SystemExit, match="expected 9.9.9"):
        bump_version.main(["--check", "v9.9.9", "--root", str(fake_repo)])


def test_bump_rejects_garbage_versions(fake_repo: Path) -> None:
    with pytest.raises(SystemExit, match="not a semver"):
        bump_version.main(["lots-of-fun", "--root", str(fake_repo)])


# --- make_update_manifest ----------------------------------------------------


@pytest.fixture()
def fake_dist(tmp_path: Path) -> Path:
    """A dist directory shaped like the publish job's merged artifacts."""
    dist = tmp_path / "dist"
    dist.mkdir()
    artifacts = ["Golavo.app.tar.gz", "Golavo_0.2.0_x64-setup.exe", "Golavo_0.2.0_x64_en-US.msi"]
    for name in artifacts:
        (dist / name).write_bytes(b"binary")
        (dist / f"{name}.sig").write_text(f"sig-of-{name}", encoding="utf-8")
    (dist / "Golavo_0.2.0_aarch64.dmg").write_bytes(b"dmg")  # no .sig — not an updater artifact
    return dist


def _generate(dist: Path) -> Path:
    make_update_manifest.main(
        [
            "generate",
            "--dist",
            str(dist),
            "--version",
            "0.2.0",
            "--tag",
            "v0.2.0",
            "--repo",
            "udhawan97/Golavo",
        ]
    )
    return dist / "latest.json"


def test_generate_covers_all_platforms_and_validates(fake_dist: Path) -> None:
    manifest_path = _generate(fake_dist)
    manifest = json.loads(manifest_path.read_text())
    assert manifest["version"] == "0.2.0"
    assert set(manifest["platforms"]) == set(make_update_manifest.REQUIRED_PLATFORMS)
    # The unversioned mac tarball (and its sig) were normalized on disk.
    assert (fake_dist / "Golavo_0.2.0_aarch64.app.tar.gz").is_file()
    assert (fake_dist / "Golavo_0.2.0_aarch64.app.tar.gz.sig").is_file()
    mac = manifest["platforms"]["darwin-aarch64"]
    assert mac["url"].endswith("/releases/download/v0.2.0/Golavo_0.2.0_aarch64.app.tar.gz")
    assert mac["signature"] == "sig-of-Golavo.app.tar.gz"
    # And the manifest round-trips through validation.
    make_update_manifest.main(
        ["validate", "--manifest", str(manifest_path), "--dist", str(fake_dist), "--tag", "v0.2.0"]
    )


def test_generate_fails_on_missing_signature(fake_dist: Path) -> None:
    (fake_dist / "Golavo_0.2.0_x64-setup.exe.sig").unlink()
    with pytest.raises(SystemExit, match="missing detached signature"):
        _generate(fake_dist)


def test_generate_fails_on_ambiguous_artifacts(fake_dist: Path) -> None:
    (fake_dist / "Golavo_0.2.1_x64-setup.exe").write_bytes(b"impostor")
    with pytest.raises(SystemExit, match="exactly one NSIS installer"):
        _generate(fake_dist)


def test_validate_rejects_bad_pub_date_and_missing_platforms(tmp_path: Path) -> None:
    manifest = tmp_path / "latest.json"
    manifest.write_text(
        json.dumps(
            {
                "version": "0.2.0",
                "pub_date": "yesterday-ish",
                "platforms": {"darwin-aarch64": {"url": "https://x/y", "signature": " "}},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(SystemExit) as excinfo:
        make_update_manifest.main(["validate", "--manifest", str(manifest)])
    message = str(excinfo.value)
    assert "pub_date is not RFC 3339" in message
    assert "missing platform key: windows-x86_64-nsis" in message
    assert "empty signature" in message
