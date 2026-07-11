#!/usr/bin/env python3
"""Validate every committed sample ForecastArtifact against the frozen contract."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "core"))

from golavo_core.artifacts import payload_sha256, validate_artifact  # noqa: E402


def main() -> None:
    paths = sorted((REPO_ROOT / "data/fixtures/sample_artifacts").glob("fa_*.json"))
    if not 6 <= len(paths) <= 10:
        raise ValueError(f"expected 6-10 sample artifacts, found {len(paths)}")
    statuses: set[str] = set()
    for path in paths:
        artifact = json.loads(path.read_text(encoding="utf-8"))
        validate_artifact(artifact)
        if payload_sha256(artifact) != artifact["provenance"]["payload_sha256"]:
            raise ValueError(f"{path}: payload_sha256 mismatch")
        statuses.add(artifact["status"])
    required = {"sealed", "scored", "abstained", "voided"}
    if statuses != required:
        raise ValueError(f"sample statuses mismatch: {sorted(statuses)}")
    print(f"artifacts: OK ({len(paths)} files; {', '.join(sorted(statuses))})")


if __name__ == "__main__":
    main()
