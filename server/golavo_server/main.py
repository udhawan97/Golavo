"""Read-only FastAPI surface for Golavo forecast artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from jsonschema import ValidationError
from starlette.concurrency import run_in_threadpool

from golavo_server import __version__, analysis, matches, runtime, seal
from golavo_server import picks as pick_service

# Every way a stored artifact can be untrustworthy: hash/id mismatch or bad value
# (ValueError), missing field (KeyError), unreadable file (OSError), or a broken
# schema (ValidationError, which is NOT a ValueError). A read path treats any of
# these as "do not serve this artifact" and fails closed.
_BAD_ARTIFACT = (ValueError, KeyError, OSError, ValidationError)

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
    # PUT/DELETE are the explicit pre-kickoff user-pick mutations. Without them
    # the desktop webview's CORS preflight rejects writes before they reach us.
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Resolved through the bundle-aware resolver so the frozen sidecar finds these
# under sys._MEIPASS. Kept as module globals because the API tests monkeypatch
# them directly; the request handlers read the globals on each call.
ARTIFACT_DIR = runtime.data_dir()
SAMPLE_DIR = runtime.sample_artifacts_dir()
EVAL_SUMMARY_PATHS = runtime.eval_summary_paths()


def _forecasts_dir() -> Path:
    """Where the forecast surface reads from — always the real ledger.

    Synthetic samples are NEVER served as data: an empty ledger honestly shows an
    empty forecast list, and the one teaching example lives inside the in-app
    sealing guide (bundled UI-side), not on the forecast routes. This makes the
    honesty invariant "samples are never passed off as real forecasts" hold at the
    source — a ``#/forecast/fa_<sample-id>`` deep link now 404s honestly rather
    than rendering a synthetic artifact as a real page.
    """
    return ARTIFACT_DIR


def showing_samples() -> bool:
    """Retained for envelope compatibility; the forecast surface never serves
    samples now, so this is always False."""
    return False


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_artifact(path: Path) -> dict[str, Any]:
    """Read and integrity-verify a sealed ForecastArtifact before serving it.

    Never trust an on-disk artifact: recompute its content hash and content id and
    reject a tampered or incoherent file (see golavo_core.artifacts). Imported
    lazily because verification pulls the scientific stack; /health and the
    readiness gate stay light and the sidecar warms this in the background.
    """
    from golavo_core.artifacts import load_verified_artifact

    return load_verified_artifact(path)


def _notebook_evidence(artifact_id: str) -> tuple[list[Any], list[Any]]:
    """Evidence facts + numbers from a precomputed notebook, or ((), ()) if none.

    The notebook sidecar is not integrity-verified (unlike the artifact), so a
    corrupt, truncated, or older-schema file must fail closed: treat it as no
    notebook rather than 500 the optional AI route. The bundle still builds from
    the verified artifact alone. The sealed path keeps base pack ids (its sources
    carry richer snapshot metadata), so per-dataset scoping is off here.
    """
    notebook_path = _forecasts_dir() / "notebooks" / f"{artifact_id}.json"
    if not notebook_path.is_file():
        return [], []
    from golavo_core.facts import notebook_to_evidence  # lazy: pulls the AI guards

    try:
        facts, numbers, _extra = notebook_to_evidence(
            _read_json(notebook_path), scope_datasets=False
        )
        return facts, numbers
    except (OSError, ValueError, KeyError, TypeError):
        return [], []


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe used by the desktop shell and CI smoke tests."""
    return {"status": "ok", "app": "golavo", "version": __version__}


@app.get("/api/v1/meta")
def meta() -> dict[str, Any]:
    """UI hints the frontend can't infer on its own — chiefly whether the
    forecast surface is showing bundled synthetic samples (fresh install) so the
    UI can label them honestly instead of as live data."""
    return {
        "version": __version__,
        "forecast_source": "sample" if showing_samples() else "ledger",
    }


@app.get("/api/v1/ai/local-models")
def ai_local_models(provider: str = "ollama") -> dict[str, Any]:
    """Installed local models (with sizes) for the Fast/Deep model picker.

    Read-only and fail-safe: an unreachable local server yields an empty list, not
    an error, so the Settings UI can show honest "start Ollama / pull a model"
    guidance. Only local providers are probed; anything else returns no models.
    """
    from golavo_server import ai_gateway

    if provider not in ai_gateway.LOCAL_PROVIDERS:
        return {
            "provider": provider,
            "status": "unsupported",
            "models": [],
            "reason": "This provider does not expose local models.",
        }
    try:
        config = ai_gateway.resolve_provider({"provider": provider})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    result = ai_gateway.inspect_local_models(config)
    if provider == "ollama":
        result = {
            **result,
            "recommended": ai_gateway.recommended_ollama_models(
                [str(model["name"]) for model in result.get("models", [])]
            ),
            "download_url": "https://ollama.com/download/mac",
            "guide_url": "https://docs.ollama.com/macos",
        }
    return result


@app.post("/api/v1/ai/ollama/downloads")
async def start_ollama_download(
    request: Request, background_tasks: BackgroundTasks
) -> JSONResponse:
    """Start a user-requested pull of one curated Golavo model.

    The sidecar talks only to the validated loopback Ollama endpoint. Model names
    are allow-listed, downloads never start implicitly, and progress/cancellation
    reuse the short-lived local job store used by Deep analysis.
    """
    from golavo_server import ai_gateway, jobs

    try:
        body = await request.json()
    except (ValueError, json.JSONDecodeError):
        body = {}
    if not isinstance(body, dict):
        body = {}
    model = str(body.get("model") or "")
    allowed = {str(item["name"]) for item in ai_gateway.RECOMMENDED_OLLAMA_MODELS}
    if model not in allowed:
        raise HTTPException(status_code=400, detail="model is not in Golavo's curated catalog")
    job_id = str(body.get("job_id") or "")
    if not jobs.JOB_ID_RE.match(job_id):
        raise HTTPException(status_code=400, detail="malformed job_id")

    config = ai_gateway.resolve_provider({"provider": "ollama"})
    before = ai_gateway.inspect_local_models(config)
    if before["status"] == "unreachable":
        raise HTTPException(
            status_code=409,
            detail="Ollama is not reachable. Install and open Ollama, then check again.",
        )
    try:
        job = jobs.store().start(job_id)
    except jobs.JobConflict as exc:
        raise HTTPException(status_code=409, detail="download already running") from exc

    def _run() -> None:
        try:
            installed_before = [str(item["name"]) for item in before.get("models", [])]
            if any(
                item["name"] == model and item["installed"]
                for item in ai_gateway.recommended_ollama_models(installed_before)
            ):
                jobs.store().finish(
                    job.job_id, result={"model": model, "status": "installed"}
                )
                return

            jobs.store().update(
                job.job_id,
                stage="downloading_model",
                detail=f"Preparing {model}",
                counts={"completed": 0, "total": None},
            )

            def _progress(status: str, completed: int | None, total: int | None) -> None:
                jobs.store().update(
                    job.job_id,
                    stage="downloading_model",
                    detail=status,
                    counts={"completed": completed, "total": total},
                )

            completed = ai_gateway.pull_ollama_model(
                config,
                model,
                progress=_progress,
                is_cancelled=lambda: jobs.store().is_cancelled(job.job_id),
            )
            if not completed or jobs.store().is_cancelled(job.job_id):
                return
            after = ai_gateway.inspect_local_models(config)
            installed_after = [str(item["name"]) for item in after.get("models", [])]
            catalog = ai_gateway.recommended_ollama_models(installed_after)
            if not any(item["name"] == model and item["installed"] for item in catalog):
                raise OSError("Ollama finished, but the model is not available yet.")
            jobs.store().finish(
                job.job_id,
                result={"model": model, "status": "installed", "models": after["models"]},
            )
        except Exception as exc:
            jobs.store().fail(job.job_id, _ai_job_error(exc))

    background_tasks.add_task(_run)
    return JSONResponse({"job_id": job.job_id, "state": "running"}, status_code=202)


def _ai_job_error(exc: Exception) -> str:
    """Short, user-safe text for an async AI job failure."""
    text = str(exc).strip()
    if not text:
        return "AI generation failed before a safe fallback was produced."
    return text[:240]


@app.get("/api/v1/status")
def engine_status() -> dict[str, Any]:
    """Live engine warm-up status for the UI's staged splash / warming card.

    Reports the match-index warm state; it NEVER triggers the (slow) index load
    itself, so it answers in microseconds even mid-warmup. Token-gated like every
    /api route — the UI only polls it after /health answers, so it doesn't need
    the /health exemption.
    """
    return {"version": __version__, **matches.index_status()}


@app.post("/api/v1/shutdown")
def shutdown() -> dict[str, bool]:
    """Desktop-only: the shell asks the sidecar to exit before installing an update.

    Windows installers cannot replace a running executable, and killing the
    PyInstaller onefile BOOTLOADER alone leaves this Python child serving (and
    holding the exe lock) — so the shell posts here (token-gated like every
    /api route) and the whole process tree exits itself. The tiny delay lets
    the 200 response flush first.

    Hard-disabled in source mode (no launch token): a cross-origin "simple"
    POST is sent by browsers before CORS applies, so an open shutdown route
    would let any webpage kill a dev server.
    """
    import os
    import threading

    if runtime.launch_token() is None:
        raise HTTPException(status_code=404, detail="shutdown is desktop-only")
    threading.Timer(0.2, os._exit, args=(0,)).start()
    return {"ok": True}


@app.get("/api/v1/forecasts")
def list_forecasts() -> list[dict[str, Any]]:
    """List immutable forecast artifacts, newest first.

    Fails closed: an artifact whose sealed identity does not match its bytes is
    omitted rather than shown as a genuine forecast.
    """
    source = _forecasts_dir()
    if not source.exists():
        return []
    artifacts: list[dict[str, Any]] = []
    for path in source.glob("fa_*.json"):
        try:
            artifacts.append(_load_artifact(path))
        except _BAD_ARTIFACT:
            continue
    return sorted(
        artifacts,
        key=lambda item: (item["provenance"]["created_at_utc"], item["artifact_id"]),
        reverse=True,
    )


@app.get("/api/v1/forecasts/{artifact_id}")
def get_forecast(artifact_id: str) -> dict[str, Any]:
    """Return one artifact by canonical id."""
    known_paths = {path.stem: path for path in _forecasts_dir().glob("fa_*.json")}
    path = known_paths.get(artifact_id)
    if path is None:
        raise HTTPException(status_code=404, detail="forecast not found")
    try:
        return _load_artifact(path)
    except _BAD_ARTIFACT as exc:
        raise HTTPException(
            status_code=500, detail="forecast failed integrity verification"
        ) from exc


@app.get("/api/v1/forecasts/{artifact_id}/facts")
def forecast_facts(artifact_id: str) -> dict[str, Any]:
    """Serve the deterministic Commentator's Notebook precomputed for one artifact.

    Read-only and pack-free: it reads a sibling ``notebooks/<artifact_id>.json``
    (written offline by ``golavo notebook``); the forecast surface never computes
    facts on the fly. When no notebook has been precomputed it returns an honest
    empty envelope rather than fabricating facts. Coincidences that ARE present
    stay labelled so the UI can quarantine them.
    """
    source = _forecasts_dir()
    known = {path.stem for path in source.glob("fa_*.json")}
    if artifact_id not in known:
        raise HTTPException(status_code=404, detail="forecast not found")
    notebook_path = source / "notebooks" / f"{artifact_id}.json"
    if not notebook_path.is_file():
        return {"artifact_id": artifact_id, "available": False, "notebook": None}
    return {"artifact_id": artifact_id, "available": True, "notebook": _read_json(notebook_path)}


@app.get("/api/v1/matches/search")
def search_matches(
    q: str,
    competition: str | None = None,
    status: str | None = None,
    limit: int = 25,
    offset: int = 0,
) -> dict[str, Any]:
    """Search the frozen, read-only match index (75k fixtures) by team or competition.

    Read-only and pack-free: it never writes and never touches the model. Forecast
    links are drawn from the REAL ledger (ARTIFACT_DIR), not the sample fallback, so
    a synthetic sample id can never attach to a real fixture. Links are cheap
    navigation — the forecast route still verifies each artifact's identity on serve.
    """
    if len(q.strip()) < 2:
        raise HTTPException(status_code=422, detail="q must be at least 2 characters")
    try:
        return matches.search_matches(
            q,
            competition=competition,
            status=status,
            limit=limit,
            offset=offset,
            forecasts_dir=ARTIFACT_DIR,
        )
    except matches.MatchIndexUnavailable as exc:
        raise HTTPException(status_code=503, detail="match index unavailable") from exc


@app.get("/api/v1/matches/competitions")
def list_competitions() -> dict[str, Any]:
    """List the distinct competitions in the index with their match counts.

    Declared BEFORE ``/matches/{match_id}`` so "competitions" is never swallowed
    as a match id.
    """
    try:
        return matches.list_competitions()
    except matches.MatchIndexUnavailable as exc:
        raise HTTPException(status_code=503, detail="match index unavailable") from exc


@app.get("/api/v1/matches/recent")
def recent_matches(
    limit: int = 24, competition: str | None = None, source_kind: str | None = None
) -> dict[str, Any]:
    """The Games home rails — upcoming fixtures and recent results from the index.

    Declared BEFORE ``/matches/{match_id}`` so "recent" is never read as a match
    id. Read-only navigation: it never seals, computes a number, or reaches the
    network. Optionally narrowed to one ``competition`` or ``source_kind`` (the
    league hubs). An empty ``upcoming`` rail is the honest state when the snapshot
    holds no forward fixtures.
    """
    try:
        return matches.recent_matches(
            limit=limit,
            competition=competition,
            source_kind=source_kind,
            forecasts_dir=ARTIFACT_DIR,
        )
    except matches.MatchIndexUnavailable as exc:
        raise HTTPException(status_code=503, detail="match index unavailable") from exc


@app.get("/api/v1/matches/window")
def matches_window(window: str, limit: int = 200) -> dict[str, Any]:
    """The Matchday home: matches in a time window (week | month | upcoming).

    Declared BEFORE ``/matches/{match_id}`` so "window" is never read as a match
    id. Results-first: week/month are anchored to the freshest result in the
    snapshot so a stale bundle degrades honestly instead of showing an empty page.
    """
    if window not in ("week", "month", "upcoming"):
        raise HTTPException(status_code=422, detail="window must be week, month, or upcoming")
    try:
        return matches.matches_window(window, limit=limit, forecasts_dir=ARTIFACT_DIR)
    except matches.MatchIndexUnavailable as exc:
        raise HTTPException(status_code=503, detail="match index unavailable") from exc


@app.get("/api/v1/matches/{match_id}")
def get_match(match_id: str) -> dict[str, Any]:
    """Return one indexed match by id, with any forecasts linked from the ledger and
    a typed seal-eligibility verdict for the in-app 'Generate local forecast' action."""
    try:
        detail = matches.get_match(match_id, forecasts_dir=ARTIFACT_DIR)
    except matches.MatchIndexUnavailable as exc:
        raise HTTPException(status_code=503, detail="match index unavailable") from exc
    if detail is None:
        raise HTTPException(status_code=404, detail="match not found")
    detail["seal_eligibility"] = seal.eligibility(detail["match"])
    try:
        pick = pick_service.get_pick(match_id, ledger=ARTIFACT_DIR)
    except pick_service.PickError:
        pick = None
    detail["pick"] = (
        {
            "id": pick["record"].get("pick_id"),
            "status": pick["status"],
        }
        if pick is not None
        else None
    )
    return detail


def _pick_error(exc: pick_service.PickError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={"reason_code": exc.reason_code, "message": exc.detail},
    )


def _pick_envelope(match_id: str, *, now_utc: Any, pick: dict[str, Any] | None) -> dict[str, Any]:
    match = matches.get_match(match_id, forecasts_dir=ARTIFACT_DIR)
    if match is None and pick is None:
        raise HTTPException(status_code=404, detail="match not found")
    record = pick["record"] if pick is not None else None
    kickoff = record["lock_at_utc"] if record else match["match"].get("kickoff_utc")
    complete = bool(match and match["match"].get("is_complete"))
    editable = bool(
        not complete
        and kickoff is not None
        and now_utc < pick_service._parse(kickoff)
        and (pick is None or pick["status"] == "draft")
    )
    return {
        "schema_version": "0.1.0",
        "match_id": match_id,
        "pick": pick,
        "editable": editable,
        "lock_at_utc": kickoff,
        "now_utc": pick_service._iso(now_utc),
    }


@app.get("/api/v1/picks/summary")
async def get_picks_summary(season: str | None = None) -> dict[str, Any]:
    now = pick_service._now(None)
    try:
        return await run_in_threadpool(
            pick_service.picks_summary, ledger=ARTIFACT_DIR, season=season, now_utc=now
        )
    except pick_service.PickError as exc:
        raise _pick_error(exc) from exc


@app.get("/api/v1/picks")
async def get_picks(
    status: str | None = None,
    season: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    now = pick_service._now(None)
    try:
        return await run_in_threadpool(
            pick_service.list_picks,
            ledger=ARTIFACT_DIR,
            status=status,
            season=season,
            limit=limit,
            offset=offset,
            now_utc=now,
        )
    except pick_service.PickError as exc:
        raise _pick_error(exc) from exc


@app.get("/api/v1/matches/{match_id}/pick")
async def get_match_pick(match_id: str) -> dict[str, Any]:
    now = pick_service._now(None)
    try:
        pick = await run_in_threadpool(
            pick_service.get_pick, match_id, ledger=ARTIFACT_DIR, now_utc=now
        )
    except pick_service.PickError as exc:
        raise _pick_error(exc) from exc
    return _pick_envelope(match_id, now_utc=now, pick=pick)


@app.put("/api/v1/matches/{match_id}/pick")
async def put_match_pick(match_id: str, request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except (ValueError, json.JSONDecodeError):
        body = {}
    if not isinstance(body, dict):
        body = {}
    now = pick_service._now(None)
    try:
        pick = await run_in_threadpool(
            pick_service.save_pick,
            match_id,
            body.get("home_goals"),
            body.get("away_goals"),
            ledger=ARTIFACT_DIR,
            now_utc=now,
        )
    except pick_service.PickError as exc:
        raise _pick_error(exc) from exc
    return JSONResponse(status_code=200, content=_pick_envelope(match_id, now_utc=now, pick=pick))


@app.delete("/api/v1/matches/{match_id}/pick")
async def remove_match_pick(match_id: str) -> dict[str, Any]:
    now = pick_service._now(None)
    try:
        await run_in_threadpool(
            pick_service.delete_pick, match_id, ledger=ARTIFACT_DIR, now_utc=now
        )
    except pick_service.PickError as exc:
        raise _pick_error(exc) from exc
    return _pick_envelope(match_id, now_utc=now, pick=None)


@app.get("/api/v1/matches/{match_id}/notebook")
def match_notebook(match_id: str) -> dict[str, Any]:
    """Serve the deterministic Commentator's Notebook for one match.

    Prefers a precomputed notebook beside a sealed forecast; else computes it on
    demand at ``kickoff - 1s`` — the seal's own conservative cutoff — so the
    notebook can never read the fixture's result or any later match. A build
    failure fails closed to an honest empty envelope, never a 500.
    """
    try:
        result = matches.match_notebook(match_id, forecasts_dir=ARTIFACT_DIR)
    except matches.MatchIndexUnavailable as exc:
        raise HTTPException(status_code=503, detail="match index unavailable") from exc
    if result is None:
        raise HTTPException(status_code=404, detail="match not found")
    return result


@app.get("/api/v1/matches/{match_id}/analysis")
async def match_analysis(match_id: str) -> dict[str, Any]:
    """On-demand, leak-safe multi-model analysis (Replay for a played match,
    Preview for a scheduled one) for ANY indexed match.

    The single new read capability of the cockpit: it fits every council model at
    the seal's own ``kickoff - 1s`` cutoff, so a Replay can never read the
    fixture's result or any later match, and returns a descriptive council — two
    voices plus a baseline, never an averaged consensus. Never writes, never
    seals. The fit runs off the event loop so a slow analysis can't stall
    /health. Fails closed to an honest ``available: false`` envelope, never a 500.
    """
    try:
        result = await run_in_threadpool(analysis.match_analysis, match_id)
    except matches.MatchIndexUnavailable as exc:
        raise HTTPException(status_code=503, detail="match index unavailable") from exc
    if result is None:
        raise HTTPException(status_code=404, detail="match not found")
    return result


@app.post("/api/v1/matches/{match_id}/seal")
async def create_seal(match_id: str, request: Request) -> JSONResponse:
    """Seal ONE deterministic local forecast for a scheduled fixture.

    The single write route, desktop-only (token-gated like every /api route). The
    client names only the fixture id and, optionally, a model ``family`` from a
    fixed allowlist; the pack, the training date, and the as-of are all resolved
    server-side, so a caller can neither backdate a seal nor choose an untrusted
    pack. The model fit runs off the event loop (``run_in_threadpool``) so a slow
    seal never freezes /health or the rest of the API (the same discipline every
    heavy route now follows). Idempotent per (fixture, family): a repeat returns
    the existing seal
    (200), a new one is 201. Typed failures: ineligible fixture -> 422 with a
    reason_code, missing pack -> 503, genuine artifact collision -> 409.
    """
    try:
        body = await request.json()
    except (ValueError, json.JSONDecodeError):
        body = {}
    if not isinstance(body, dict):
        body = {}
    family = body.get("family") or seal.DEFAULT_FAMILY
    if not isinstance(family, str):
        raise HTTPException(
            status_code=422,
            detail={"reason_code": "unsupported_family", "message": "family must be a string"},
        )

    try:
        result = await run_in_threadpool(
            seal.seal_match, match_id, family=family, forecasts_dir=ARTIFACT_DIR
        )
    except seal.SealError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"reason_code": exc.reason_code, "message": exc.detail},
        ) from exc
    except matches.MatchIndexUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail={"reason_code": "engine_warming", "message": "match index unavailable"},
        ) from exc
    return JSONResponse(status_code=201 if result["created"] else 200, content=result)


@app.get("/api/v1/fixtures/check")
def fixtures_check() -> dict[str, Any]:
    """Opt-in fixture freshness: report genuinely-new upcoming fixtures upstream.

    The ONLY route that reaches the network, and it does so only when the UI —
    with the user's "keep fixtures up to date" setting on — calls it. Read-only:
    it diffs the CC0 source against the committed index and returns upcoming games
    not yet present; it never writes, seals, or rebuilds anything.
    """
    from golavo_server import fixtures

    try:
        frame = matches._load_index()
    except matches.MatchIndexUnavailable:
        frame = None
    try:
        return fixtures.check_new_fixtures(frame)
    except fixtures.FixtureCheckError as exc:
        raise HTTPException(
            status_code=503,
            detail={"reason_code": "fixture_source_unreachable", "message": str(exc)},
        ) from exc


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
async def narrative(artifact_id: str, request: Request, background_tasks: BackgroundTasks) -> Any:
    """Return an OPTIONAL, guard-validated AI narration for one artifact.

    Additive and off by default: with no body (or ``{"provider": "off"}``) this
    returns a ``disabled`` envelope without ever calling a model. The forecast
    endpoints never touch this path, so AI can never block or delay a forecast.
    Every number in an ``ok`` narration is one the deterministic engine already
    produced; anything else falls back to ``local_only``.
    """
    from golavo_core.evidence import build_evidence_bundle  # lazy: pulls the AI guards

    from golavo_server import ai_gateway, jobs

    known_paths = {path.stem: path for path in _forecasts_dir().glob("fa_*.json")}
    path = known_paths.get(artifact_id)
    if path is None:
        raise HTTPException(status_code=404, detail="forecast not found")
    try:
        artifact = await run_in_threadpool(_load_artifact, path)
    except _BAD_ARTIFACT as exc:
        raise HTTPException(
            status_code=500, detail="forecast failed integrity verification"
        ) from exc

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

    # Fold any precomputed notebook's context/predictive facts into the bundle so
    # the model may cite them; coincidences are excluded and the numeric whitelist
    # still governs. Absent a notebook, the bundle is exactly as before. The bundle
    # build and the model call run off the event loop (run_in_threadpool), mirroring
    # create_seal/match_narrative, so a slow narration never freezes /health or the
    # rest of the API.
    def _build_bundle() -> dict[str, Any]:
        extra_facts, extra_numbers = _notebook_evidence(artifact_id)
        return build_evidence_bundle(artifact, extra_facts=extra_facts, extra_numbers=extra_numbers)

    bundle = await run_in_threadpool(_build_bundle)

    # New clients ask for an asynchronous job so the WebView never has to hold a
    # single request open for a 5-8 minute Gemma run. No job id / async flag keeps
    # the historical blocking API intact for older or third-party clients.
    job_id = body.get("job_id")
    job = None
    if body.get("async_job") is True and isinstance(job_id, str) and job_id:
        if not jobs.JOB_ID_RE.match(job_id):
            raise HTTPException(status_code=400, detail="malformed job_id")
        try:
            job = jobs.store().start(job_id)
        except jobs.JobConflict as exc:
            raise HTTPException(status_code=409, detail="job already running") from exc

    def _progress(stage: str, detail: str, counts: dict[str, Any]) -> None:
        if job is not None:
            jobs.store().update(job.job_id, stage=stage, detail=detail, counts=counts)

    def _cancelled() -> bool:
        return job is not None and jobs.store().is_cancelled(job.job_id)

    def _serialize(envelope: Any) -> dict[str, Any]:
        # The UI resolves claim ids against these trusted bundle lookups.
        return {
            "artifact_id": artifact_id,
            "bundle_hash": bundle["bundle_hash"],
            "sources": [
                {
                    "source_id": s["source_id"],
                    "kind": s["kind"],
                    "title": s["title"],
                    "url": s["url"],
                }
                for s in bundle["sources"]
            ],
            "numbers": [
                {"id": n["id"], "display": n["display"], "label": n["label"], "unit": n["unit"]}
                for n in bundle["allowed_numbers"]
            ],
            **envelope.to_dict(),
        }

    def _run() -> dict[str, Any]:
        try:
            result = _serialize(
                ai_gateway.generate_narration(
                    bundle,
                    config,
                    refresh=bool(body.get("refresh", False)),
                    progress=_progress,
                    is_cancelled=_cancelled,
                )
            )
            if job is not None:
                jobs.store().finish(job.job_id, result=result)
            return result
        except Exception as exc:
            if job is not None:
                jobs.store().fail(job.job_id, _ai_job_error(exc))
            raise

    if job is not None:
        background_tasks.add_task(_run)
        return JSONResponse({"job_id": job.job_id, "state": "running"}, status_code=202)
    return await run_in_threadpool(_run)


@app.post("/api/v1/matches/{match_id}/narrative")
async def match_narrative(
    match_id: str, request: Request, background_tasks: BackgroundTasks
) -> Any:
    """An OPTIONAL, guard-validated AI deep read of one match's notes + council.

    The cockpit's "make the notes deeper" action: the on-demand MatchAnalysis
    (Replay/Preview council) and the Commentator's Notebook are folded into a
    match evidence bundle (`ma_*`, schema 0.2.0) and run through the SAME
    fail-closed pipeline the sealed path uses — numeric whitelist, mandatory
    citations, betting-lexicon rejection, one retry then local_only. Off by
    default; `{"refresh": true}` skips the cache read to regenerate. The bundle
    computation runs off the event loop.
    """
    from golavo_core.evidence import build_match_evidence_bundle  # lazy: AI guards
    from golavo_core.facts import notebook_to_evidence

    from golavo_server import ai_gateway, jobs

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

    # Optional client-generated progress-tracking id (idempotency key). Validate
    # it now, but do not register the job until the evidence bundle is valid. A
    # bundle failure happens before any model work and must not leave a ghost job
    # stuck forever in the "assembling evidence" stage.
    job_id = body.get("job_id")
    if isinstance(job_id, str) and job_id:
        if not jobs.JOB_ID_RE.match(job_id):
            raise HTTPException(status_code=400, detail="malformed job_id")

    def _build_bundle() -> dict[str, Any] | None:
        envelope = analysis.match_analysis(match_id)
        if envelope is None:
            return None
        if not envelope.get("available") or envelope.get("analysis") is None:
            raise ValueError(envelope.get("reason") or "analysis unavailable")
        nb_facts: list[Any] = []
        nb_numbers: list[Any] = []
        nb_extra: list[Any] = []
        pack_ids: tuple[str, ...] = ()
        nb = matches.match_notebook(match_id, forecasts_dir=ARTIFACT_DIR)
        if nb and nb.get("available") and nb.get("notebook"):
            nb_facts, nb_numbers, nb_extra = notebook_to_evidence(nb["notebook"])
            # The first notebook source is the match-index pack used by the model
            # council. Later base ids can come from a sealed notebook's additional
            # result snapshots. They must be present so folded facts resolve, but
            # must not be attributed to council numbers that never consumed them.
            notebook_ids = tuple(nb["notebook"].get("source_ids") or ())
            pack_ids = notebook_ids[:1]
            known_extra = {str(source["source_id"]) for source in nb_extra}
            for source_id in notebook_ids[1:]:
                if source_id in known_extra:
                    continue
                nb_extra.append(
                    {
                        "source_id": source_id,
                        "title": f"Vendored data pack · {source_id} · match results",
                        "license": "CC0-1.0",
                    }
                )
                known_extra.add(source_id)
        return build_match_evidence_bundle(
            envelope["analysis"],
            notebook_facts=nb_facts,
            notebook_numbers=nb_numbers,
            pack_source_ids=pack_ids,
            extra_sources=nb_extra,
        )

    try:
        bundle = await run_in_threadpool(_build_bundle)
    except matches.MatchIndexUnavailable as exc:
        raise HTTPException(status_code=503, detail="match index unavailable") from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"reason_code": "analysis_unavailable", "message": str(exc)},
        ) from exc
    if bundle is None:
        raise HTTPException(status_code=404, detail="match not found")

    job = None
    if isinstance(job_id, str) and job_id:
        try:
            job = jobs.store().start(job_id)
        except jobs.JobConflict as exc:
            raise HTTPException(status_code=409, detail="job already running") from exc

    # Progress + cancel hooks (no-ops when there's no job). The web-research lane
    # runs only when the user opted in (allow_research in the body); the fetchers
    # never touch the network otherwise or in CI (GOLAVO_NO_RESEARCH=1).
    def _progress(stage: str, detail: str, counts: dict[str, Any]) -> None:
        if job is not None:
            jobs.store().update(job.job_id, stage=stage, detail=detail, counts=counts)

    def _cancelled() -> bool:
        return job is not None and jobs.store().is_cancelled(job.job_id)

    researcher = None
    if config.allow_research:
        from golavo_server.research import run_research

        researcher = lambda: run_research(bundle, config.depth, progress=_progress)  # noqa: E731

    def _serialize(envelope: Any) -> dict[str, Any]:
        sources = [
            {"source_id": s["source_id"], "kind": s["kind"], "title": s["title"], "url": s["url"]}
            for s in bundle["sources"]
        ]
        sources.extend(envelope.web_sources)
        return {
            "match_id": match_id,
            "bundle_hash": bundle["bundle_hash"],
            "sources": sources,
            "numbers": [
                {"id": n["id"], "display": n["display"], "label": n["label"], "unit": n["unit"]}
                for n in bundle["allowed_numbers"]
            ],
            "job_id": job.job_id if job is not None else None,
            **envelope.to_dict(),
        }

    def _run() -> dict[str, Any]:
        try:
            env = ai_gateway.generate_narration(
                bundle,
                config,
                refresh=bool(body.get("refresh", False)),
                researcher=researcher,
                progress=_progress,
                is_cancelled=_cancelled,
            )
            result = _serialize(env)
            if job is not None:
                jobs.store().finish(job.job_id, result=result)
            return result
        except Exception as exc:
            if job is not None:
                jobs.store().fail(job.job_id, _ai_job_error(exc))
            raise

    if job is not None and body.get("async_job") is True:
        background_tasks.add_task(_run)
        return JSONResponse({"job_id": job.job_id, "state": "running"}, status_code=202)
    return await run_in_threadpool(_run)


@app.get("/api/v1/ai/jobs/{job_id}")
def ai_job_progress(job_id: str) -> dict[str, Any]:
    """Live progress for an in-flight AI read (polled by the UI). 404 when the id
    is unknown or has been pruned; 400 on a malformed id."""
    from golavo_server import jobs

    if not jobs.JOB_ID_RE.match(job_id):
        raise HTTPException(status_code=400, detail="malformed job_id")
    job = jobs.store().get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job.to_dict()


@app.post("/api/v1/ai/jobs/{job_id}/cancel")
def ai_job_cancel(job_id: str) -> dict[str, Any]:
    """Request cancellation of an in-flight AI read. The generator checks between
    stages; an in-flight model call is not aborted (the read may still finish and
    cache)."""
    from golavo_server import jobs

    if not jobs.JOB_ID_RE.match(job_id):
        raise HTTPException(status_code=400, detail="malformed job_id")
    cancelled = jobs.store().cancel(job_id)
    return {"job_id": job_id, "cancelled": bool(cancelled)}


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
