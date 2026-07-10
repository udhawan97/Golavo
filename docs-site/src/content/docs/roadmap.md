---
title: Roadmap
description: The smallest trustworthy MVP first, with entry/exit criteria and kill switches — then the full aspirational product.
---

Golavo is built data-first. The first phase is a feasibility spike with a real kill criterion, not a foundation-pour.

## MVP

| Phase | Deliverable | Exit criteria | Kill criterion |
|---|---|---|---|
| **0 — Data-feasibility spike** | ingest real matches, one reproducible sealed forecast, backtested & scored, every fact cited | Dixon-Coles beats baselines on forward RPS; forecasts are deterministic; provenance complete; CC0 data error rate < 2% | Model can't beat baselines, or open data fails the quality audit → stop and rethink data strategy |
| **1 — Engine + ledger** | Parquet/DuckDB warehouse, hash-chained ledger, calibration harness, 5 leagues + internationals | calibration within bands; abstention gates fire correctly | calibration unfixable in ≥2 leagues |
| **2 — Source-mode web app** | Matchday, Fixture Room, Forecast Theatre, After the Whistle; casual/expert; all data states | performance & a11y budgets met; a live matchday sealed and scored | — |
| **3 — BYOK depth** | football-data.org + API-Football typed-feature adapters; confirmed-lineup forecasts | confirmed-lineup seal works; keys never leave the keychain | live API terms prohibit local caching → adapter degraded |
| **4 — Desktop + release** | Tauri shell, signed updater (stable/beta), notarized DMG + signed EXE, docs site | install/update/rollback matrix green on macOS + Windows | sidecar packaging unresolved after 2 focused weeks → fallback shell |

## Full aspirational Golavo

- **5 — Scorers & corners** — internationals scorer module first (CC0); club scorers/corners only if a lawful data source is verified.
- **6 — AI Deep Read** — local-first, then BYOK cloud, with the full AI contract and a CI red-team suite.
- **7 — Fact engine & dossiers** — template registry growth; team/player/manager dossiers from Wikidata + CC0.
- **8 — Cups & UEFA depth** — via BYOK, driven by the coverage ledger; a rules engine for two-legged ties, extra time, and penalties across eras.
- **9 — Community & longevity** — signed community packs, i18n, ODbL overlay opt-in UX.

Each phase carries its own entry/exit criteria, tests, defer list, and kill switch in the planning docs.
