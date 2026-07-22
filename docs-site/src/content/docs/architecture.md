---
title: Architecture
description: How Golavo turns pinned source bytes into sealed forecasts, serves them through a supervised local sidecar, and keeps optional AI outside the numeric authority boundary.
---

Golavo is a **deterministic forecasting engine wrapped in a thin desktop app**.
The Python core owns the science and every persisted number. FastAPI exposes
those results — read-only, except one append-only route that seals a new
forecast. React renders the workbench. Tauri supervises
the packaged processes. Optional AI is a replaceable explanation client over a
restricted evidence bundle — never a second forecasting engine.

The diagrams below describe the implemented v0.2.0 architecture. DuckDB views,
SQLite state, canonical entity graphs, and a hash-chained multi-artifact ledger
remain **planned in [ADR-0001](https://github.com/udhawan97/Golavo/blob/main/docs/adr/0001-architecture.md)**;
they are not presented here as shipped components.

## System map

The top row is the five-second explanation; the lower map names the actual
processes, boundaries, and source directories. Follow the moving gold signal, or
ignore it entirely when reduced motion is enabled.

[![How Golavo works for users and developers: the desktop shell starts a private local service, React presents read-only views, FastAPI serves validated contracts, and the deterministic Python core owns every forecast number while optional AI stays outside.](/Golavo/assets/golavo-system-architecture.svg)](/Golavo/assets/golavo-system-architecture.svg)

### Responsibility boundaries

| Boundary | Owns | Explicitly does not own | Source of truth |
|---|---|---|---|
| **Tauri shell** | port/token bootstrap, sidecar lifecycle, health gate, webview config, gated updater | forecasts, model state, API data shaping | `desktop/src-tauri/src/lib.rs`, `health.rs`, `updater.rs` |
| **React workbench** | navigation, loading/error/empty states, Casual/Expert presentation, provenance and calibration views | artifact mutation, inline statistics, hidden contract coercion | `ui/src/`, especially `lib/api.ts` and `lib/contract.ts` |
| **FastAPI sidecar** | token gate; forecast / facts / match-search / cockpit-analysis / calibration / evaluation reads; an append-only seal route; optional narration orchestration | statistical computation inline, mutating a stored seal | `server/golavo_server/main.py` |
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
| `GET /api/v1/meta` | app/contract version and forecast source (`sample` vs `ledger`) | no |
| `POST /api/v1/shutdown` | desktop-only lifecycle: stop the sidecar tree before a Windows install | no (process only) |
| `GET /api/v1/forecasts` | immutable artifacts, newest first | no |
| `GET /api/v1/forecasts/{artifact_id}` | one canonical artifact | no |
| `GET /api/v1/forecasts/{artifact_id}/facts` | precomputed Commentator's Notebook, or an honest unavailable envelope | no |
| `GET /api/v1/matches/search` | search the deterministic ~77k-match index by team/competition | no |
| `GET /api/v1/matches/competitions` | the competitions present in the index | no |
| `GET /api/v1/matches/recent` | recent results for the Games home | no |
| `GET /api/v1/matches/{match_id}` | one indexed match + its `seal_eligibility` verdict | no |
| `GET /api/v1/matches/{match_id}/conditions` | display-only city, exact local kickoff, pre-match rest, and travel context | no |
| `GET /api/v1/maps/world` | pinned offline Natural Earth 1:110m basemap | no |
| `GET /api/v1/matches/{match_id}/notebook` | on-demand Commentator's Notebook at `kickoff − 1s` | no |
| `GET /api/v1/matches/{match_id}/analysis` | on-demand Match Cockpit (Replay/Preview) model council | no |
| `POST /api/v1/matches/{match_id}/seal` | run the deterministic engine and write an immutable seal for an eligible fixture | **appends** a new artifact; never rewrites one |
| `GET /api/v1/fixtures/check` | opt-in launch-time check for newly-published upcoming internationals | no |
| `GET /api/v1/tournaments/worldcup-2026/outlook` | exact bracket enumeration from current model fits; never a sealed forecast | no |
| `POST /api/v1/tournaments/worldcup-2026/retrospective` | backtest every played 2026 World Cup match at its own pre-kickoff cutoff | no — nothing is persisted or scored as a seal |
| `GET /api/v1/calibration` | recomputed forward record over real sealed→resolved chains | no |
| `POST /api/v1/forecasts/{artifact_id}/narrative` | optional narration over a sealed forecast; may fail back to local-only | narrative only; never the seal |
| `POST /api/v1/matches/{match_id}/narrative` | optional narration over a match's notebook + council | narrative only; never a seal |
| `GET /api/v1/eval/summary` | historical chronological folds, separate from forward evidence | no |

The table above is a representative selection, not the full surface: later
releases added local-only routes for corrections, followed matches, approved-source
refresh, the ODbL overlay, match research, and the World Cup retrospective. Every
one of them is read-only or writes strictly outside the ledger, except the two
named next.

**Two routes write a forecast artifact, and both only ever append.**
`POST /matches/{id}/seal` runs the same deterministic engine as the `golavo seal`
CLI (byte-identical) and appends a new immutable seal; the pack, training cutoff,
and as-of are all resolved server-side, so a seal cannot be backdated or pointed
at an untrusted pack. `POST /forecasts/settle` appends a scored or voided
*successor* once a strictly newer validated source state carries the result. No
route rewrites a sealed artifact — resolution is a new file, never an edit.

`POST /shutdown` only stops the sidecar process tree. The two `narrative` routes
wrap an optional provider call around deterministic evidence and return either
guarded text or a fallback status — they cannot persist or rewrite a forecast.

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

Read the upper rail as a user journey — **collect, prepare, predict, lock,
score, learn**. The lower row is the developer receipt for those same six steps.

[![Golavo's six-step forecast lifecycle: collect a pinned source snapshot, prepare typed matches, predict chronologically, lock the claim before kickoff, score it from a strictly newer state, and learn through forward calibration without rewriting the original seal.](/Golavo/assets/golavo-forecast-lifecycle.svg)](/Golavo/assets/golavo-forecast-lifecycle.svg)

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

The international source publishes dates, not kickoff times. Where a pinned CC0
overlay supplies a verified kickoff, Golavo uses it and marks the row `exact`;
otherwise it falls back to 00:00 UTC on match day as a conservative proxy and
marks the row `day`. It never invents a precise kickoff time, and it never treats
a proxy as if it were one: today 94 of the index's 77,363 rows carry a verified
kickoff, all of them 2026 World Cup fixtures.

That distinction is load-bearing. A date is not a time, so ordering by date alone
treats every fixture on a day as simultaneous — which is exactly how a result from
20:00 could reach a forecast for a match that kicked off at 00:30 that morning.
Training rows are ordered by the sharpest instant each row can prove, and where a
proxy row shares a fixture's calendar day, the surfaces that rely on it disclose
that its order within the day cannot be shown.

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

The upper row answers the ordinary question — *who decides what the forecast
says?* The lower contract shows exactly how code prevents explanation layers from
becoming a second model.

[![Who controls a Golavo forecast: the local deterministic engine makes every number, facts and evidence add sourced context without writer access, and optional AI may explain an allowlisted bundle but cannot edit the sealed forecast.](/Golavo/assets/golavo-intelligence-boundary.svg)](/Golavo/assets/golavo-intelligence-boundary.svg)

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
training-history support. The Model Lab's Track record presents the real forward record. AI
Deep Read optionally adds cited narrative. None of these surfaces recomputes or
overrides the seal.

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
4. A stable build signs every active pack manifest before it enters the frozen sidecar.
5. Release jobs emit DMG / MSI / EXE artifacts, updater signatures, `SHA256SUMS.txt`,
   and a detached signature over that aggregate checksum ledger.
6. OS code signing and notarization remain conditional on platform credentials.

The current public installers are OS-unsigned, so Gatekeeper or SmartScreen may warn.
That platform trust boundary is separate from Golavo's release identity: updater payloads,
official pack manifests, and aggregate checksums are authenticated before use. None of
those release controls can alter a sealed artifact.

## Read the contracts directly

- [`forecast_artifact.schema.json`](https://github.com/udhawan97/Golavo/blob/main/docs/contracts/forecast_artifact.schema.json)
  — the immutable forecast/resolution shape.
- [`forecast_proof.schema.json`](https://github.com/udhawan97/Golavo/blob/main/docs/contracts/forecast_proof.schema.json)
  — the portable offline-verifiable artifact lineage bundle.
- [`evidence_bundle.schema.json`](https://github.com/udhawan97/Golavo/blob/main/docs/contracts/evidence_bundle.schema.json)
  — the constrained input to optional narration.
- [`facts.schema.json`](https://github.com/udhawan97/Golavo/blob/main/docs/contracts/facts.schema.json)
  — the Commentator's Notebook contract.
- [`ai_narration.schema.json`](https://github.com/udhawan97/Golavo/blob/main/docs/contracts/ai_narration.schema.json)
  — the only narrative shape accepted back from a provider.
- [`tournament_retrospective.schema.json`](https://github.com/udhawan97/Golavo/blob/main/docs/contracts/tournament_retrospective.schema.json)
  — the two-layer World Cup backtest, including the typed check that its story and
  skill layers really came from one snapshot.
- [Track record](/Golavo/prediction-ledger/) — the Model Lab's forward record:
  timing, resolution, and verification details.
- [Prediction methodology](/Golavo/methodology/prediction/) — candidate models,
  chronological folds, and metrics.
- [Privacy & security](/Golavo/privacy-security/) — runtime network and key
  handling.
- [ADR-0001](https://github.com/udhawan97/Golavo/blob/main/docs/adr/0001-architecture.md)
  — the desktop decision record and reconsideration triggers.
