#!/usr/bin/env python3
"""Generate and verify the exact environment entering the release signer."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import re
import sys
from pathlib import Path
from typing import Any

from packaging.markers import Marker, default_environment

SCHEMA_VERSION = "golavo-release-inventory-v1"
LOCK_INPUTS = (
    ".github/workflows/release.yml",
    "core/pyproject.toml",
    "server/pyproject.toml",
    "desktop/src-tauri/Cargo.lock",
    "desktop/src-tauri/Cargo.toml",
    "desktop/src-tauri/tauri.conf.json",
    "desktop/src-tauri/tauri.updater.conf.json",
    "desktop/package-lock.json",
    "desktop/package.json",
    "ui/package-lock.json",
    "ui/package.json",
    "rust-toolchain.toml",
    "packaging/build.sh",
    "packaging/golavo-sidecar.spec",
    "packaging/pyproject.toml",
    "packaging/uv.lock",
    "scripts/release_inventory.py",
)
REQUIRED_PACKAGES = {
    "certifi",
    "fastapi",
    "golavo-core",
    "golavo-server",
    "pyinstaller",
    "uvicorn",
}


def _sha256(path: Path) -> str:
    # GitHub's Windows checkout can materialize CRLF even though the reviewed
    # Git blob uses LF. Bind the same text input on both release platforms.
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def _sha256_bytes(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _normalized(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def lock_inventory(repo: Path) -> list[dict[str, str]]:
    locks = []
    for relative in LOCK_INPUTS:
        path = repo / relative
        if not path.is_file():
            raise ValueError(f"release input is missing: {relative}")
        locks.append({"path": relative, "sha256": _sha256(path)})
    return locks


def package_inventory() -> list[dict[str, str]]:
    packages: dict[str, str] = {}
    for distribution in importlib.metadata.distributions():
        raw_name = distribution.metadata.get("Name")
        if not raw_name:
            continue
        name = _normalized(raw_name)
        version = distribution.version
        previous = packages.setdefault(name, version)
        if previous != version:
            raise ValueError(f"multiple installed versions for {name}: {previous}, {version}")
    return [{"name": name, "version": packages[name]} for name in sorted(packages)]


def _target_marker_environment(target: str, python_version: str) -> dict[str, str]:
    environment = default_environment()
    environment.update(
        {
            "implementation_name": "cpython",
            "platform_python_implementation": "CPython",
            "python_full_version": python_version,
            "python_version": ".".join(python_version.split(".")[:2]),
        }
    )
    if target == "aarch64-apple-darwin":
        environment.update(
            {
                "os_name": "posix",
                "platform_machine": "arm64",
                "platform_system": "Darwin",
                "sys_platform": "darwin",
            }
        )
    elif target == "x86_64-pc-windows-msvc":
        environment.update(
            {
                "os_name": "nt",
                "platform_machine": "AMD64",
                "platform_system": "Windows",
                "sys_platform": "win32",
            }
        )
    else:
        raise ValueError(f"unsupported release target: {target}")
    return environment


def sbom_inventory(path: Path, *, target: str, python_version: str) -> list[dict[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("bomFormat") != "CycloneDX" or payload.get("specVersion") != "1.5":
        raise ValueError("release SBOM must be CycloneDX 1.5")
    components = payload.get("components")
    if not isinstance(components, list):
        raise ValueError("release SBOM components are missing")
    environment = _target_marker_environment(target, python_version)
    packages: dict[str, str] = {}
    for component in components:
        if not isinstance(component, dict):
            raise ValueError("release SBOM component is malformed")
        properties = component.get("properties", [])
        if not isinstance(properties, list):
            raise ValueError("release SBOM component properties are malformed")
        marker = next(
            (
                entry.get("value")
                for entry in properties
                if isinstance(entry, dict) and entry.get("name") == "uv:package:marker"
            ),
            None,
        )
        if marker is not None:
            if not isinstance(marker, str):
                raise ValueError("release SBOM component marker is malformed")
            if not Marker(marker).evaluate(environment=environment):
                continue
        raw_name = component.get("name")
        version = component.get("version")
        if not isinstance(raw_name, str) or not isinstance(version, str) or not version:
            raise ValueError("release SBOM component identity is malformed")
        name = _normalized(raw_name)
        previous = packages.setdefault(name, version)
        if previous != version:
            raise ValueError(f"release SBOM contains multiple versions for {name}")
    return [{"name": name, "version": packages[name]} for name in sorted(packages)]


def sbom_identity(path: Path, *, target: str) -> dict[str, str]:
    expected_name = f"release-sbom-{target}.cdx.json"
    if path.name != expected_name:
        raise ValueError(f"release SBOM path must end in {expected_name}")
    return {"path": expected_name, "sha256": _sha256_bytes(path)}


def build_inventory(
    repo: Path, *, source_sha: str, target: str, sbom: Path
) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise ValueError("source SHA must be a full lowercase Git commit")
    packages = package_inventory()
    python_version = platform.python_version()
    expected_packages = sbom_inventory(sbom, target=target, python_version=python_version)
    if packages != expected_packages:
        raise ValueError("installed package inventory does not match the release SBOM")
    return {
        "schema_version": SCHEMA_VERSION,
        "source_sha": source_sha,
        "target": target,
        "python": python_version,
        "locks": lock_inventory(repo),
        "sbom": sbom_identity(sbom, target=target),
        "packages": packages,
    }


def validate_inventory(
    payload: dict[str, Any], repo: Path, *, source_sha: str, target: str, sbom: Path
) -> None:
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("release inventory schema is unsupported")
    if payload.get("source_sha") != source_sha or payload.get("target") != target:
        raise ValueError("release inventory identity does not match this build")
    if payload.get("python") != "3.12.14":
        raise ValueError("release inventory must come from pinned Python 3.12.14")
    if payload.get("locks") != lock_inventory(repo):
        raise ValueError("release inputs changed after inventory generation")
    if payload.get("sbom") != sbom_identity(sbom, target=target):
        raise ValueError("release SBOM identity changed after inventory generation")
    packages = payload.get("packages")
    if not isinstance(packages, list) or not all(isinstance(entry, dict) for entry in packages):
        raise ValueError("release package inventory is missing")
    names = [entry.get("name") for entry in packages]
    if names != sorted(set(names)):
        raise ValueError("release package inventory is not unique and sorted")
    missing = sorted(REQUIRED_PACKAGES - set(names))
    if missing:
        raise ValueError(f"release package inventory is incomplete: {', '.join(missing)}")
    if any(
        not isinstance(entry.get("version"), str) or not entry["version"]
        for entry in packages
    ):
        raise ValueError("release package inventory contains an empty version")
    expected_packages = sbom_inventory(sbom, target=target, python_version=payload["python"])
    if packages != expected_packages:
        raise ValueError("installed package inventory does not match the release SBOM")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("generate", "validate"))
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--sbom", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    repo = args.repo.resolve()
    sbom = args.sbom.resolve()
    if args.mode == "generate":
        if args.output is None:
            raise SystemExit("--output is required for generate")
        payload = build_inventory(
            repo, source_sha=args.source_sha, target=args.target, sbom=sbom
        )
        validate_inventory(
            payload, repo, source_sha=args.source_sha, target=args.target, sbom=sbom
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
    else:
        if args.input is None:
            raise SystemExit("--input is required for validate")
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        validate_inventory(
            payload, repo, source_sha=args.source_sha, target=args.target, sbom=sbom
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
