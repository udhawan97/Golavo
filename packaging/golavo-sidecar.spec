# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: freeze the Golavo FastAPI sidecar into one binary.

Onefile, so the result can be a Tauri ``externalBin`` — a single executable
named ``golavo-sidecar-<target-triple>``. It bundles the read-only resources the
server reads at runtime (the ForecastArtifact JSON schema and the vendored
evaluation summaries), preserving their repo-relative layout so
``golavo_core.resources`` resolves them under ``sys._MEIPASS`` when frozen.

Build (from the repo root):
    pyinstaller --clean --noconfirm packaging/golavo-sidecar.spec \
        --distpath packaging/out --workpath packaging/build
"""

import os

from PyInstaller.utils.hooks import collect_submodules

# SPECPATH is injected by PyInstaller and points at packaging/; its parent is the
# repo root. This is robust regardless of the invoking working directory.
ROOT = os.path.dirname(SPECPATH)  # noqa: F821  (SPECPATH is a PyInstaller global)
ENTRY = os.path.join(ROOT, "server", "golavo_server", "sidecar.py")

# Read-only resources, shipped at their repo-relative paths (dest is a directory).
_EVAL_SUMMARIES = (
    "eval_summary.json",
    "eval_summary_epl.json",
    "eval_summary_laliga.json",
    "eval_summary_bundesliga.json",
    "eval_summary_seriea.json",
    "eval_summary_ligue1.json",
)
datas = [
    (os.path.join(ROOT, "docs", "contracts", "forecast_artifact.schema.json"), "docs/contracts"),
    # Phase 5 additive sibling contracts for the optional AI layer.
    (os.path.join(ROOT, "docs", "contracts", "evidence_bundle.schema.json"), "docs/contracts"),
    (os.path.join(ROOT, "docs", "contracts", "ai_narration.schema.json"), "docs/contracts"),
]
datas += [
    (os.path.join(ROOT, "docs", "handoff", name), "docs/handoff") for name in _EVAL_SUMMARIES
]

# uvicorn and the golavo packages import submodules dynamically; collect them so
# the frozen server can actually boot. numpy/pandas/scipy/pyarrow are handled by
# PyInstaller's bundled hooks.
hiddenimports = []
for package in ("uvicorn", "golavo_core", "golavo_server"):
    hiddenimports += collect_submodules(package)

a = Analysis(
    [ENTRY],
    pathex=[os.path.join(ROOT, "core"), os.path.join(ROOT, "server")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib",
        "tkinter",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
        "IPython",
        "notebook",
        "pytest",
        "mypy",
        "ruff",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="golavo-sidecar",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
