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

import glob
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
    (os.path.join(ROOT, "docs", "contracts", "user_pick.schema.json"), "docs/contracts"),
    (os.path.join(ROOT, "docs", "contracts", "followed_match.schema.json"), "docs/contracts"),
    # Phase 5 additive sibling contracts for the optional AI layer.
    (os.path.join(ROOT, "docs", "contracts", "evidence_bundle.schema.json"), "docs/contracts"),
    (os.path.join(ROOT, "docs", "contracts", "ai_narration.schema.json"), "docs/contracts"),
    # Phase 7 CommentatorsNotebook contract: build_notebook(validate=True) reads it
    # at runtime, so a frozen build without it fails every on-demand notebook closed.
    (os.path.join(ROOT, "docs", "contracts", "facts.schema.json"), "docs/contracts"),
    # Phase 0 competition identities and honest feature availability states.
    (os.path.join(ROOT, "docs", "contracts", "competition_catalog.schema.json"), "docs/contracts"),
    # Phase 3 display-only location/rest/travel contract.
    (os.path.join(ROOT, "docs", "contracts", "conditions_snapshot.schema.json"), "docs/contracts"),
    (os.path.join(ROOT, "docs", "contracts", "match_analysis.schema.json"), "docs/contracts"),
    # Historical team-only event research contract.
    (os.path.join(ROOT, "docs", "contracts", "research_team_analytics.schema.json"), "docs/contracts"),
    # Consent-first approved-source refresh: the frozen sidecar validates the
    # same receipts, generations and API envelopes as source mode.
    (os.path.join(ROOT, "docs", "contracts", "source_snapshot.schema.json"), "docs/contracts"),
    (os.path.join(ROOT, "docs", "contracts", "data_generation.schema.json"), "docs/contracts"),
    (os.path.join(ROOT, "docs", "contracts", "data_refresh_state.schema.json"), "docs/contracts"),
    (os.path.join(ROOT, "docs", "contracts", "data_refresh_api.schema.json"), "docs/contracts"),
    # Optional ODbL overlay contract only. No OpenLigaDB response/database bytes
    # or overlay pack directory are ever included in the frozen sidecar.
    (os.path.join(ROOT, "docs", "contracts", "openligadb_overlay_api.schema.json"), "docs/contracts"),
    # Phase 6 ships contracts and code only. User proposals/evidence live under
    # Application Support and are never PyInstaller data inputs.
    (os.path.join(ROOT, "docs", "contracts", "correction_proposal.schema.json"), "docs/contracts"),
    (os.path.join(ROOT, "docs", "contracts", "correction_event.schema.json"), "docs/contracts"),
    (os.path.join(ROOT, "docs", "contracts", "correction_export.schema.json"), "docs/contracts"),
    (os.path.join(ROOT, "docs", "contracts", "correction_api.schema.json"), "docs/contracts"),
    # Phase 7 contracts only. Captured source bytes and candidate databases are
    # user-owned Application Support state and are never bundled.
    (os.path.join(ROOT, "docs", "contracts", "research_run.schema.json"), "docs/contracts"),
    (os.path.join(ROOT, "docs", "contracts", "research_capture.schema.json"), "docs/contracts"),
    (os.path.join(ROOT, "docs", "contracts", "candidate_fact.schema.json"), "docs/contracts"),
    (os.path.join(ROOT, "docs", "contracts", "research_api.schema.json"), "docs/contracts"),
    (os.path.join(ROOT, "data", "sources", "registry.json"), "data/sources"),
    (os.path.join(ROOT, "data", "sources", "registry.schema.json"), "data/sources"),
]
datas += [
    (os.path.join(ROOT, "docs", "handoff", name), "docs/handoff") for name in _EVAL_SUMMARIES
]
# Pinned, compact GeoNames lookup and Natural Earth 1:110m basemap. Raw source
# packs stay in the repository for audit; the frozen app needs only these
# deterministic derived resources (~1.6 MB) and never reaches a map/geocoder API.
datas += [
    (os.path.join(ROOT, "data", "enrichment", name), "data/enrichment")
    for name in ("places.json", "places.meta.json", "world_110m.geojson", "manifest.json")
]
# Reviewed venue registry, exact scoped assignments, and the manifest that
# hashes them together with the enrichment files above. Manual-review queues
# and raw upstream snapshots remain repository audit material, not runtime data.
datas += [
    (os.path.join(ROOT, "data", "context", name), "data/context")
    for name in ("manifest.json", "venue_entities.json", "venue_assignments.json")
]
# Synthetic sample forecasts: a fresh desktop install has an empty ledger, so
# the API serves these until the user has real seals (see runtime.sample_
# artifacts_dir). Kept at their repo-relative layout so the resolver finds them.
datas += [
    (path, "data/fixtures/sample_artifacts")
    for path in glob.glob(os.path.join(ROOT, "data", "fixtures", "sample_artifacts", "*.json"))
]
# CC0 match search index: the frozen 77k-row Parquet plus its meta digest and
# side tables. All sources are CC0-1.0 (guarded by check_license_isolation.sh);
# no ODbL data ships here. Kept at the repo-relative layout so
# golavo_core.resources resolves them under sys._MEIPASS when frozen (~2.4MB).
datas += [
    (os.path.join(ROOT, "data", "index", name), "data/index")
    for name in (
        "matches_index.parquet",
        "matches_index.meta.json",
        "goalscorers.parquet",
        "shootouts.parquet",
        "aliases.json",
    )
]
# CC0 internationals pack: seal.resolve_pack_dir trains an in-app forward forecast
# from the greatest-anchor internationals snapshot, so the frozen app must carry
# that pack AND packs/snapshots.json (which seal.resolve_pack_dir reads to find it).
# Only the internationals source is forward-sealable today (the five openfootball
# leagues share one source_id and can't be told apart), so only its active pack
# ships (~6.7MB). Selecting it dynamically here keeps the freeze correct across
# refreshes without editing the spec. validate_pack re-hashes every manifest-listed
# file, so the whole pack dir is bundled at its repo-relative layout for
# golavo_core.resources to resolve under sys._MEIPASS.
import json as _json  # noqa: E402

_snap_path = os.path.join(ROOT, "packs", "snapshots.json")
datas += [(_snap_path, "packs")]
_isolated_path = os.path.join(ROOT, "packs", "isolated.json")
datas += [(_isolated_path, "packs")]
_research = next(
    e for e in _json.load(open(_isolated_path))["snapshots"]
    if str(e["source_id"]) == "pappalardo-wyscout-events"
)["pack"]
datas += [
    (path, _research)
    for path in glob.glob(os.path.join(ROOT, _research, "*"))
    if os.path.isfile(path)
]
_fjelstul = next(
    e for e in _json.load(open(_isolated_path))["snapshots"]
    if str(e["source_id"]) == "fjelstul-worldcup"
)["pack"]
datas += [
    (path, _fjelstul)
    for path in glob.glob(os.path.join(ROOT, _fjelstul, "*"))
    if os.path.isfile(path)
]
_intl = [
    e for e in _json.load(open(_snap_path))["snapshots"]
    if str(e["source_id"]) == "martj42-international-results"
]
_active = max(
    _intl,
    key=lambda e: (str(e.get("upstream_committed_at_utc") or e["retrieved_at_utc"]), str(e["pack"])),
)["pack"]
datas += [
    (path, _active)
    for path in glob.glob(os.path.join(ROOT, _active, "*"))
    if os.path.isfile(path)
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
