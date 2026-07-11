"""Read-only FastAPI surface for Golavo forecast artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from golavo_core.calibration import calibration_summary

from golavo_server import __version__

app = FastAPI(title="Golavo", version=__version__)
# Loopback dev origins only: 5173 is the primary Vite port, 5174 the secondary
# dev instance (e.g. a live-API session next to the mock one).
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:5174",
        "http://localhost:5174",
    ],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

REPO_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = REPO_ROOT / "data/artifacts"
# Internationals first, then club leagues in customary big-five order. Each file
# is one league's frozen chronological evaluation; leagues are modeled
# independently (no cross-league strength calibration).
EVAL_SUMMARY_PATHS = (
    REPO_ROOT / "docs/handoff/eval_summary.json",
    REPO_ROOT / "docs/handoff/eval_summary_epl.json",
    REPO_ROOT / "docs/handoff/eval_summary_laliga.json",
    REPO_ROOT / "docs/handoff/eval_summary_bundesliga.json",
    REPO_ROOT / "docs/handoff/eval_summary_seriea.json",
    REPO_ROOT / "docs/handoff/eval_summary_ligue1.json",
)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe used by the desktop shell and CI smoke tests."""
    return {"status": "ok", "app": "golavo", "version": __version__}


@app.get("/api/v1/forecasts")
def list_forecasts() -> list[dict[str, Any]]:
    """List immutable forecast artifacts, newest first."""
    if not ARTIFACT_DIR.exists():
        return []
    artifacts = [_read_json(path) for path in ARTIFACT_DIR.glob("fa_*.json")]
    return sorted(
        artifacts,
        key=lambda item: (item["provenance"]["created_at_utc"], item["artifact_id"]),
        reverse=True,
    )


@app.get("/api/v1/forecasts/{artifact_id}")
def get_forecast(artifact_id: str) -> dict[str, Any]:
    """Return one artifact by canonical id."""
    known_paths = {path.stem: path for path in ARTIFACT_DIR.glob("fa_*.json")}
    path = known_paths.get(artifact_id)
    if path is None:
        raise HTTPException(status_code=404, detail="forecast not found")
    return _read_json(path)


@app.get("/api/v1/calibration")
def calibration() -> dict[str, Any]:
    """Serve the real sealed→scored calibration record (never eval backtests).

    The record is recomputed from the immutable ledger on each request, so it
    can never drift from the artifacts it summarizes. An empty ledger yields an
    honest zero-count record rather than an error.
    """
    return calibration_summary(ARTIFACT_DIR)


@app.get("/api/v1/eval/summary")
def eval_summary() -> dict[str, Any]:
    """Serve the combined evaluation summary (international + club folds)."""
    summaries = [_read_json(path) for path in EVAL_SUMMARY_PATHS if path.is_file()]
    if not summaries:
        raise HTTPException(status_code=404, detail="evaluation summary not found")
    folds: list[dict[str, Any]] = []
    for summary in summaries:
        folds.extend(summary.get("folds", []))
    return {
        "schema_version": summaries[0].get("schema_version", "0.1.0"),
        "primary_metric": "log_loss",
        "sources": [summary.get("source_snapshot") for summary in summaries],
        "folds": folds,
    }
