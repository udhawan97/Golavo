"""Read-only FastAPI surface for Golavo Phase 0 artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from golavo_server import __version__

app = FastAPI(title="Golavo", version=__version__)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

REPO_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = REPO_ROOT / "data/artifacts"
EVAL_SUMMARY_PATH = REPO_ROOT / "docs/handoff/eval_summary.json"


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


@app.get("/api/v1/eval/summary")
def eval_summary() -> dict[str, Any]:
    """Serve the frozen Phase 0 evaluation summary."""
    if not EVAL_SUMMARY_PATH.is_file():
        raise HTTPException(status_code=404, detail="evaluation summary not found")
    return _read_json(EVAL_SUMMARY_PATH)
