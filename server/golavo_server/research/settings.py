"""Small, explicit local settings file for match research consent."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

DEFAULTS: dict[str, Any] = {
    "schema_version": "0.1.0",
    "enabled": False,
    "retention_days": 30,
    "searxng_enabled": False,
    "searxng_url": None,
}


def read(root: Path) -> dict[str, Any]:
    path = Path(root) / "settings.json"
    try:
        payload = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return dict(DEFAULTS)
    if not isinstance(payload, dict):
        return dict(DEFAULTS)
    enabled = payload.get("enabled")
    retention = payload.get("retention_days")
    searx_enabled = payload.get("searxng_enabled")
    searx_url = payload.get("searxng_url")
    if not isinstance(enabled, bool) or not isinstance(searx_enabled, bool):
        return dict(DEFAULTS)
    if not isinstance(retention, int) or isinstance(retention, bool) or not 1 <= retention <= 90:
        return dict(DEFAULTS)
    if searx_url is not None and (not isinstance(searx_url, str) or len(searx_url) > 500):
        return dict(DEFAULTS)
    return {
        "schema_version": "0.1.0",
        "enabled": enabled,
        "retention_days": retention,
        "searxng_enabled": searx_enabled,
        "searxng_url": searx_url,
    }


def write(root: Path, value: dict[str, Any]) -> dict[str, Any]:
    enabled = value.get("enabled")
    retention = value.get("retention_days", 30)
    searx_enabled = value.get("searxng_enabled", False)
    searx_url = value.get("searxng_url")
    if not isinstance(enabled, bool) or not isinstance(searx_enabled, bool):
        raise ValueError("enabled settings must be boolean")
    if not isinstance(retention, int) or isinstance(retention, bool) or not 1 <= retention <= 90:
        raise ValueError("retention_days must be between 1 and 90")
    if searx_url is not None and (not isinstance(searx_url, str) or len(searx_url) > 500):
        raise ValueError("searxng_url must be a short URL")
    payload = {
        "schema_version": "0.1.0",
        "enabled": enabled,
        "retention_days": retention,
        "searxng_enabled": searx_enabled,
        "searxng_url": searx_url.strip()
        if isinstance(searx_url, str) and searx_url.strip()
        else None,
    }
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(root, 0o700)
    except OSError:
        pass
    with tempfile.NamedTemporaryFile(
        dir=root, prefix=".settings-", delete=False, mode="w", encoding="utf-8"
    ) as handle:
        json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    os.replace(temporary, root / "settings.json")
    return payload
