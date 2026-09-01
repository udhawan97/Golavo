from __future__ import annotations

import re
import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "release.yml"
LOCK_PATH = ROOT / "packaging" / "uv.lock"


def test_release_actions_and_runtime_versions_are_exactly_pinned() -> None:
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    action_refs = re.findall(r"uses:\s*([^@\s]+)@([^\s#]+)", text)
    assert action_refs
    assert all(re.fullmatch(r"[0-9a-f]{40}", revision) for _action, revision in action_refs)
    assert len(re.findall(r"uses:.*@[0-9a-f]{40}\s+#\s+v\d", text)) == len(action_refs)

    workflow = yaml.safe_load(text)
    python_versions = []
    node_versions = []
    uv_versions = []
    for job in workflow["jobs"].values():
        for step in job.get("steps", []):
            action = step.get("uses", "")
            if action.startswith("actions/setup-python@"):
                python_versions.append(step["with"]["python-version"])
            elif action.startswith("actions/setup-node@"):
                node_versions.append(step["with"]["node-version"])
            elif action.startswith("astral-sh/setup-uv@"):
                uv_versions.append(step["with"]["version"])
    assert python_versions and set(python_versions) == {"3.12.14"}
    assert node_versions and set(node_versions) == {"22.23.2"}
    assert uv_versions and set(uv_versions) == {"0.11.30"}


def test_release_permissions_are_job_local_and_least_privilege() -> None:
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    assert workflow.get("permissions") is None
    assert {
        name: job.get("permissions") for name, job in workflow["jobs"].items()
    } == {
        "prepare": {"contents": "read"},
        "preflight": {"contents": "read"},
        "build": {"contents": "read"},
        "publish": {"contents": "write"},
    }


def test_release_workflow_uses_frozen_lock_and_verifies_sbom_before_signing() -> None:
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "pip install" not in text
    assert text.count("uv sync --project packaging --frozen --python 3.12.14") == 3
    assert "uv export --project packaging --frozen --format cyclonedx1.5" in text
    assert text.count("--sbom ") == 4
    assert text.index("Verify platform inventories before signing and publication") < text.index(
        "Assemble + validate updater manifest"
    )
    assert text.index("Export SBOM, inventory, and verify inputs entering the signer") < text.index(
        "Build sidecar (PyInstaller) + Tauri bundle"
    )


def test_release_lock_hashes_registry_artifacts_and_includes_local_packages() -> None:
    lock = tomllib.loads(LOCK_PATH.read_text(encoding="utf-8"))
    packages = {entry["name"]: entry for entry in lock["package"]}
    assert packages["pyinstaller"]["version"] == "6.22.2"
    assert packages["golavo-core"]["source"] == {"editable": "../core"}
    assert packages["golavo-server"]["source"] == {"editable": "../server"}

    registry_packages = [
        entry for entry in lock["package"] if "registry" in entry.get("source", {})
    ]
    assert registry_packages
    for entry in registry_packages:
        assert entry["sdist"]["hash"].startswith("sha256:")
        assert entry["wheels"]
        assert all(wheel["hash"].startswith("sha256:") for wheel in entry["wheels"])

    assert any("sys_platform == 'win32'" in marker for marker in lock["resolution-markers"])
    for name in ("numpy", "pyarrow", "pydantic-core", "scipy"):
        urls = [wheel["url"] for wheel in packages[name]["wheels"]]
        assert any("macosx" in url and "arm64" in url for url in urls)
        assert any("win_amd64" in url for url in urls)


def test_rust_toolchain_is_exact() -> None:
    toolchain = tomllib.loads((ROOT / "rust-toolchain.toml").read_text(encoding="utf-8"))
    assert toolchain["toolchain"]["channel"] == "1.97.0"
