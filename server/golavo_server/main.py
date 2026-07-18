"""Read-only FastAPI surface for Golavo forecast artifacts."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from jsonschema import ValidationError
from starlette.concurrency import run_in_threadpool

from golavo_server import (
    __version__,
    analysis,
    analytics,
    conditions,
    context_registry,
    correction_exports,
    correction_policy,
    correction_sanitize,
    correction_store,
    correction_validation,
    follows,
    matches,
    openligadb_jobs,
    openligadb_overlay,
    openligadb_state,
    outlook,
    refresh_jobs,
    research_pack,
    retrospective,
    runtime,
    seal,
)
from golavo_server import picks as pick_service
from golavo_server import research as match_research
from golavo_server.research import extract as research_extract
from golavo_server.research import policy as research_policy
from golavo_server.research import settings as research_settings
from golavo_server.research import store as research_store

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
    path = request.url.path
    correction_path = path.startswith("/api/v1/corrections") or (
        path.startswith("/api/v1/matches/") and path.endswith("/corrections")
    )
    match_research_path = path.startswith("/api/v1/research/") and not path.startswith(
        "/api/v1/research/competitions/"
    )
    if correction_path and token is None:
        return JSONResponse(
            {"detail": "correction routes require the private desktop launch token"},
            status_code=403,
        )
    if match_research_path and token is None:
        return JSONResponse(
            {"detail": "match research requires the private desktop launch token"},
            status_code=403,
        )
    if correction_path and request.method not in {"GET", "OPTIONS"}:
        try:
            content_length = int(request.headers.get("content-length", "0"))
        except ValueError:
            content_length = 0
        if content_length > 131072:
            return JSONResponse({"detail": "correction request exceeds 128 KiB"}, status_code=413)
    if match_research_path and request.method not in {"GET", "OPTIONS"}:
        try:
            content_length = int(request.headers.get("content-length", "0"))
        except ValueError:
            content_length = 0
        if content_length > 65536:
            return JSONResponse({"detail": "research request exceeds 64 KiB"}, status_code=413)
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
CORRECTIONS_DIR = runtime.corrections_dir()
RESEARCH_DIR = runtime.research_dir()
EVAL_SUMMARY_PATHS = runtime.eval_summary_paths()


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
    notebook_path = ARTIFACT_DIR / "notebooks" / f"{artifact_id}.json"
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
    data_status = refresh_jobs.status()
    active = data_status.get("active_generation") or {}
    return {
        "version": __version__,
        "source_sha": runtime.source_sha(),
        # Always the real ledger. Synthetic samples are NEVER served as data:
        # an empty ledger honestly shows an empty forecast list, and the one
        # teaching example lives inside the in-app sealing guide (bundled
        # UI-side), not on these routes. So a #/forecast/fa_<sample-id> deep
        # link 404s honestly rather than rendering a synthetic artifact.
        "forecast_source": "ledger",
        "refresh_supported": data_status["refresh_supported"],
        "data_generation_id": active.get("generation_id"),
    }


@app.get("/api/v1/capabilities")
def get_capabilities() -> dict[str, Any]:
    """Stable competition identities and honest per-feature availability states."""
    from golavo_core.competitions import competition_catalog

    return competition_catalog()


@app.get("/api/v1/analytics/competitions/{competition_id}")
def get_competition_analytics(competition_id: str, as_of_utc: str | None = None) -> dict[str, Any]:
    """Cutoff-safe strength and workload context from the active local index."""
    try:
        return analytics.get_competition_analytics(competition_id, as_of_utc=as_of_utc)
    except ValueError as exc:
        message = str(exc)
        status = 404 if message.startswith("unknown competition_id") else 400
        raise HTTPException(status_code=status, detail=message) from exc
    except matches.MatchIndexUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/v1/competitions/{competition_id}/scorers")
def get_competition_scorers(
    competition_id: str, as_of_utc: str | None = None, min_goals: int = 1
) -> dict[str, Any]:
    """A competition's leak-safe Golden Boot and penalty-shootout ledger."""
    from golavo_server import scorers

    try:
        return scorers.get_competition_scorers(
            competition_id, as_of_utc=as_of_utc, min_goals=min_goals
        )
    except ValueError as exc:
        message = str(exc)
        status = 404 if message.startswith("unknown competition_id") else 400
        raise HTTPException(status_code=status, detail=message) from exc
    except matches.MatchIndexUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/v1/ratings/international")
def get_international_ratings(as_of_utc: str | None = None, top_n: int = 40) -> dict[str, Any]:
    """Golavo Ratings — the in-house national-team Elo table, leak-safe at the cutoff."""
    from golavo_server import ratings

    try:
        return ratings.get_international_ratings(as_of_utc=as_of_utc, top_n=top_n)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except matches.MatchIndexUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/v1/tournaments/worldcup-2026/outlook")
def get_world_cup_2026_outlook(as_of_utc: str | None = None) -> dict[str, Any]:
    """Exact four-team bracket enumeration from Golavo's two model voices."""
    try:
        return outlook.world_cup_2026(as_of_utc=as_of_utc)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except matches.MatchIndexUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/v1/tournaments/worldcup-2026/retrospective")
async def start_world_cup_2026_retrospective(
    request: Request, background_tasks: BackgroundTasks
) -> Any:
    """Backtest every played 2026 World Cup match at its own pre-kickoff cutoff.

    A backtest, never a seal: nothing here is persisted or scored as a record.
    The fit is minutes long, so a job_id streams progress; without one the work
    still runs off the event loop.
    """
    from golavo_server import jobs

    lane = jobs.RETROSPECTIVE_LANE
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001 -- an empty body is a valid synchronous request
        body = {}
    job_id = body.get("job_id") if isinstance(body, dict) else None

    tracked: str | None = None
    if isinstance(job_id, str) and job_id:
        if not lane.owns(job_id):
            raise HTTPException(status_code=400, detail="malformed job_id")
        try:
            # The lane starts the job in its OWN first stage, with its opening
            # detail, atomically — so a client polling right after this 202 (before
            # the first progress tick) can never be shown another lane's stage or a
            # null detail.
            tracked = lane.start(
                job_id,
                detail="Run started; no match scored yet",
                counts={"completed": 0, "total": 0},
            ).job_id
        except jobs.JobConflict as exc:
            raise HTTPException(status_code=409, detail="job already running") from exc

    def _progress(done: int, total: int) -> None:
        lane.progress(
            tracked,
            stage="replaying",
            detail=f"Backtesting match {done} of {total}",
            counts={"completed": done, "total": total},
        )

    def _run() -> dict[str, Any]:
        # No separate "scoring" stage: the lane's finish sets "done" with no yield
        # point in between, so a client can never observe an intermediate stage
        # here — decorative state a poller would never see.
        return lane.run(
            tracked,
            lambda: retrospective.build(
                progress=_progress,
                is_cancelled=lambda: lane.is_cancelled(tracked),
            ),
        )

    if tracked is not None:
        background_tasks.add_task(_run)
        return JSONResponse({"job_id": tracked, "state": "running"}, status_code=202)
    try:
        return await run_in_threadpool(_run)
    except matches.MatchIndexUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/v1/tournaments/worldcup-2026/retrospective/jobs/{job_id}")
def world_cup_2026_retrospective_job(job_id: str) -> dict[str, Any]:
    """Progress for one retrospective run. Its own lane, not the AI job route."""
    from golavo_server import jobs

    if not jobs.RETROSPECTIVE_LANE.owns(job_id):
        raise HTTPException(status_code=400, detail="malformed job_id")
    job = jobs.store().get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job.to_dict()


@app.post("/api/v1/tournaments/worldcup-2026/retrospective/jobs/{job_id}/cancel")
def world_cup_2026_retrospective_job_cancel(job_id: str) -> dict[str, Any]:
    """Request cancellation of an in-flight retrospective run. Its own lane's
    door, so a client never has to reach into the AI job route to stop a
    ~5-minute backtest it started here — nor this door into the AI lane's jobs."""
    from golavo_server import jobs

    lane = jobs.RETROSPECTIVE_LANE
    if not lane.owns(job_id):
        raise HTTPException(status_code=400, detail="malformed job_id")
    return {"job_id": job_id, "cancelled": bool(lane.cancel(job_id))}


@app.get("/api/v1/analytics/competitions/{competition_id}/season-outlook")
def get_season_outlook(
    competition_id: str,
    as_of_utc: str | None = None,
    season: str | None = None,
) -> dict[str, Any]:
    """Standings plus a seeded outlook only after the fixture certificate passes."""
    try:
        return outlook.season(competition_id, as_of_utc=as_of_utc, season_id=season)
    except ValueError as exc:
        message = str(exc)
        status = 404 if message.startswith("no verified standings rule") else 400
        raise HTTPException(status_code=status, detail=message) from exc
    except matches.MatchIndexUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/v1/research/competitions/{competition_id}")
def get_research_team_analytics(competition_id: str) -> dict[str, Any]:
    """Historical, competition-and-era-scoped team aggregates from an isolated pack."""
    try:
        return research_pack.team_analytics(competition_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise HTTPException(status_code=503, detail="research pack unavailable") from exc


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
    lane = jobs.MODEL_DOWNLOAD_LANE
    try:
        job = lane.start(job_id)
    except jobs.JobConflict as exc:
        raise HTTPException(status_code=409, detail="download already running") from exc

    def _download() -> dict[str, Any] | None:
        installed_before = [str(item["name"]) for item in before.get("models", [])]
        if any(
            item["name"] == model and item["installed"]
            for item in ai_gateway.recommended_ollama_models(installed_before)
        ):
            return {"model": model, "status": "installed"}

        lane.progress(
            job.job_id,
            stage="downloading_model",
            detail=f"Preparing {model}",
            counts={"completed": 0, "total": None},
        )

        def _progress(status: str, completed: int | None, total: int | None) -> None:
            lane.progress(
                job.job_id,
                stage="downloading_model",
                detail=status,
                counts={"completed": completed, "total": total},
            )

        completed = ai_gateway.pull_ollama_model(
            config,
            model,
            progress=_progress,
            is_cancelled=lambda: lane.is_cancelled(job.job_id),
        )
        if lane.is_cancelled(job.job_id):
            # A cancelled pull owns its own terminal state; finishing it here would
            # relabel what the user asked for. Raising still runs the lane's fail(),
            # which is a no-op on a cancelled job EXCEPT that it releases the id —
            # so a cancelled download can be retried without waiting out the TTL.
            raise _DownloadCancelled
        if not completed:
            raise OSError("The download stopped before the model was installed.")
        after = ai_gateway.inspect_local_models(config)
        installed_after = [str(item["name"]) for item in after.get("models", [])]
        catalog = ai_gateway.recommended_ollama_models(installed_after)
        if not any(item["name"] == model and item["installed"] for item in catalog):
            raise OSError("Ollama finished, but the model is not available yet.")
        return {"model": model, "status": "installed", "models": after["models"]}

    def _run() -> None:
        try:
            lane.run(job.job_id, _download)
        except _DownloadCancelled:
            return  # the job is already cancelled; fail() was a no-op on it
        except Exception as exc:  # noqa: BLE001 (a background task owns its own errors)
            jobs.store().fail(job.job_id, _ai_job_error(exc))

    background_tasks.add_task(_run)
    return JSONResponse({"job_id": job.job_id, "state": "running"}, status_code=202)


class _DownloadCancelled(Exception):
    """The pull stopped because the user cancelled it — not a failure."""


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
    source = ARTIFACT_DIR
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
    known_paths = {path.stem: path for path in ARTIFACT_DIR.glob("fa_*.json")}
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
    source = ARTIFACT_DIR
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


def _typed_detail(exc: Any) -> dict[str, Any]:
    """The error envelope every typed local-store failure is reported in.

    The UI parses ``reason_code`` to decide what to say and whether to offer a
    retry, so this shape is a contract. It was written out at each of the eight
    places a typed failure became an HTTPException.
    """
    return {"reason_code": exc.reason_code, "message": exc.detail}


def _follow_error(exc: follows.FollowError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail=_typed_detail(exc),
    )


def _notifications_supported() -> bool:
    """The packaged desktop always supplies a launch token; source/browser mode does not."""
    return runtime.launch_token() is not None


def _follow_source_context(source_id: str) -> tuple[str | None, str | None, str | None]:
    status = refresh_jobs.status()
    source = next(
        (item for item in status.get("sources", []) if item.get("source_id") == source_id),
        {},
    )
    generation = status.get("active_generation") or {}
    return (
        source.get("active_ref"),
        source.get("last_checked_at_utc"),
        generation.get("generation_id"),
    )


@app.get("/api/v1/follows")
def list_followed_matches(
    state: str = "active", limit: int = 100, offset: int = 0, event_limit: int = 20
) -> dict[str, Any]:
    try:
        return follows.list_follows(
            ledger=ARTIFACT_DIR,
            state=state,
            limit=limit,
            offset=offset,
            event_limit=event_limit,
        )
    except follows.FollowError as exc:
        raise _follow_error(exc) from exc


@app.get("/api/v1/follows/settings")
def get_follow_settings() -> dict[str, Any]:
    try:
        return follows.settings(
            ledger=ARTIFACT_DIR, notifications_supported=_notifications_supported()
        )
    except follows.FollowError as exc:
        raise _follow_error(exc) from exc


@app.put("/api/v1/follows/settings")
async def put_follow_settings(request: Request) -> dict[str, Any]:
    try:
        body = await request.json()
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail="request body must be valid JSON") from exc
    value = body.get("notifications_opt_in") if isinstance(body, dict) else None
    if not isinstance(value, bool):
        raise HTTPException(status_code=422, detail="notifications_opt_in must be boolean")
    try:
        return await run_in_threadpool(
            follows.update_settings,
            value,
            ledger=ARTIFACT_DIR,
            notifications_supported=_notifications_supported(),
        )
    except follows.FollowError as exc:
        raise _follow_error(exc) from exc


@app.post("/api/v1/follows/reconcile")
async def reconcile_followed_matches() -> dict[str, Any]:
    """Reconcile against already-active local bytes; this route never reaches the network."""
    async def reconcile(stable: matches.StableGeneration) -> dict[str, Any]:
        stable.require_stable()
        return await run_in_threadpool(
            follows.reconcile,
            ledger=ARTIFACT_DIR,
            frame=stable.snapshot.frame,
            index_fingerprint=stable.snapshot.fingerprint,
            generation_id=stable.generation_id,
            source_status=stable.sources,
            generation_commit=stable.commit,
        )

    try:
        return await matches.run_on_stable_generation(
            reconcile,
            detail="verified match index changed during follow reconciliation; retry",
        )
    except matches.MatchIndexUnavailable as exc:
        raise HTTPException(status_code=503, detail="match index unavailable") from exc
    except follows.FollowError as exc:
        raise _follow_error(exc) from exc


@app.post("/api/v1/follows/events/read")
async def read_follow_events(request: Request) -> dict[str, Any]:
    try:
        body = await request.json()
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail="request body must be valid JSON") from exc
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="request body must be an object")
    event_ids = body.get("event_ids")
    if event_ids is not None and not (
        isinstance(event_ids, list) and all(isinstance(item, str) for item in event_ids)
    ):
        raise HTTPException(status_code=422, detail="event_ids must be an array of strings")
    try:
        return await run_in_threadpool(
            follows.mark_read,
            event_ids,
            ledger=ARTIFACT_DIR,
            all_events=body.get("all") is True,
        )
    except follows.FollowError as exc:
        raise _follow_error(exc) from exc


@app.post("/api/v1/follows/notification-claims")
async def claim_follow_notifications() -> dict[str, Any]:
    try:
        return await run_in_threadpool(follows.claim_notifications, ledger=ARTIFACT_DIR)
    except follows.FollowError as exc:
        raise _follow_error(exc) from exc


@app.post("/api/v1/follows/events/{event_id}/notification")
async def update_follow_notification(event_id: str, request: Request) -> dict[str, Any]:
    try:
        body = await request.json()
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail="request body must be valid JSON") from exc
    if not isinstance(body, dict) or not isinstance(body.get("status"), str):
        raise HTTPException(status_code=422, detail="status is required")
    try:
        return await run_in_threadpool(
            follows.update_notification,
            event_id,
            str(body["status"]),
            ledger=ARTIFACT_DIR,
            error=str(body["error"]) if body.get("error") else None,
        )
    except follows.FollowError as exc:
        raise _follow_error(exc) from exc


@app.delete("/api/v1/follows/history")
async def delete_follow_history(request: Request) -> dict[str, Any]:
    try:
        body = await request.json()
    except (ValueError, json.JSONDecodeError):
        body = {}
    if not isinstance(body, dict) or body.get("confirm") != "remove_follow_history":
        raise HTTPException(
            status_code=422,
            detail={
                "reason_code": "confirmation_required",
                "message": "confirm must equal remove_follow_history",
            },
        )
    try:
        return await run_in_threadpool(follows.remove_history, ledger=ARTIFACT_DIR)
    except follows.FollowError as exc:
        raise _follow_error(exc) from exc


@app.delete("/api/v1/follows/{follow_id}")
async def unfollow_match(follow_id: str) -> dict[str, Any]:
    try:
        return await run_in_threadpool(follows.unfollow, follow_id, ledger=ARTIFACT_DIR)
    except follows.FollowError as exc:
        raise _follow_error(exc) from exc


def _correction_root() -> Path:
    if CORRECTIONS_DIR is None:
        raise HTTPException(
            status_code=503,
            detail={
                "reason_code": "correction_store_unavailable",
                "message": "correction proposals require a writable desktop data directory",
            },
        )
    return Path(CORRECTIONS_DIR)


def _research_root() -> Path:
    if RESEARCH_DIR is None:
        raise HTTPException(
            status_code=503,
            detail={
                "reason_code": "research_store_unavailable",
                "message": "match research requires a writable desktop data directory",
            },
        )
    return Path(RESEARCH_DIR)


async def _research_body(request: Request) -> dict[str, Any]:
    try:
        raw = await request.body()
        if len(raw) > 65536:
            raise HTTPException(status_code=413, detail="research request exceeds 64 KiB")
        body = json.loads(raw)
    except HTTPException:
        raise
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail="request body must be valid JSON") from exc
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="request body must be an object")
    return body


def _research_error(exc: Exception) -> HTTPException:
    if isinstance(exc, research_store.ResearchStoreError):
        return HTTPException(
            status_code=exc.status,
            detail=_typed_detail(exc),
        )
    if isinstance(exc, research_policy.ResearchPolicyError):
        return HTTPException(
            status_code=422,
            detail=_typed_detail(exc),
        )
    if isinstance(exc, match_research.ResearchFetchError):
        status = 429 if exc.reason_code == "source_busy" else 503
        return HTTPException(
            status_code=status,
            detail=_typed_detail(exc),
        )
    return HTTPException(status_code=500, detail="research operation failed")


def _correction_error(exc: Exception) -> HTTPException:
    if isinstance(exc, correction_store.CorrectionStoreError):
        return HTTPException(
            status_code=exc.status_code,
            detail=_typed_detail(exc),
        )
    if isinstance(exc, correction_policy.CorrectionPolicyError):
        return HTTPException(
            status_code=422,
            detail=_typed_detail(exc),
        )
    if isinstance(exc, correction_sanitize.EvidenceError):
        return HTTPException(
            status_code=422,
            detail=_typed_detail(exc),
        )
    return HTTPException(status_code=500, detail="correction operation failed")


async def _correction_body(request: Request) -> dict[str, Any]:
    try:
        raw = await request.body()
        if len(raw) > 131072:
            raise HTTPException(status_code=413, detail="correction request exceeds 128 KiB")
        body = json.loads(raw)
    except HTTPException:
        raise
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail="request body must be valid JSON") from exc
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="request body must be an object")
    return body


def _match_for_correction(
    match_id: str | None, snapshot: matches.IndexSnapshot | None = None
) -> dict[str, Any] | None:
    if not match_id:
        return None
    detail = matches.get_match(match_id, forecasts_dir=ARTIFACT_DIR, snapshot=snapshot)
    return detail["match"] if detail is not None else None


def _missing_fixture_match(
    proposal: dict[str, Any], snapshot: matches.IndexSnapshot | None = None
) -> dict[str, Any] | None:
    key = proposal["proposed"].get("upstream_record_key")
    if not isinstance(key, str) or not key:
        return None
    frame = snapshot.frame if snapshot is not None else matches._load_index()
    if "upstream_fixture_key" not in frame.columns:
        return None
    selected = frame.loc[frame["upstream_fixture_key"].astype("string") == key]
    if selected.empty:
        return None
    detail = matches.get_match(
        str(selected.iloc[0]["match_id"]),
        forecasts_dir=ARTIFACT_DIR,
        snapshot=snapshot,
    )
    return detail["match"] if detail is not None else None


@app.get("/api/v1/corrections/capabilities")
def correction_capabilities() -> dict[str, Any]:
    try:
        fingerprint = matches.index_fingerprint()
    except matches.MatchIndexUnavailable:
        fingerprint = None
    return {
        **correction_policy.capabilities(write_enabled=CORRECTIONS_DIR is not None),
        "current_index_fingerprint": fingerprint,
    }


@app.get("/api/v1/corrections")
def list_corrections(state: str | None = None, limit: int = 100, offset: int = 0) -> dict[str, Any]:
    try:
        return correction_store.list_proposals(
            _correction_root(), state=state, limit=limit, offset=offset
        )
    except correction_store.CorrectionStoreError as exc:
        raise _correction_error(exc) from exc


@app.post("/api/v1/corrections")
async def create_correction(request: Request) -> JSONResponse:
    body = await _correction_body(request)
    correction_type = body.get("correction_type")
    source_id = body.get("source_id")
    target_input = body.get("target")
    proposed_input = body.get("proposed")
    if correction_type not in correction_policy.CORRECTION_TYPES:
        raise HTTPException(status_code=422, detail="unsupported correction_type")
    if (
        not isinstance(source_id, str)
        or re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,119}", source_id) is None
    ):
        raise HTTPException(status_code=422, detail="source_id is required")
    if not isinstance(target_input, dict) or not isinstance(proposed_input, dict):
        raise HTTPException(status_code=422, detail="target and proposed must be objects")
    policy = correction_policy.policy_for(source_id)
    if policy is not None:
        try:
            correction_policy.validate_type(source_id, str(correction_type))
        except correction_policy.CorrectionPolicyError as exc:
            raise _correction_error(exc) from exc
    match_id = target_input.get("match_id")
    if correction_type != "missing_fixture" and not isinstance(match_id, str):
        raise HTTPException(status_code=422, detail="an exact match_id is required")
    async def propose(
        stable: matches.StableGeneration,
    ) -> tuple[dict[str, Any], bool]:
        match = await run_in_threadpool(
            _match_for_correction,
            match_id if isinstance(match_id, str) else None,
            stable.snapshot,
        )
        stable.require_stable()
        if correction_type != "missing_fixture" and match is None:
            raise HTTPException(status_code=404, detail="match not found")
        original = correction_validation.derive_original(str(correction_type), match)
        kind = {
            "missing_fixture": "fixture_candidate",
            "team_alias": "team",
            "venue": "venue",
        }.get(str(correction_type), "match")
        target = {
            "kind": kind,
            "match_id": match_id if isinstance(match_id, str) else None,
            # Entity identities are never accepted from the client. Phase 6
            # anchors aliases/venues to the exact indexed match; a later
            # reviewed registry workflow may derive a stable entity id.
            "entity_id": None,
            "upstream_record_key": (
                proposed.get("upstream_record_key")
                if correction_type == "missing_fixture"
                else match.get("upstream_fixture_key")
                if match
                else None
            ),
            "base_generation_id": stable.generation_id,
            "index_fingerprint": stable.snapshot.fingerprint,
        }
        return await run_in_threadpool(
            correction_store.create_proposal,
            _correction_root(),
            correction_type=str(correction_type),
            target=target,
            original=original,
            proposed=proposed,
            source_id=source_id,
            generation_commit=stable.commit,
        )

    try:
        proposed = correction_validation.normalize_proposed(proposed_input)
        assert isinstance(proposed, dict)
        proposal, created = await matches.run_on_stable_generation(
            propose,
            detail="verified match index changed while creating the correction; retry",
        )
    except matches.MatchIndexUnavailable as exc:
        raise HTTPException(status_code=503, detail="match index unavailable") from exc
    except (correction_store.CorrectionStoreError, correction_policy.CorrectionPolicyError) as exc:
        raise _correction_error(exc) from exc
    return JSONResponse(status_code=201 if created else 200, content=proposal)


@app.get("/api/v1/corrections/missing-fixtures")
def local_missing_fixtures() -> dict[str, Any]:
    try:
        result = correction_store.list_proposals(
            _correction_root(), accepted_only=True, limit=100, offset=0
        )
    except correction_store.CorrectionStoreError as exc:
        raise _correction_error(exc) from exc
    result["items"] = [
        item for item in result["items"] if item["correction_type"] == "missing_fixture"
    ]
    result["total"] = len(result["items"])
    return result


@app.get("/api/v1/corrections/{proposal_id}")
def get_correction(proposal_id: str) -> dict[str, Any]:
    try:
        return correction_store.get_proposal(_correction_root(), proposal_id, include_events=True)
    except correction_store.CorrectionStoreError as exc:
        raise _correction_error(exc) from exc


@app.put("/api/v1/corrections/{proposal_id}/draft")
async def revise_correction(proposal_id: str, request: Request) -> dict[str, Any]:
    body = await _correction_body(request)
    if not isinstance(body.get("proposed"), dict) or not isinstance(
        body.get("expected_head_event_id"), str
    ):
        raise HTTPException(
            status_code=422, detail="proposed and expected_head_event_id are required"
        )
    try:
        proposed = correction_validation.normalize_proposed(body["proposed"])
        assert isinstance(proposed, dict)
        return await run_in_threadpool(
            correction_store.revise_draft,
            _correction_root(),
            proposal_id,
            proposed,
            str(body["expected_head_event_id"]),
        )
    except correction_store.CorrectionStoreError as exc:
        raise _correction_error(exc) from exc


@app.post("/api/v1/corrections/{proposal_id}/evidence")
async def attach_correction_evidence(proposal_id: str, request: Request) -> JSONResponse:
    body = await _correction_body(request)
    source_url = body.get("source_url")
    captured_text = body.get("captured_text")
    revision = body.get("source_revision")
    if not isinstance(source_url, str) or not isinstance(captured_text, str):
        raise HTTPException(status_code=422, detail="source_url and captured_text are required")
    if revision is not None and (not isinstance(revision, str) or len(revision) > 200):
        raise HTTPException(status_code=422, detail="source_revision must be a short string")
    try:
        proposal = correction_store.get_proposal(_correction_root(), proposal_id)
        canonical_url, hostname = correction_policy.canonical_evidence_url(
            proposal.get("source_id"), source_url
        )
        raw, display = correction_sanitize.sanitize(captured_text)
        result, created = await run_in_threadpool(
            correction_store.attach_evidence,
            _correction_root(),
            proposal_id,
            source_url=canonical_url,
            hostname=hostname,
            source_revision=(
                correction_validation.normalize_proposed(revision)
                if isinstance(revision, str)
                else None
            ),
            raw=raw,
            evidence_receipt=correction_sanitize.receipt(raw, display),
        )
    except (
        correction_store.CorrectionStoreError,
        correction_policy.CorrectionPolicyError,
        correction_sanitize.EvidenceError,
    ) as exc:
        raise _correction_error(exc) from exc
    return JSONResponse(status_code=201 if created else 200, content=result)


@app.post("/api/v1/corrections/{proposal_id}/validate")
async def validate_correction(proposal_id: str) -> dict[str, Any]:
    try:
        proposal = correction_store.get_proposal(_correction_root(), proposal_id)
        current = (
            _missing_fixture_match(proposal)
            if proposal["correction_type"] == "missing_fixture"
            else _match_for_correction(proposal["target"].get("match_id"))
        )
        return await run_in_threadpool(
            correction_validation.validate,
            _correction_root(),
            proposal_id,
            current_match=current,
        )
    except matches.MatchIndexUnavailable as exc:
        raise HTTPException(status_code=503, detail="match index unavailable") from exc
    except (correction_store.CorrectionStoreError, correction_policy.CorrectionPolicyError) as exc:
        raise _correction_error(exc) from exc


@app.post("/api/v1/corrections/{proposal_id}/accept-local")
async def accept_local_correction(proposal_id: str, request: Request) -> dict[str, Any]:
    body = await _correction_body(request)
    if body.get("confirm") != "local_annotation_only" or not isinstance(
        body.get("expected_head_event_id"), str
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "confirm must equal local_annotation_only and expected_head_event_id is required"
            ),
        )
    try:
        proposal = correction_store.get_proposal(_correction_root(), proposal_id)
        state = (
            "accepted_local" if proposal["state"] == "validated_candidate" else proposal["state"]
        )
        return await run_in_threadpool(
            correction_store.transition,
            _correction_root(),
            proposal_id,
            allowed={"validated_candidate", "exported"},
            state=state,
            event_type="accepted_local",
            payload={
                "scope": "local_annotation_only",
                "authoritative_override": False,
                "verification_level": proposal["verification_level"],
            },
            local_visibility="local_annotation",
            expected_head_event_id=body["expected_head_event_id"],
        )
    except correction_store.CorrectionStoreError as exc:
        raise _correction_error(exc) from exc


@app.post("/api/v1/corrections/{proposal_id}/revoke-local")
async def revoke_local_correction(proposal_id: str, request: Request) -> dict[str, Any]:
    body = await _correction_body(request)
    if not isinstance(body.get("expected_head_event_id"), str):
        raise HTTPException(status_code=422, detail="proposal version is required")
    try:
        proposal = correction_store.get_proposal(_correction_root(), proposal_id)
        state = (
            "validated_candidate" if proposal["state"] == "accepted_local" else proposal["state"]
        )
        return await run_in_threadpool(
            correction_store.transition,
            _correction_root(),
            proposal_id,
            allowed={"accepted_local", "exported", "submitted"},
            state=state,
            event_type="acceptance_revoked",
            payload={"local_annotation_removed": True},
            local_visibility="queue_only",
            expected_head_event_id=body.get("expected_head_event_id"),
        )
    except correction_store.CorrectionStoreError as exc:
        raise _correction_error(exc) from exc


@app.post("/api/v1/corrections/{proposal_id}/withdraw")
async def withdraw_correction(proposal_id: str, request: Request) -> dict[str, Any]:
    body = await _correction_body(request)
    if not isinstance(body.get("expected_head_event_id"), str):
        raise HTTPException(status_code=422, detail="proposal version is required")
    try:
        return await run_in_threadpool(
            correction_store.transition,
            _correction_root(),
            proposal_id,
            allowed=correction_store.ACTIVE_STATES,
            state="withdrawn",
            event_type="withdrawn",
            payload={"reason": body.get("reason") if isinstance(body.get("reason"), str) else None},
            local_visibility="queue_only",
            expected_head_event_id=body.get("expected_head_event_id"),
        )
    except correction_store.CorrectionStoreError as exc:
        raise _correction_error(exc) from exc


@app.post("/api/v1/corrections/{proposal_id}/exports")
async def export_correction(proposal_id: str, request: Request) -> dict[str, Any]:
    body = await _correction_body(request)
    if body.get("confirm") != "reviewed_for_public_export" or not isinstance(
        body.get("expected_head_event_id"), str
    ):
        raise HTTPException(
            status_code=422,
            detail="public export review confirmation and proposal version are required",
        )
    try:
        return await run_in_threadpool(
            correction_exports.export_proposal,
            _correction_root(),
            proposal_id,
            expected_head_event_id=body["expected_head_event_id"],
        )
    except correction_store.CorrectionStoreError as exc:
        raise _correction_error(exc) from exc


@app.post("/api/v1/corrections/{proposal_id}/mark-submitted")
async def mark_correction_submitted(proposal_id: str, request: Request) -> dict[str, Any]:
    body = await _correction_body(request)
    if body.get("confirm") != "submitted_externally" or not isinstance(
        body.get("expected_head_event_id"), str
    ):
        raise HTTPException(
            status_code=422,
            detail="external submission confirmation and proposal version are required",
        )
    try:
        current = correction_store.get_proposal(_correction_root(), proposal_id)
        if current["head_event_id"] != body["expected_head_event_id"]:
            raise correction_store.CorrectionStoreError(
                "proposal_changed", "proposal changed in another view"
            )
        if current["state"] == "submitted":
            return current
        return await run_in_threadpool(
            correction_store.transition,
            _correction_root(),
            proposal_id,
            allowed={"exported"},
            state="submitted",
            event_type="marked_submitted",
            payload={
                "self_attested": True,
                "external_reference": body.get("external_reference")
                if isinstance(body.get("external_reference"), str)
                else None,
            },
            expected_head_event_id=body.get("expected_head_event_id"),
        )
    except correction_store.CorrectionStoreError as exc:
        raise _correction_error(exc) from exc


@app.post("/api/v1/corrections/{proposal_id}/evidence/{evidence_id}/redact")
async def redact_correction_evidence(
    proposal_id: str, evidence_id: str, request: Request
) -> dict[str, Any]:
    body = await _correction_body(request)
    if body.get("confirm") != "redact_local_evidence" or not isinstance(
        body.get("expected_head_event_id"), str
    ):
        raise HTTPException(
            status_code=422,
            detail="evidence redaction confirmation and proposal version are required",
        )
    try:
        return await run_in_threadpool(
            correction_store.redact_evidence,
            _correction_root(),
            proposal_id,
            evidence_id,
            expected_head_event_id=body["expected_head_event_id"],
        )
    except correction_store.CorrectionStoreError as exc:
        raise _correction_error(exc) from exc


@app.delete("/api/v1/corrections")
async def purge_corrections(request: Request) -> dict[str, Any]:
    body = await _correction_body(request)
    if body.get("confirm") != "remove_all_local_corrections":
        raise HTTPException(
            status_code=422, detail="full correction removal confirmation is required"
        )
    try:
        return await run_in_threadpool(correction_store.purge, _correction_root())
    except correction_store.CorrectionStoreError as exc:
        raise _correction_error(exc) from exc


@app.get("/api/v1/matches/{match_id}/corrections")
def match_corrections(match_id: str) -> dict[str, Any]:
    try:
        return correction_store.list_proposals(
            _correction_root(), match_id=match_id, accepted_only=True, limit=100, offset=0
        )
    except correction_store.CorrectionStoreError as exc:
        raise _correction_error(exc) from exc


@app.get("/api/v1/research/capabilities")
def match_research_capabilities() -> dict[str, Any]:
    settings = research_settings.read(_research_root())
    try:
        fingerprint = matches.index_fingerprint()
    except matches.MatchIndexUnavailable:
        fingerprint = None
    return {
        "schema_version": "0.1.0",
        "supported": True,
        "write_enabled": RESEARCH_DIR is not None,
        "enabled": bool(settings["enabled"]),
        "foreground_only": True,
        "automatic_fetch": False,
        "built_in_general_search": False,
        "cloud_ai_extraction": False,
        "authoritative_output": False,
        "max_pages_per_run": 4,
        "max_raw_bytes_per_page": 524288,
        "searxng_supported": False,
        "current_index_fingerprint": fingerprint,
        "sources": [
            policy.public()
            for policy in sorted(
                research_policy.source_policies().values(), key=lambda value: value.source_id
            )
        ],
    }


@app.get("/api/v1/research/settings")
def get_match_research_settings() -> dict[str, Any]:
    return research_settings.read(_research_root())


@app.put("/api/v1/research/settings")
async def put_match_research_settings(request: Request) -> dict[str, Any]:
    body = await _research_body(request)
    try:
        return await run_in_threadpool(research_settings.write, _research_root(), body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/v1/research/discoveries")
async def discover_match_sources(request: Request) -> dict[str, Any]:
    body = await _research_body(request)
    if body.get("confirm") != "discover_sources":
        raise HTTPException(status_code=422, detail="discovery confirmation is required")
    settings = research_settings.read(_research_root())
    if settings["enabled"] is not True:
        raise HTTPException(status_code=409, detail="match research is disabled")
    query = body.get("query")
    provider = body.get("provider", "wikimedia")
    if not isinstance(query, str) or not query.strip() or len(query) > 240:
        raise HTTPException(status_code=422, detail="a short discovery query is required")
    if provider != "wikimedia":
        raise HTTPException(status_code=422, detail="unsupported discovery provider")
    try:
        items = await run_in_threadpool(match_research.discover, query, provider=provider, limit=6)
    except (research_policy.ResearchPolicyError, match_research.ResearchFetchError) as exc:
        raise _research_error(exc) from exc
    return {
        "schema_version": "0.1.0",
        "provider": provider,
        "query": " ".join(query.split()),
        "items": items,
        "disclosure": "Discovery results are candidate URLs only; no snippet is evidence.",
    }


@app.post("/api/v1/research/runs")
async def create_match_research_run(
    request: Request, background_tasks: BackgroundTasks
) -> JSONResponse:
    from golavo_server import ai_gateway, jobs

    body = await _research_body(request)
    if body.get("confirm") != "fetch_selected_sources":
        raise HTTPException(status_code=422, detail="source-fetch confirmation is required")
    settings = research_settings.read(_research_root())
    if settings["enabled"] is not True:
        raise HTTPException(status_code=409, detail="match research is disabled")
    match_id = body.get("match_id")
    selected_urls = body.get("selected_urls")
    if (
        not isinstance(match_id, str)
        or not isinstance(selected_urls, list)
        or not all(isinstance(value, str) for value in selected_urls)
    ):
        raise HTTPException(status_code=422, detail="match_id and selected_urls are required")
    expected = body.get("expected_index_fingerprint")
    if not isinstance(expected, str):
        raise HTTPException(
            status_code=409, detail="match index changed; reload before researching"
        )
    canonical_urls: list[str] = []
    try:
        for value in selected_urls:
            canonical_urls.append(research_policy.canonicalize_url(value)[0])
    except research_policy.ResearchPolicyError as exc:
        raise _research_error(exc) from exc
    provider_config: dict[str, Any] | None = None
    if body.get("allow_local_ai") is True:
        requested = body.get("local_ai")
        if not isinstance(requested, dict):
            raise HTTPException(status_code=422, detail="local_ai configuration is required")
        try:
            resolved = ai_gateway.resolve_provider(requested)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if resolved.provider not in ai_gateway.LOCAL_PROVIDERS:
            raise HTTPException(status_code=422, detail="research extraction accepts local AI only")
        provider_config = requested
    try:
        await run_in_threadpool(
            research_store.prune, _research_root(), int(settings["retention_days"])
        )
        for _attempt in range(3):
            snapshot = matches.index_snapshot()
            if expected != snapshot.fingerprint:
                raise HTTPException(
                    status_code=409, detail="match index changed; reload before researching"
                )
            match = _match_for_correction(match_id, snapshot)
            if match is None:
                if matches.snapshot_is_current(snapshot):
                    raise HTTPException(status_code=404, detail="match not found")
                continue
            try:
                run = await run_in_threadpool(
                    research_store.create_run,
                    _research_root(),
                    match_id=match_id,
                    index_fingerprint=snapshot.fingerprint,
                    selected_urls=canonical_urls,
                    allow_local_ai=provider_config is not None,
                    generation_commit=lambda operation, snapshot=snapshot: (
                        matches.apply_if_snapshot_current(snapshot, operation)
                    ),
                )
            except research_store.ResearchStoreError as exc:
                if exc.reason_code == "index_generation_changed":
                    continue
                raise
            break
        else:
            raise matches.MatchIndexUnavailable(
                "verified match index changed while creating the research run; retry"
            )
        jobs.AI_LANE.start(run["run_id"])
    except matches.MatchIndexUnavailable as exc:
        raise HTTPException(status_code=503, detail="match index unavailable") from exc
    except (research_store.ResearchStoreError, jobs.JobConflict) as exc:
        if isinstance(exc, research_store.ResearchStoreError):
            raise _research_error(exc) from exc
        raise HTTPException(status_code=409, detail="research run already active") from exc

    def _run() -> None:
        try:
            result = match_research.execute_run(
                _research_root(),
                run=run,
                match=match,
                provider_config=provider_config,
                cancel=lambda: jobs.store().is_cancelled(run["run_id"]),
            )
            jobs.store().finish(run["run_id"], result=result)
        except Exception:
            try:
                research_store.update_run(
                    _research_root(),
                    run["run_id"],
                    state="failed",
                    reason_codes=["unexpected_research_failure"],
                )
            finally:
                jobs.store().fail(run["run_id"], "research run failed")

    background_tasks.add_task(_run)
    return JSONResponse(status_code=202, content=run)


@app.get("/api/v1/research/runs")
def list_match_research_runs(match_id: str, limit: int = 10) -> dict[str, Any]:
    from golavo_server import jobs

    if not match_id or len(match_id) > 200:
        raise HTTPException(status_code=422, detail="a match_id is required")
    try:
        runs = research_store.list_runs(_research_root(), match_id=match_id, limit=limit)
        recovered: list[dict[str, Any]] = []
        for run in runs:
            if run["state"] not in research_store.TERMINAL_RUN_STATES:
                job = jobs.store().get(run["run_id"])
                if job is None or job.state != "running":
                    run = research_store.update_run(
                        _research_root(),
                        run["run_id"],
                        state="cancelled",
                        reason_codes=[*run["reason_codes"], "app_interrupted"],
                    )
            recovered.append(
                {
                    **run,
                    "candidates": research_store.list_candidates(_research_root(), run["run_id"]),
                }
            )
        return {"schema_version": "0.1.0", "items": recovered, "total": len(recovered)}
    except research_store.ResearchStoreError as exc:
        raise _research_error(exc) from exc


@app.get("/api/v1/research/runs/{run_id}")
def get_match_research_run(run_id: str) -> dict[str, Any]:
    try:
        run = research_store.get_run(_research_root(), run_id)
        return {**run, "candidates": research_store.list_candidates(_research_root(), run_id)}
    except research_store.ResearchStoreError as exc:
        raise _research_error(exc) from exc


@app.post("/api/v1/research/runs/{run_id}/cancel")
def cancel_match_research_run(run_id: str) -> dict[str, Any]:
    from golavo_server import jobs

    try:
        run = research_store.get_run(_research_root(), run_id)
    except research_store.ResearchStoreError as exc:
        raise _research_error(exc) from exc
    cancelled = jobs.store().cancel(run_id)
    if cancelled:
        run = research_store.update_run(
            _research_root(), run_id, state="cancelled", reason_codes=["cancelled"]
        )
    return {"run_id": run_id, "cancelled": cancelled, "run": run}


@app.post("/api/v1/research/candidates/{candidate_id}/queue")
async def queue_research_candidate(candidate_id: str, request: Request) -> JSONResponse:
    body = await _research_body(request)
    if body.get("confirm") != "add_to_correction_queue":
        raise HTTPException(status_code=422, detail="correction-queue confirmation is required")
    try:
        namespace, candidate = research_store.get_candidate_record(_research_root(), candidate_id)
        if candidate.get("candidate_id") != candidate_id:
            raise research_store.ResearchStoreError(
                "candidate_id_mismatch", "research candidate identity mismatch", 503
            )
        source_id = str(candidate.get("source", {}).get("source_id") or "")
        source_policy = research_policy.source_policies().get(source_id)
        if source_policy is None:
            raise research_store.ResearchStoreError(
                "candidate_source_unavailable", "research candidate source is unavailable", 409
            )
        receipt, _raw_capture = research_store.load_capture(
            _research_root(), namespace, str(candidate["evidence"]["capture_id"])
        )
        research_extract.validate_stored_candidate(
            candidate, policy=source_policy, namespace=namespace, capture=receipt
        )
    except research_store.ResearchStoreError as exc:
        raise _research_error(exc) from exc
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "reason_code": "candidate_verification_failed",
                "message": "research candidate failed evidence verification",
            },
        ) from exc
    if body.get("expected_candidate_sha256") != candidate_id.removeprefix("cf_"):
        raise HTTPException(status_code=409, detail="research candidate changed")
    try:
        snapshot = matches.index_snapshot()
    except matches.MatchIndexUnavailable as exc:
        raise HTTPException(status_code=503, detail="match index unavailable") from exc
    if (
        body.get("expected_index_fingerprint") != snapshot.fingerprint
        or candidate["target"]["index_fingerprint"] != snapshot.fingerprint
    ):
        raise HTTPException(
            status_code=409, detail="match index changed; research candidate is stale"
        )
    if candidate.get("queued_proposal_id"):
        if not matches.apply_if_snapshot_current(snapshot, lambda: None):
            raise HTTPException(
                status_code=409, detail="match index changed; research candidate is stale"
            )
        proposal = correction_store.get_proposal(
            _correction_root(), str(candidate["queued_proposal_id"]), include_events=True
        )
        return JSONResponse(status_code=200, content={"candidate": candidate, "proposal": proposal})
    match = _match_for_correction(candidate["target"]["match_id"], snapshot)
    if match is None:
        raise HTTPException(status_code=409, detail="target match is no longer available")
    if not matches.snapshot_is_current(snapshot):
        raise HTTPException(
            status_code=409, detail="match index changed; research candidate is stale"
        )
    source_id = str(candidate["source"]["source_id"])
    correction_type = str(candidate["correction_type"])
    try:
        correction_policy.validate_type(source_id, correction_type)
        proposed = correction_validation.normalize_proposed(candidate["proposed"])
        original = correction_validation.derive_original(correction_type, match)
        target = {
            "kind": "team" if correction_type == "team_alias" else "venue",
            "match_id": match["match_id"],
            "entity_id": candidate["target"].get("entity_id"),
            "upstream_record_key": match.get("upstream_fixture_key"),
            "base_generation_id": None,
            "index_fingerprint": snapshot.fingerprint,
        }
        proposal, created = await run_in_threadpool(
            correction_store.create_proposal,
            _correction_root(),
            correction_type=correction_type,
            target=target,
            original=original,
            proposed=proposed,
            source_id=source_id,
            generation_commit=lambda operation, snapshot=snapshot: (
                matches.apply_if_snapshot_current(snapshot, operation)
            ),
        )
        if not matches.snapshot_is_current(snapshot):
            raise research_store.ResearchStoreError(
                "index_generation_changed",
                "match index changed before research evidence was attached",
                409,
            )
        source_url, hostname = correction_policy.canonical_evidence_url(
            source_id, candidate["source"]["canonical_url"]
        )
        raw, display = correction_sanitize.sanitize(candidate["evidence"]["exact_quote"])
        proposal, _evidence_created = await run_in_threadpool(
            correction_store.attach_evidence,
            _correction_root(),
            proposal["proposal_id"],
            source_url=source_url,
            hostname=hostname,
            source_revision=candidate["source"].get("revision_id"),
            raw=raw,
            evidence_receipt=correction_sanitize.receipt(raw, display),
            research_origin={
                "run_id": candidate["run_id"],
                "candidate_id": candidate_id,
                "capture_id": candidate["evidence"]["capture_id"],
                "capture_raw_sha256": candidate["evidence"]["raw_sha256"],
                "extractor_id": candidate["extractor"]["id"],
                "extractor_version": candidate["extractor"]["version"],
            },
        )
        candidate = research_store.mark_queued(
            _research_root(),
            candidate_id,
            proposal["proposal_id"],
            generation_commit=lambda operation, snapshot=snapshot: (
                matches.apply_if_snapshot_current(snapshot, operation)
            ),
        )
    except (
        correction_store.CorrectionStoreError,
        correction_policy.CorrectionPolicyError,
        correction_sanitize.EvidenceError,
        research_store.ResearchStoreError,
    ) as exc:
        if isinstance(exc, research_store.ResearchStoreError):
            raise _research_error(exc) from exc
        raise _correction_error(exc) from exc
    return JSONResponse(
        status_code=201 if created else 200,
        content={"candidate": candidate, "proposal": proposal},
    )


@app.delete("/api/v1/research/history")
async def purge_match_research(request: Request) -> dict[str, Any]:
    from golavo_server import jobs

    body = await _research_body(request)
    if body.get("confirm") != "remove_local_research_history":
        raise HTTPException(status_code=422, detail="research-history confirmation is required")
    if jobs.store().running_ids(prefix="rr_"):
        raise HTTPException(
            status_code=409,
            detail={
                "reason_code": "research_run_active",
                "message": "cancel the active match research run before clearing history",
            },
        )
    try:
        return await run_in_threadpool(research_store.purge, _research_root())
    except research_store.ResearchStoreError as exc:
        raise _research_error(exc) from exc


@app.get("/api/v1/maps/world")
def get_world_map() -> dict[str, Any]:
    """Committed Natural Earth 1:110m basemap; offline and public domain."""
    try:
        return conditions.world_map()
    except OSError as exc:
        raise HTTPException(status_code=503, detail="offline basemap unavailable") from exc


@app.get("/api/v1/context/capabilities")
def get_context_capabilities() -> dict[str, Any]:
    """Health and scope of the immutable display-only context pack."""
    return context_registry.capabilities(matches.index_fingerprint())


@app.get("/api/v1/matches/{match_id}/conditions")
def get_match_conditions(match_id: str) -> dict[str, Any]:
    """Display-only location, rest and travel context known before this match."""
    try:
        result = conditions.match_conditions(match_id)
    except matches.MatchIndexUnavailable as exc:
        raise HTTPException(status_code=503, detail="match index unavailable") from exc
    except OSError as exc:
        raise HTTPException(status_code=503, detail="context pack unavailable") from exc
    if result is None:
        raise HTTPException(status_code=404, detail="match not found")
    return result


@app.post("/api/v1/matches/{match_id}/weather/refresh")
async def refresh_match_weather(match_id: str, request: Request) -> dict[str, Any]:
    """Consent-gated per-user Open-Meteo fetch of a pre-kickoff forecast for a match.

    Requires an explicit ``{"confirm": "fetch_weather"}`` body: the fetch reaches
    api.open-meteo.com from the user's own machine (keyless, CC-BY, display-only).
    """
    from datetime import UTC, datetime

    from golavo_server import weather

    try:
        body = await request.json()
    except Exception:  # noqa: BLE001 -- a missing/invalid body is a missing consent
        body = {}
    if not isinstance(body, dict) or body.get("confirm") != "fetch_weather":
        raise HTTPException(
            status_code=400,
            detail={
                "reason_code": "consent_required",
                "message": "confirm must equal fetch_weather",
            },
        )
    try:
        return weather.refresh(match_id, now_utc=datetime.now(UTC))
    except weather.WeatherRefreshError as exc:
        raise HTTPException(
            status_code=exc.status,
            detail=_typed_detail(exc),
        ) from exc
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
    try:
        detail["follow"] = follows.get_follow_for_match(match_id, ledger=ARTIFACT_DIR)
    except follows.FollowError:
        # A damaged optional follow store must not hide an otherwise valid match.
        detail["follow"] = None
    return detail


@app.put("/api/v1/matches/{match_id}/follow")
async def follow_match(match_id: str) -> JSONResponse:
    async def follow(stable: matches.StableGeneration) -> JSONResponse:
        detail = await run_in_threadpool(
            matches.get_match,
            match_id,
            forecasts_dir=ARTIFACT_DIR,
            snapshot=stable.snapshot,
        )
        stable.require_stable()
        if detail is None:
            raise HTTPException(status_code=404, detail="match not found")
        source = stable.sources.get(str(detail["match"].get("source_id") or ""), {})
        followed, created = await run_in_threadpool(
            follows.follow_match,
            detail["match"],
            ledger=ARTIFACT_DIR,
            source_ref=source.get("active_ref"),
            source_checked_at_utc=source.get("last_checked_at_utc"),
            generation_id=stable.generation_id,
            index_fingerprint=stable.snapshot.fingerprint,
            generation_commit=stable.commit,
        )
        return JSONResponse(status_code=201 if created else 200, content=followed)

    try:
        return await matches.run_on_stable_generation(
            follow,
            detail="verified match index changed while following the match; retry",
        )
    except matches.MatchIndexUnavailable as exc:
        raise HTTPException(status_code=503, detail="match index unavailable") from exc
    except follows.FollowError as exc:
        raise _follow_error(exc) from exc


def _pick_error(exc: pick_service.PickError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail=_typed_detail(exc),
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
            detail=_typed_detail(exc),
        ) from exc
    except matches.MatchIndexUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail={"reason_code": "engine_warming", "message": "match index unavailable"},
        ) from exc
    return JSONResponse(status_code=201 if result["created"] else 200, content=result)


@app.get("/api/v1/fixtures/check")
def fixtures_check() -> dict[str, Any]:
    """Deprecated compatibility check for pre-refresh UI builds.

    New clients use /api/v1/data/* for approved-source revision checks, immutable
    snapshots and atomic activation. This route stays read-only for one release.
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


@app.get("/api/v1/data/status")
def data_refresh_status() -> dict[str, Any]:
    """Source-specific check, activation, capability and rollback state."""
    return refresh_jobs.status()


@app.post("/api/v1/data/refresh")
async def start_data_refresh(request: Request) -> JSONResponse:
    """Start one approved-source check or check-and-refresh job.

    The sidecar never invokes this route itself. Automatic launch/periodic calls
    originate in the visible UI after the persisted consent policy is read.
    """
    try:
        body = await request.json()
    except (ValueError, json.JSONDecodeError):
        body = {}
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="request body must be an object")
    mode = body.get("mode", "check")
    trigger = body.get("trigger", "manual")
    scope = body.get("scope", "all")
    source_ids = body.get("source_ids")
    if source_ids is not None and not (
        isinstance(source_ids, list) and all(isinstance(item, str) for item in source_ids)
    ):
        raise HTTPException(status_code=422, detail="source_ids must be an array of strings")
    if scope == "followed" and source_ids is not None:
        raise HTTPException(
            status_code=422,
            detail="scope followed derives source_ids from local follows",
        )
    try:
        job, deduplicated = refresh_jobs.coordinator().start(
            mode=str(mode), source_ids=source_ids, trigger=str(trigger), scope=str(scope)
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(
            status_code=422 if isinstance(exc, ValueError) else 503,
            detail={"reason_code": "refresh_unavailable", "message": str(exc)},
        ) from exc
    return JSONResponse(status_code=202, content={**job, "deduplicated": deduplicated})


@app.get("/api/v1/data/refresh/{job_id}")
def get_data_refresh_job(job_id: str) -> dict[str, Any]:
    job = refresh_jobs.coordinator().get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="refresh job not found")
    return job


@app.post("/api/v1/data/refresh/{job_id}/cancel")
def cancel_data_refresh_job(job_id: str) -> dict[str, Any]:
    job = refresh_jobs.coordinator().cancel(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="refresh job not found")
    return job


@app.post("/api/v1/data/rollback")
def rollback_data_refresh() -> dict[str, Any]:
    try:
        return refresh_jobs.rollback()
    except (OSError, RuntimeError, ValueError) as exc:
        raise HTTPException(
            status_code=409,
            detail={"reason_code": "rollback_unavailable", "message": str(exc)},
        ) from exc


@app.get("/api/v1/overlays/openligadb/status")
def openligadb_status() -> dict[str, Any]:
    """Consent, health, license and isolated-generation state for OpenLigaDB."""
    return openligadb_jobs.status()


@app.get("/api/v1/overlays/openligadb/settings")
def openligadb_settings() -> dict[str, Any]:
    status = openligadb_jobs.status()
    return {
        "schema_version": "0.1.0",
        "enabled": status["enabled"],
        "refresh_policy": status["refresh_policy"],
        "selected_competitions": status["selected_competitions"],
        "license": status["license"],
        "display_only": True,
    }


@app.put("/api/v1/overlays/openligadb/settings")
async def update_openligadb_settings(request: Request) -> dict[str, Any]:
    try:
        body = await request.json()
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail="request body must be valid JSON") from exc
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="request body must be an object")
    try:
        openligadb_jobs.configure(body)
    except PermissionError as exc:
        raise HTTPException(
            status_code=409,
            detail={"reason_code": "odbl_consent_required", "message": str(exc)},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"reason_code": "openligadb_settings_rejected", "message": str(exc)},
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=409,
            detail={"reason_code": "openligadb_settings_rejected", "message": str(exc)},
        ) from exc
    except OSError as exc:
        raise HTTPException(
            status_code=503,
            detail={"reason_code": "openligadb_settings_unavailable", "message": str(exc)},
        ) from exc
    return openligadb_jobs.status()


@app.post("/api/v1/overlays/openligadb/refresh")
async def start_openligadb_refresh(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except (ValueError, json.JSONDecodeError):
        body = {}
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="request body must be an object")
    unknown = sorted(set(body) - {"trigger"})
    if unknown:
        raise HTTPException(status_code=422, detail=f"unknown request fields: {unknown}")
    try:
        job, deduplicated = openligadb_jobs.coordinator().start(
            trigger=str(body.get("trigger") or "manual")
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=409,
            detail={"reason_code": "openligadb_not_consented", "message": str(exc)},
        ) from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(
            status_code=422 if isinstance(exc, ValueError) else 503,
            detail={"reason_code": "openligadb_refresh_unavailable", "message": str(exc)},
        ) from exc
    return JSONResponse(status_code=202, content={**job, "deduplicated": deduplicated})


@app.get("/api/v1/overlays/openligadb/refresh/{job_id}")
def get_openligadb_refresh(job_id: str) -> dict[str, Any]:
    job = openligadb_jobs.coordinator().get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="OpenLigaDB refresh job not found")
    return job


@app.post("/api/v1/overlays/openligadb/refresh/{job_id}/cancel")
def cancel_openligadb_refresh(job_id: str) -> dict[str, Any]:
    job = openligadb_jobs.coordinator().cancel(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="OpenLigaDB refresh job not found")
    return job


@app.post("/api/v1/overlays/openligadb/rollback")
def rollback_openligadb() -> dict[str, Any]:
    try:
        return openligadb_jobs.rollback()
    except (OSError, RuntimeError, ValueError) as exc:
        raise HTTPException(
            status_code=409,
            detail={"reason_code": "openligadb_rollback_unavailable", "message": str(exc)},
        ) from exc


@app.delete("/api/v1/overlays/openligadb")
def delete_openligadb() -> dict[str, Any]:
    try:
        return openligadb_jobs.delete_all()
    except (OSError, RuntimeError, ValueError) as exc:
        raise HTTPException(
            status_code=409,
            detail={"reason_code": "openligadb_delete_rejected", "message": str(exc)},
        ) from exc


def _require_openligadb_enabled() -> None:
    if not openligadb_state.load_settings()["enabled"]:
        raise HTTPException(
            status_code=409,
            detail={
                "reason_code": "openligadb_disabled",
                "message": (
                    "OpenLigaDB is disabled; enable it in Settings before reading overlay data"
                ),
            },
        )


@app.get("/api/v1/overlays/openligadb/competitions")
def get_openligadb_competitions() -> dict[str, Any]:
    _require_openligadb_enabled()
    try:
        return openligadb_overlay.list_competitions()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (OSError, RuntimeError) as exc:
        raise HTTPException(
            status_code=503, detail="OpenLigaDB overlay data is unavailable"
        ) from exc


@app.get("/api/v1/overlays/openligadb/matches")
def get_openligadb_matches(
    shortcut: str | None = None,
    from_utc: str | None = None,
    to_utc: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    _require_openligadb_enabled()
    try:
        return openligadb_overlay.list_matches(
            shortcut=shortcut, from_utc=from_utc, to_utc=to_utc, limit=limit
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (OSError, RuntimeError) as exc:
        raise HTTPException(
            status_code=503, detail="OpenLigaDB overlay data is unavailable"
        ) from exc


@app.get("/api/v1/overlays/openligadb/matches/{source_match_id}")
def get_openligadb_match(source_match_id: int) -> dict[str, Any]:
    _require_openligadb_enabled()
    try:
        result = openligadb_overlay.get_match(source_match_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (OSError, RuntimeError) as exc:
        raise HTTPException(
            status_code=503, detail="OpenLigaDB overlay data is unavailable"
        ) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="OpenLigaDB match not found")
    return result


@app.get("/api/v1/calibration")
def calibration() -> dict[str, Any]:
    """Serve the real sealed→scored calibration record (never eval backtests).

    The record is recomputed from the immutable ledger on each request, so it
    can never drift from the artifacts it summarizes. An empty ledger yields an
    honest zero-count record rather than an error.
    """
    from golavo_core.calibration import calibration_summary  # lazy: see import note above

    return calibration_summary(ARTIFACT_DIR)


@app.post("/api/v1/forecasts/settle")
async def settle_forecasts() -> dict[str, Any]:
    """Check pinned CC0 result sources and settle every eligible local seal.

    This is deliberately a POST and never runs merely because the sidecar
    started: the UI calls it after an explicit "Check results" action, or under
    the user's persisted keep-data-fresh consent.  Source fetching and metric
    work run off the event loop; scoring appends immutable successors and never
    edits the sealed forecast.
    """
    from golavo_server import settlement

    try:
        report = await run_in_threadpool(settlement.settle_pending_forecasts, ARTIFACT_DIR)
        await run_in_threadpool(follows.record_settlement_report, report, ledger=ARTIFACT_DIR)
        return report
    except (OSError, ValueError, ValidationError) as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "reason_code": "ledger_invalid",
                "message": f"the local forecast ledger could not be settled safely: {exc}",
            },
        ) from exc


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

    known_paths = {path.stem: path for path in ARTIFACT_DIR.glob("fa_*.json")}
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
            job = jobs.AI_LANE.start(job_id)
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
            job = jobs.AI_LANE.start(job_id)
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
    report_cards: list[dict[str, Any]] = []
    for summary in summaries:
        folds.extend(summary.get("folds", []))
        report_cards.extend(summary.get("report_cards", []))
    return {
        "schema_version": summaries[0].get("schema_version", "0.1.0"),
        "primary_metric": "log_loss",
        "sources": [summary.get("source_snapshot") for summary in summaries],
        "folds": folds,
        "report_cards": report_cards,
    }
