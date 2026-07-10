"""FastAPI application entry point.

Run in source mode:
    uvicorn golavo_server.main:app --host 127.0.0.1 --port 8000 --app-dir server

Only a health probe exists during the scaffold phase. The desktop shell will
spawn this server on an ephemeral loopback port with a per-launch token.
"""

from __future__ import annotations

from fastapi import FastAPI

from golavo_server import __version__

app = FastAPI(title="Golavo", version=__version__)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe used by the desktop shell and CI smoke tests."""
    return {"status": "ok", "app": "golavo", "version": __version__}
