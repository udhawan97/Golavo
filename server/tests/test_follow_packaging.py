"""Static release guards for the while-open notification boundary."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_notification_plugin_has_only_explicit_main_window_permissions() -> None:
    capabilities = json.loads(
        (ROOT / "desktop/src-tauri/capabilities/default.json").read_text(encoding="utf-8")
    )
    permissions = capabilities["permissions"]
    assert "notification:allow-is-permission-granted" in permissions
    assert "notification:allow-request-permission" in permissions
    assert "notification:allow-notify" in permissions
    assert "notification:default" not in permissions
    assert capabilities["windows"] == ["main"]


def test_phase5_does_not_add_closed_app_execution() -> None:
    paths = [
        ROOT / "desktop/src-tauri/Cargo.toml",
        ROOT / "desktop/src-tauri/tauri.conf.json",
        ROOT / "desktop/src-tauri/capabilities/default.json",
        ROOT / "ui/package.json",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8").casefold() for path in paths)
    for forbidden in ("tauri-plugin-autostart", "launchagent", "login item"):
        assert forbidden not in combined


def test_sidecar_bundles_follow_contract_but_not_follow_database() -> None:
    spec = (ROOT / "packaging/golavo-sidecar.spec").read_text(encoding="utf-8")
    assert "followed_match.schema.json" in spec
    assert "follows.sqlite3" not in spec
