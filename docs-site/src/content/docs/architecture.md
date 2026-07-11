---
title: Architecture
description: How Golavo turns pinned source bytes into sealed forecasts, serves them through a supervised local sidecar, and keeps optional AI outside the numeric authority boundary.
---

Golavo is a **deterministic forecasting engine wrapped in a thin desktop app**.
The Python core owns the science and every persisted number. FastAPI exposes
read-only views of those results. React renders the workbench. Tauri supervises
the packaged processes. Optional AI is a replaceable explanation client over a
restricted evidence bundle — never a second forecasting engine.

The diagrams below describe the implemented v0.2.0 architecture. DuckDB views,
SQLite state, canonical entity graphs, and a hash-chained multi-artifact ledger
remain **planned in [ADR-0001](https://github.com/udhawan97/Golavo/blob/main/docs/adr/0001-architecture.md)**;
they are not presented here as shipped components.

## System map

![Golavo system architecture: the Tauri shell supervises a token-protected loopback FastAPI sidecar; the React workbench reads the API; the deterministic Python core owns all numbers and immutable local data; optional model providers and release automation sit outside the numeric authority boundary.](/Golavo/assets/golavo-system-architecture.svg)

### Responsibility boundaries

| Boundary | Owns | Explicitly does not own | Source of truth |
|---|---|---|---|
| **Tauri shell** | port/token bootstrap, sidecar lifecycle, health gate, webview config, gated updater | forecasts, model state, API data shaping | `desktop/src-tauri/src/lib.rs`, `health.rs`, `updater.rs` |
| **React workbench** | navigation, loading/error/empty states, Casual/Expert presentation, provenance and calibration views | artifact mutation, inline statistics, hidden contract coercion | `ui/src/`, especially `lib/api.ts` and `lib/contract.ts` |
| **FastAPI sidecar** | token gate, read-only forecast/facts/evaluation/calibration routes, optional narration orchestration | statistical computation inline, changing stored seals | `server/golavo_server/main.py` |
| **Deterministic core** | ingest, normalization, candidate models, chronological evaluation, seal/score/void transitions, facts, evidence, calibration | UI state, desktop lifecycle, unrequested network access | `core/golavo_core/` |
| **Data packs + artifacts** | reproducible source bytes, licenses, manifests, retained history, persisted forecast claims | code behavior or mutable live-feed state | `packs/`, `data/artifacts/`, `docs/contracts/` |
| **AI gateway** | provider selection, transport, guard-validated narrative or fail-closed fallback | probability creation or mutation, direct artifact writes | `server/golavo_server/ai_gateway.py`, `core/golavo_core/ai/` |
| **Packaging/release** | frozen sidecar, Tauri bundles, checksums, gated signing/updater assets | runtime forecasting or ledger decisions | `packaging/`, `.github/workflows/release.yml` |

This separation is intentional: a UI bug cannot legitimately create a number,
the desktop shell cannot silently alter a model, and the AI path can disappear
entirely without changing a forecast.

## The packaged request path

The desktop build has one local data path:

```text
Tauri webview
  → React contract client
  → HTTP on an ephemeral 127.0.0.1 port + x-golavo-token
  → FastAPI route
  → golavo-core or an immutable JSON resource
  → validated response
  → read-only workbench view
```

No runtime API hostname is compiled into the UI. The shell injects
`window.__GOLAVO_RUNTIME__ = { apiBase, token }` before the app's scripts run.
The UI data layer reads that object and attaches the per-launch token. This
keeps the packaged path private without creating a remote account or hosted
backend.

### API surface

| Route | Role | Mutation? |
|---|---|---|
| `GET /health` | shell readiness probe; intentionally exempt from the token gate | no |
| `GET /api/v1/forecasts` | immutable artifacts, newest first | no |
| `GET /api/v1/forecasts/{artifact_id}` | one canonical artifact | no |
| `GET /api/v1/forecasts/{artifact_id}/facts` | precomputed Commentator's Notebook, or an honest unavailable envelope | no |
| `GET /api/v1/calibration` | recomputed forward record over real sealed→resolved chains | no |
| `GET /api/v1/eval/summary` | historical chronological folds, separate from forward evidence | no |
| `POST /api/v1/forecasts/{artifact_id}/narrative` | optional narration request; defaults to disabled and may fail back to local-only | narrative only; never the seal |

`POST /narrative` is the sole non-GET app route. It cannot persist or rewrite a
forecast; it wraps an optional provider call around deterministic evidence and
returns either guarded text or a fallback status.

## Desktop shell and sidecar lifecycle

The Rust shell is a supervisor, not a business-logic layer. Before showing a
window it performs this bounded sequence:

1. **Port** — bind `127.0.0.1:0` to reserve a free loopback port.
2. **Token** — mint a fresh 256-bit per-launch token.
3. **State directory** — resolve and create the per-user ledger directory.
4. **Spawn** — start `golavo-sidecar-<target-triple>` with port, token, data
   directory, and parent PID.
5. **Health gate** — poll `/health` for at most 90 seconds. The webview does not
   exist until the sidecar is ready.
6. **Inject** — create the window with its ephemeral API base and token already
   present.
7. **Teardown** — kill the child on both exit event paths. The Python child also
   watches the shell PID as a second orphan-process defense.

The frozen sidecar resolves bundled schemas and evaluation summaries through
`golavo_core.resources`: source mode reads from the repository; frozen mode
reads from PyInstaller's extraction directory. Heavy numeric imports are lazy,
so `/health` and the initial forecast surface are not blocked by calibration
dependencies.

### Security controls

- The sidecar binds to `127.0.0.1`, never `0.0.0.0`.
- Every packaged `/api/*` request needs the fresh `x-golavo-token`; `/health`
  and CORS preflight are the narrow exemptions.
- CORS accepts only the local Vite origins and Tauri webview origins.
- The webview CSP limits connections to itself and the loopback sidecar.
- Cloud AI is off by default and uses an explicit BYOK request. Local provider
  overrides are restricted to HTTP(S) loopback URLs.
- API keys are read from an environment variable or OS keychain, placed only in
  request headers, and omitted from bundles, logs, caches, and response bodies.

## Forecast lifecycle and integrity

![Golavo forecast lifecycle: a pinned source snapshot is normalized and modeled, must pass strict pre-kickoff seal gates, and creates an immutable ForecastArtifact; a strictly newer snapshot later creates a separate scored or voided successor and updates the forward calibration record.](/Golavo/assets/golavo-forecast-lifecycle.svg)

The crucial design decision is that a forecast is a **claim with immutable
bytes**, not the current row in a mutable predictions table.

### 1. Retain the source state

Sourcepack construction writes a new pinned pack instead of overwriting the
previous one. Each pack carries its source, upstream reference, license,
retrieval time, manifest, and SHA-256 coverage. `packs/snapshots.json` registers
retained international snapshots so CI can replay the same scheduled→completed
transition.

### 2. Normalize once, model deterministically

Ingest turns source-specific rows into a typed match table. Team-name history is
resolved by dated intervals. Candidate families run over chronological folds:
climatological, Elo ordinal-logit, independent Poisson, time-decayed
Dixon–Coles, and bivariate Poisson. Model family, version, seed, parameters hash,
and training cutoff are part of the eventual seal.

### 3. Fail the seal if time can leak

`seal_forecast` refuses to write unless all of these hold:

- the snapshot data-state anchor is not later than the seal time;
- the seal time is earlier than the fixture's kickoff proxy;
- every training row is at or before the recorded cutoff; and
- the target fixture is still scheduled in the sealing snapshot.

The international source has dates but no verified kickoff times, so Golavo
uses 00:00 UTC on match day as a conservative proxy. It does not invent a
precise kickoff time.

### 4. Seal the complete numeric claim

The `ForecastArtifact` records W/D/L probabilities, expected goals, and — for
goal-based candidate families — the exact-score grid plus its out-of-grid tail.
Coherence checks prove the stored matrix marginalizes back to the same W/D/L
probabilities and expected goals. The artifact also carries snapshot ids,
generator metadata, deterministic parameters, and a digest over canonical JSON.

### 5. Resolve with a new artifact

Scoring accepts a result only from a validated source state strictly newer than
the seal's. It writes a separate successor with the outcome, assigned
probability, log loss, and Brier score. Postponed or abandoned fixtures produce
a separate voided successor with a reason. One root seal resolves once; the
original file is never rewritten.

### 6. Keep forward evidence separate

`GET /api/v1/calibration` recomputes counts, running quality, reliability bins,
and chain summaries from real seals. Historical evaluation folds live behind a
different endpoint and view. This prevents polished backtest results from being
presented as accumulated pre-kickoff evidence.

### What proves what

| Evidence | What it proves | What it cannot prove alone |
|---|---|---|
| pack manifest + hashes | exact source bytes used | when Golavo published a forecast |
| model/version/seed/params/cutoff | reproducible computation state | that the source state was available publicly at that moment |
| canonical artifact digest | the seal's payload has not changed | wall-clock creation time |
| public git history before kickoff proxy | the genuine forward seal was published in time | that a model is accurate |
| scored successors + calibration | what happened after real seals | performance outside the observed sample |

## Local Intelligence and optional AI

![Golavo intelligence boundary: the deterministic engine owns every probability; facts and the evidence compiler cannot write forecasts; optional AI receives only an allowlisted evidence bundle and is discarded on guard failure; Casual, Expert, Ledger and AI Deep Read share the same sealed numbers.](/Golavo/assets/golavo-intelligence-boundary.svg)

Golavo has three intelligence layers, but only one numeric authority.

### Layer 0 — deterministic engine

Always on and fully local. It produces the complete forecast, score matrix,
sealed metadata, evaluation, and forward calibration. Turning every AI setting
off changes none of those bytes.

### Layer 1 — facts and evidence

The Commentator's Notebook runs pre-registered templates over source history.
Every accepted fact records its label (**predictive**, **context**, or
**coincidence**), sample, denominator, base rate where applicable, date range,
freshness, and source ids. Coincidences are capped and quarantined from AI.

The facts package has a machine-checked dependency invariant: it cannot import
modules that write a forecast, probability, or calibration value. An evidence
compiler then combines the seal and safe facts into a deterministic bundle with
an `allowed_numbers` list. Each allowed number has an id, trusted display string,
unit, label, and source relationship.

### Layer 2 — optional narration

AI receives only the evidence bundle plus separately fenced optional context.
It has no forecast write path. Before text reaches the UI, Golavo checks:

1. output is valid narration-schema JSON;
2. every claim cites allowed source ids;
3. every numeric token exactly matches an allowed display and references the
   correct number id and source;
4. unsupported odds/betting language is absent; and
5. candidate-fact numbers are grounded verbatim in their cited quote when that
   separately gated mode is enabled.

The gateway returns one of four explicit states: `disabled`, `unavailable`,
`local_only`, or `ok`. A malformed, injected, unsupported, or unreachable model
response becomes `local_only`; the app continues with the unchanged forecast.

### Presentation is not a second model

Casual and Expert modes are two reads of the same artifact. Casual mode uses
plain language; Expert mode exposes the seal, provenance, score matrix, and
uncertainty. Ledger presents the real forward record. AI Deep Read optionally
adds cited narrative. None of these surfaces recomputes or overrides the seal.

## Source mode vs packaged mode

| Concern | Source mode | Packaged desktop |
|---|---|---|
| UI | Vite dev server | bundled webview assets |
| API | developer-started Uvicorn | PyInstaller sidecar supervised by Tauri |
| Address | configured local base | ephemeral `127.0.0.1` port injected at launch |
| Token | unset; local development CORS only | fresh 256-bit token required for `/api/*` |
| Data | repository packs/artifacts | bundled read-only resources + per-user ledger directory |
| AI | off unless developer selects a provider | off unless user explicitly selects local or BYOK cloud |
| Exit | processes controlled separately | shell kills sidecar; sidecar watches parent PID |

The shared contracts make these deployment modes equivalent at the app/core
boundary. The workbench validates responses rather than silently adapting to
contract drift.

## Failure behavior

| Failure | Result |
|---|---|
| sidecar cannot start or pass `/health` | no window is shown; child is killed; backed-up user state may be rolled back |
| request lacks the launch token | `401`; no API data is returned |
| API response violates the UI contract | visible error state; malformed data is not rendered as a forecast |
| source snapshot or manifest fails validation | ingest/seal/score operation stops |
| seal invariant fails | no artifact is written |
| newer result is missing/postponed | no fabricated score; write a reasoned void successor when appropriate |
| optional model is absent | `disabled` or `unavailable`; local forecast remains complete |
| narration fails any guard | discard response, return `local_only`, preserve every engine number |
| shell exits unexpectedly | parent-PID watcher terminates the sidecar |

## Build and release boundary

Packaging is downstream of the runtime architecture:

1. PyInstaller freezes the FastAPI/core sidecar and its read-only resources.
2. The build copies it to Tauri's required target-triple filename.
3. Tauri bundles the UI, shell, and sidecar into platform installers.
4. Release jobs emit DMG / MSI / EXE artifacts plus `SHA256SUMS`.
5. Signing, notarization, and the signed updater are wired but enabled only when
   maintainers provide the required secrets.

The current public build is unsigned. Packaging and signing can affect whether
an operating system trusts the bundle, but they cannot participate in forecast
generation or alter a sealed artifact.

## Read the contracts directly

- [`forecast_artifact.schema.json`](https://github.com/udhawan97/Golavo/blob/main/docs/contracts/forecast_artifact.schema.json)
  — the immutable forecast/resolution shape.
- [`evidence_bundle.schema.json`](https://github.com/udhawan97/Golavo/blob/main/docs/contracts/evidence_bundle.schema.json)
  — the constrained input to optional narration.
- [`facts.schema.json`](https://github.com/udhawan97/Golavo/blob/main/docs/contracts/facts.schema.json)
  — the Commentator's Notebook contract.
- [`ai_narration.schema.json`](https://github.com/udhawan97/Golavo/blob/main/docs/contracts/ai_narration.schema.json)
  — the only narrative shape accepted back from a provider.
- [Prediction ledger](/Golavo/prediction-ledger/) — timing, resolution, and
  verification details.
- [Prediction methodology](/Golavo/methodology/prediction/) — candidate models,
  chronological folds, and metrics.
- [Privacy & security](/Golavo/privacy-security/) — runtime network and key
  handling.
- [ADR-0001](https://github.com/udhawan97/Golavo/blob/main/docs/adr/0001-architecture.md)
  — the desktop decision record and reconsideration triggers.
