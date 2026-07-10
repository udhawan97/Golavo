---
title: Architecture
description: How Golavo is put together — the desktop shell, the local Python core, the warehouse, and the forecast ledger.
---

Golavo is a Tauri 2 desktop shell driving a local FastAPI/Python sidecar, with a React + TypeScript UI. Analytics live in a Parquet + DuckDB warehouse; settings, provenance, jobs, and the immutable forecast ledger live in SQLite. The full decision and the alternatives considered are in [ADR-0001](https://github.com/udhawan97/Golavo/blob/main/docs/adr/0001-architecture.md).

## Component boundaries

```text
ui/        React + TypeScript + Vite      — never touches data sources directly
server/    FastAPI                        — routes, jobs, evidence bundles, AI gateway
core/      Python modeling library        — ingest, warehouse, models, ledger, facts
desktop/   Tauri 2 shell                  — window, capabilities, signed updater
packs/     signed data packs             — core-cc0 and overlay-odbl kept apart
```

- The UI never talks to sources; the server never computes statistics inline (it calls `core`); `core` never does network I/O outside `ingest`.
- The AI gateway is the only module that talks to language models, and it can only read evidence bundles.

## Local-server lifecycle

The shell spawns the sidecar on `127.0.0.1` with an ephemeral port and a per-launch token; every request must carry the token. A `/health` gate must pass before the window shows. The shell kills the sidecar on exit — and, on Windows, before an update installs (the installer force-exits the app).

## Data integrity

- **Immutable snapshots** — every fetch is stored as a content-addressed blob with a manifest (source, url, license, `retrieved_at`). Forecasts reference snapshot sets and are fully replayable.
- **Canonical entities** — an internal id per team/player/manager/venue/competition, cross-referenced to Wikidata QIDs; name changes seeded from martj42's `former_names.csv`.
- **Conflicts** — per-field source priority; disagreements are surfaced in Data & Model Health, never silently averaged.
- **Migrations** — versioned, with pre-migration backup, row-count verification, and rollback metadata.
