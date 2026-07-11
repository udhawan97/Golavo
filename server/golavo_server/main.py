"""Read-only FastAPI surface for Golavo forecast artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from golavo_server import __version__, runtime

# NB: golavo_core.calibration pulls in numpy/pandas/scipy, which cost ~25s to
# import from the frozen onefile sidecar. It is imported lazily inside the
# calibration handler so /health, /forecasts and /eval/summary — and thus the
# desktop shell's readiness gate and window — come up in a couple of seconds.

app = FastAPI(title="Golavo", version=__version__)


# Per-launch token gate. Registered BEFORE the CORS middleware so CORS stays
# outermost (and thus still tags responses). When GOLAVO_TOKEN is unset — source
# mode and CI — this is a no-op, keeping the API open for `npm run dev` + pytest.
# Preflight (OPTIONS) and the /health liveness probe are always exempt so the
# browser preflight and the shell's readiness gate never need the token.
@app.middleware("http")
async def _require_launch_token(request: Request, call_next: Any) -> Any:
    token = runtime.launch_token()
    if token is not None and request.method != "OPTIONS" and request.url.path.startswith("/api/"):
        if request.headers.get(runtime.TOKEN_HEADER) != token:
            return JSONResponse({"detail": "missing or invalid launch token"}, status_code=401)
    return await call_next(request)


# Loopback dev origins (5173 primary Vite port, 5174 a secondary dev instance)
# plus the Tauri webview origins used by the packaged desktop shell
# (tauri://localhost on macOS/Linux, http(s)://tauri.localhost on Windows).
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:5174",
        "http://localhost:5174",
        "tauri://localhost",
        "http://tauri.localhost",
        "https://tauri.localhost",
    ],
    allow_credentials=False,
    # POST is only used by the optional, off-by-default AI narrative endpoint;
    # the forecast/eval/calibration surface stays strictly read-only (GET).
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Resolved through the bundle-aware resolver so the frozen sidecar finds these
# under sys._MEIPASS. Kept as module globals because the API tests monkeypatch
# them directly; the request handlers read the globals on each call.
ARTIFACT_DIR = runtime.data_dir()
EVAL_SUMMARY_PATHS = runtime.eval_summary_paths()


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
    from golavo_core.calibration import calibration_summary  # lazy: see import note above

    return calibration_summary(ARTIFACT_DIR)


@app.post("/api/v1/forecasts/{artifact_id}/narrative")
async def narrative(artifact_id: str, request: Request) -> dict[str, Any]:
    """Return an OPTIONAL, guard-validated AI narration for one artifact.

    Additive and off by default: with no body (or ``{"provider": "off"}``) this
    returns a ``disabled`` envelope without ever calling a model. The forecast
    endpoints never touch this path, so AI can never block or delay a forecast.
    Every number in an ``ok`` narration is one the deterministic engine already
    produced; anything else falls back to ``local_only``.
    """
    from golavo_core.evidence import build_evidence_bundle  # lazy: pulls the AI guards

    from golavo_server import ai_gateway

    known_paths = {path.stem: path for path in ARTIFACT_DIR.glob("fa_*.json")}
    path = known_paths.get(artifact_id)
    if path is None:
        raise HTTPException(status_code=404, detail="forecast not found")

    try:
        body = await request.json()
    except (ValueError, json.JSONDecodeError):
        body = {}
    if not isinstance(body, dict):
        body = {}

    try:
        config = ai_gateway.resolve_provider(body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    bundle = build_evidence_bundle(_read_json(path))
    envelope = ai_gateway.generate_narration(bundle, config)
    # The UI resolves a claim's source_ids/number_refs against these trusted
    # bundle lookups to render citation chips with the exact engine display value.
    sources = [
        {"source_id": s["source_id"], "kind": s["kind"], "title": s["title"], "url": s["url"]}
        for s in bundle["sources"]
    ]
    numbers = [
        {"id": n["id"], "display": n["display"], "label": n["label"], "unit": n["unit"]}
        for n in bundle["allowed_numbers"]
    ]
    return {
        "artifact_id": artifact_id,
        "bundle_hash": bundle["bundle_hash"],
        "sources": sources,
        "numbers": numbers,
        **envelope.to_dict(),
    }


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
