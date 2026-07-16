#!/usr/bin/env python3
"""Fail closed if local research can contaminate authoritative data paths."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "data" / "sources" / "registry.json"

# Research is allowed to create an untrusted Phase 6 draft through the API
# composition root. It must never be imported by an authoritative producer.
FORBIDDEN_IMPORT_ROOTS = (
    ROOT / "core",
    ROOT / "server" / "golavo_server" / "analysis.py",
    ROOT / "server" / "golavo_server" / "matches.py",
    ROOT / "server" / "golavo_server" / "seal.py",
    ROOT / "server" / "golavo_server" / "settlement.py",
    ROOT / "server" / "golavo_server" / "refresh.py",
)

# These committed locations may contain only authoritative/redistributable data.
# User-owned data/artifacts is intentionally excluded from this read-only check.
AUTHORITATIVE_JSON_ROOTS = (
    ROOT / "data" / "index",
    ROOT / "packs" / "core-cc0",
    ROOT / "data" / "fixtures" / "sample_artifacts",
)

RESEARCH_ONLY_KEYS = {
    "candidate_id",
    "capture_id",
    "research_run_id",
    "research_capture_id",
    "research_candidate_id",
}


def _python_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(path.rglob("*.py")) if path.is_dir() else []


def _imports_research(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name.startswith("golavo_server.research") for alias in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith("golavo_server.research"):
                return True
            if module == "golavo_server" and any(alias.name == "research" for alias in node.names):
                return True
    return False


def _contains_research_key(value: object) -> bool:
    if isinstance(value, dict):
        if RESEARCH_ONLY_KEYS.intersection(value):
            return True
        return any(_contains_research_key(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_research_key(item) for item in value)
    return False


def _validate_registry(errors: list[str]) -> None:
    payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
    for source in payload["sources"]:
        access = source.get("research_access")
        if not access:
            continue
        source_id = source["source_id"]
        if source.get("license") == "ODbL-1.0" or source.get("classification") == "odbl-pack":
            errors.append(f"{source_id}: ODbL sources cannot be research inputs")
        for pattern in access["path_patterns"]:
            try:
                re.compile(pattern)
            except re.error as exc:
                errors.append(f"{source_id}: invalid path regex {pattern!r}: {exc}")
            if pattern in {".*", "^.*$", "^/.*$", "/.*"}:
                errors.append(f"{source_id}: catch-all research path is forbidden")
        allowed = set(access["permitted_fact_types"])
        if access.get("ai_fallback") and not allowed.issubset({"team_alias", "venue"}):
            errors.append(f"{source_id}: AI fallback exceeds the v1 alias/venue boundary")
        corrections = source.get("corrections") or {}
        if corrections.get("license_namespace") != access["license_namespace"]:
            errors.append(f"{source_id}: research and correction license namespaces differ")
        if not set(access["hosts"]).issubset(set(corrections.get("evidence_hosts", []))):
            errors.append(f"{source_id}: research host is not allowed as correction evidence")


def main() -> int:
    errors: list[str] = []

    for root in FORBIDDEN_IMPORT_ROOTS:
        for path in _python_files(root):
            if _imports_research(path):
                errors.append(f"authoritative module imports research: {path.relative_to(ROOT)}")

    correction_modules = ROOT / "server" / "golavo_server"
    for path in sorted(correction_modules.glob("correction_*.py")):
        if _imports_research(path):
            errors.append(f"correction layer imports research: {path.relative_to(ROOT)}")

    for root in AUTHORITATIVE_JSON_ROOTS:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                errors.append(f"cannot inspect {path.relative_to(ROOT)}: {exc}")
                continue
            if _contains_research_key(payload):
                errors.append(
                    f"research identity found in authoritative JSON: {path.relative_to(ROOT)}"
                )

    _validate_registry(errors)

    production_roots = (ROOT / "server" / "golavo_server", ROOT / "ui" / "src")
    for root in production_roots:
        for path in sorted(
            file for file in root.rglob("*") if file.suffix in {".py", ".ts", ".tsx"}
        ):
            if "duckduckgo" in path.read_text(encoding="utf-8", errors="ignore").casefold():
                errors.append(f"retired DuckDuckGo integration remains in {path.relative_to(ROOT)}")

    spec = (ROOT / "packaging" / "golavo-sidecar.spec").read_text(encoding="utf-8")
    for name in (
        "research_capture.schema.json",
        "candidate_fact.schema.json",
        "research_run.schema.json",
        "research_api.schema.json",
    ):
        if name not in spec:
            errors.append(f"sidecar does not include {name}")
    if re.search(r"(?:research\.sqlite3|control\.sqlite3|/research|\\research)", spec):
        errors.append("sidecar spec appears to include mutable research data")

    if errors:
        for error in errors:
            print(f"research isolation: ERROR: {error}")
        return 1
    print("research isolation: OK (candidates cannot enter authoritative or redistributable paths)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
