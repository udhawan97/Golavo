---
title: Roadmap
description: The smallest trustworthy MVP first, with entry/exit criteria and kill switches — then the full aspirational product.
---

Golavo is built data-first. The first phase is a feasibility spike with a real kill criterion, not a foundation-pour.

## MVP

| Phase | Deliverable | Exit criteria | Kill criterion |
|---|---|---|---|
| **0 — Data-feasibility spike** | men's senior full-international ingest; deterministic candidate models; sealed/scored artifacts; read-only API | provenance, schema, determinism, leakage, and chronological evaluation gates pass | accepted open data or a calibration-first baseline proves unusable → rethink scope |
| **1 — Engine + ledger** | expanded warehouse, planned hash-chained ledger, calibration harness | calibration within bands; abstention gates fire correctly | calibration remains unfixable in the chosen scope |
| **2 — Source-mode web app** | Matchday, Fixture Room, Forecast Theatre, After the Whistle; casual/expert; all data states | performance & a11y budgets met; a live matchday sealed and scored | — |
| **3 — BYOK depth** | evaluate lawful typed-feature adapters; confirmed-lineup forecasts only if terms allow | confirmed-lineup seal works; keys never leave the keychain | live API terms prohibit the required use → adapter rejected |
| **4 — Desktop + release** | Tauri shell, signed updater (stable/beta), notarized DMG + signed EXE, docs site | install/update/rollback matrix green on macOS + Windows | sidecar packaging unresolved after 2 focused weeks → fallback shell |

## Full aspirational Golavo

- **5 — Scorers & corners** — internationals scorer module first (CC0); club scorers/corners only if a lawful data source is verified.
- **6 — AI Deep Read** — local-first, then BYOK cloud, with the full AI contract and a CI red-team suite.
- **7 — Fact engine & dossiers** — template registry growth; team/player/manager dossiers from Wikidata + CC0.
- **8 — Cups & UEFA depth** — via BYOK, driven by the coverage ledger; a rules engine for two-legged ties, extra time, and penalties across eras.
- **9 — Community & longevity** — signed community packs, i18n, ODbL overlay opt-in UX.

Each phase carries its own entry/exit criteria, tests, defer list, and kill switch in the planning docs.
