---
title: Architecture
description: The Python forecasting core, the read-only FastAPI surface, and the Phase 4 Tauri desktop shell that supervises a frozen sidecar.
---

Golavo is a Python forecasting core, a Parquet typed-match table, immutable JSON
forecast artifacts, and a read-only FastAPI surface. **Phase 4** adds a Tauri 2
desktop shell that packages the core as a frozen **sidecar** and supervises its
lifecycle. DuckDB views, SQLite state, an AI gateway, and a hash-chained ledger
remain **planned (ADR-0001)**.

## Component boundaries

```text
ui/         React + Vite workbench     — reads the live sidecar, or bundled mocks
server/     FastAPI                    — health + read-only forecast/eval/calibration routes
core/       Python modeling library    — ingest, models, evaluation, seal/score
desktop/    Tauri 2 shell (Phase 4)    — spawns/supervises the sidecar, injects runtime config
packaging/  build tooling              — PyInstaller sidecar + Tauri bundle + checksums
packs/      pinned source snapshots    — manifest, hashes, per-pack license
```

## Desktop shell & sidecar lifecycle (Phase 4)

The shell is a thin Rust process; all forecasting stays in Python. On launch:

1. **Port + token** — the shell binds `127.0.0.1:0` to grab a free loopback port
   and mints a fresh 256-bit token.
2. **Spawn** — it starts the PyInstaller-frozen sidecar
   (`golavo-sidecar-<target-triple>`, a Tauri `externalBin`) with that port and
   token, pointing its ledger at the per-user app-data directory.
3. **Health gate** — it blocks on the sidecar's `/health` (bounded timeout)
   before creating any window.
4. **Config injection** — it builds the window with an initialization script that
   sets `window.__GOLAVO_RUNTIME__ = { apiBase, token }`, so the bundled UI talks
   to the ephemeral port with the token on every request. Nothing is hardcoded.
5. **Teardown** — on every exit path (`RunEvent::ExitRequested`/`Exit`; on
   Windows the installer force-exits before an update) the shell kills the
   sidecar, so no orphaned process remains.

The frozen sidecar resolves its read-only resources (JSON schema, evaluation
summaries) through a source-vs-frozen path abstraction (`golavo_core.resources`),
finding them under `sys._MEIPASS` when frozen and under the repo root in source
mode. Heavy numeric imports (numpy/pandas/scipy) are deferred and warmed in the
background so the readiness gate and window come up in well under a second.

## Security posture

- **Loopback only** — the sidecar binds `127.0.0.1`; the port is ephemeral.
- **Per-launch token** — every request from the shell/UI carries an
  `x-golavo-token` header; the API rejects `/api/*` requests without it. The
  `/health` probe and CORS preflight are exempt.
- **Strict CSP** — the webview allows connections only to `self` and the loopback
  sidecar.
- In source mode the server runs open (no token) with CORS limited to the local
  Vite origins — unchanged from earlier phases, so `make dev` still works.

## Data integrity

- **Immutable snapshots** — every fetch is a content-addressed blob with a
  manifest (source, url, license, `retrieved_at`); forecasts reference snapshot
  sets and are fully replayable.
- **Team names** — former names are resolved with the dated intervals in
  martj42's `former_names.csv`.
- **Canonical entity graphs, conflict views, migrations, and SQLite state** —
  planned (ADR-0001).
