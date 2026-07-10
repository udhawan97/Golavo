---
title: Architecture
description: What Phase 0 implements and which local-first components remain planned.
---

Phase 0 implements a Python forecasting core, a Parquet typed-match table, immutable JSON forecast artifacts, and a read-only FastAPI surface for men's senior full internationals. The Tauri shell, sidecar lifecycle, DuckDB views, SQLite state, AI gateway, and hash-chained ledger are **planned (ADR-0001)**.

## Component boundaries

```text
ui/        separate Phase 0 UI lane
server/    FastAPI                        — health + read-only forecast/evaluation routes
core/      Python modeling library        — ingest, models, evaluation, seal/score
desktop/   planned (ADR-0001)             — Tauri shell and signed updater
packs/     pinned source snapshots        — manifest, hashes, per-pack license
```

- The server serves artifacts already produced by `core`; sourcepack construction is the only Phase 0 network path.
- UI integration and an evidence-only AI gateway are planned (ADR-0001), not Phase 0 capabilities.

## Local-server lifecycle

Phase 0 runs the source server directly on loopback with CORS limited to the two local Vite origins. There is no authentication in source mode. The tokenized sidecar lifecycle is planned (ADR-0001) for the desktop phase.

## Data integrity

- **Immutable snapshots** — every fetch is stored as a content-addressed blob with a manifest (source, url, license, `retrieved_at`). Forecasts reference snapshot sets and are fully replayable.
- **Team names** — former names are resolved with the dated intervals in martj42's `former_names.csv`.
- **Canonical entity graphs, conflict views, migrations, and SQLite state** — planned (ADR-0001).
