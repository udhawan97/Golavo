"""Static release guards for private correction data and update survival."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_sidecar_bundles_contracts_but_no_correction_data() -> None:
    spec = (ROOT / "packaging/golavo-sidecar.spec").read_text(encoding="utf-8")
    for name in (
        "correction_proposal.schema.json",
        "correction_event.schema.json",
        "correction_export.schema.json",
        "correction_api.schema.json",
    ):
        assert name in spec
    for forbidden in ("queue.sqlite3", ".golavo-correction.json", "corrections/evidence"):
        assert forbidden not in spec


def test_desktop_update_backup_includes_isolated_correction_root() -> None:
    updater = (ROOT / "desktop/src-tauri/src/updater.rs").read_text(encoding="utf-8")
    assert 'join("corrections")' in updater
    assert 'backup.join("corrections")' in updater
    assert 'recover_component(app, corrections, "corrections")' in updater


def test_native_export_bridge_rejects_odbl_namespace() -> None:
    bridge = (ROOT / "desktop/src-tauri/src/correction_export.rs").read_text(encoding="utf-8")
    assert 'Some("overlay-odbl-1.0")' in bridge
    assert '"overlay-odbl-1.0"' not in bridge.split("const NAMESPACES", 1)[1].split("];", 1)[0]
