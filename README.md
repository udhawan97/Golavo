<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/brand/animated/golavo-lockup-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="assets/brand/animated/golavo-lockup-light.svg">
  <img src="assets/brand/animated/golavo-lockup-light.svg" alt="Golavo" width="440">
</picture>

### The numbers remember everything. The beautiful game still keeps the last word.

**Open-source, local-first soccer forecasting for full internationals.**
Phase 0 is a deterministic, local forecasting spike for men's senior full internationals. Broader coverage, AI narration, and desktop distribution are planned in [ADR-0001](docs/adr/0001-architecture.md).

<!-- Badges resolve once the repo is public on GitHub. -->
[![CI](https://github.com/udhawan97/Golavo/actions/workflows/ci.yml/badge.svg)](https://github.com/udhawan97/Golavo/actions/workflows/ci.yml)
[![Release](https://github.com/udhawan97/Golavo/actions/workflows/release.yml/badge.svg)](https://github.com/udhawan97/Golavo/actions/workflows/release.yml)
[![Docs](https://github.com/udhawan97/Golavo/actions/workflows/pages.yml/badge.svg)](https://udhawan97.github.io/Golavo)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

[**Website & Docs**](https://udhawan97.github.io/Golavo) · [Methodology](https://udhawan97.github.io/Golavo/methodology/prediction/) · [Coverage](https://udhawan97.github.io/Golavo/data/coverage/) · [Roadmap](#roadmap)

</div>

> [!WARNING]
> **Status: pre-alpha (Phase 0 — data-feasibility spike).** No installable build yet. This repository is the scaffold and the plan. Coverage claims below describe the *designed* product, not shipped features. Nothing here is a betting product.

---

## What Golavo is

Golavo's Phase 0 engine builds a reproducible 1X2 forecast for a men's senior full international, then **seals** a versioned JSON artifact with its model and source snapshot. A later result snapshot can produce a new scored artifact without rewriting the seal. Exact-score presentation, goalscorers, corners, broader competitions, and a public calibration ledger are planned in [ADR-0001](docs/adr/0001-architecture.md).

**What Golavo is not:** a livescore app (open-core results are delayed), a betting tool (no odds, no picks, no "locks," no bankroll advice), a redistributor of licensed data feeds, or an "AI predictor" (the statistics own the numbers).

## The Local vs AI contract

| | The statistical engine | The AI layer (optional) |
|---|---|---|
| **Owns** | Every probability, score matrix, and count distribution | Narrative, scenario explanation, research |
| **May** | Rerun when a *confirmed* new fact becomes a typed feature | Surface cited facts and propose typed features for the engine |
| **May never** | — | Silently change a probability, or state a number not in its evidence bundle |

The optional AI layer and typed-feature reruns are **planned (ADR-0001)** and are out of Phase 0. Their contract is fixed now so future AI work cannot become a second forecasting oracle.

## How a forecast is made

```
pinned CC0 snapshot ──► typed match table ──► candidate statistical model
         │                                           │
         └── manifest + sha256 ─────────────► sealed forecast artifact
                                                     │
                         newer result snapshot ──────► new scored artifact
```

## Coverage — the honest version

Phase 0 uses one vendored, pinned CC0 snapshot of `martj42/international_results`. It covers men's senior full-international results, goalscorers, shootouts, and former names; the engine currently consumes results and former names. Phase 1 adds the **English Premier League** as a **historical** backbone from a pinned `openfootball` snapshot (CC0-1.0), accepted for completed seasons only after a coverage audit and backtested — **not live**. Lineups, injuries, corners, xG, and BYOK adapters remain out of scope. Free access is not the same as lawful open data — see [Data sources & coverage](https://udhawan97.github.io/Golavo/data/coverage/).

| Phase 0 scope | Results | Goalscorers / shootouts | Lineups / injuries / corners / xG |
|---|---|---|---|
| **Men's senior full internationals** | ✅ CC0, ingested | ✅ CC0 snapshot, not modeled | 🚫 no accepted open source |
| **English Premier League** (historical) | ✅ Phase 1 — openfootball CC0, 15 clean seasons 2010-11→2024-25 | 🚫 out of scope | 🚫 no accepted open source |

The snapshot is reproducible and pinned, not a live feed. xG does not appear in the accepted Phase 0 source.

## Run modes

| Mode | Who it's for | Status |
|---|---|---|
| **Source (local API + core)** | developers, researchers | Phase 0 |
| **Source web app** | developers, researchers | planned (ADR-0001, Phase 2) |
| **Desktop (macOS DMG / Windows EXE)** | everyone | planned (ADR-0001, Phase 4) |

```bash
# Source-mode API (Phase 0)
git clone https://github.com/udhawan97/Golavo.git && cd Golavo
make setup
uvicorn golavo_server.main:app --host 127.0.0.1 --port 8000 --app-dir server
```

## Architecture

Phase 0 ships a Python core, a Parquet typed-match table, JSON forecast artifacts, and a read-only FastAPI surface. A Tauri 2 desktop shell, React UI integration, DuckDB views, SQLite state, and a hash-chained ledger are **planned (ADR-0001)**.

```
core/       Python modeling library — ingest, warehouse, models, ledger, facts   (Apache-2.0)
server/     FastAPI app — routes, jobs, evidence bundles, AI gateway             (Apache-2.0)
ui/         React + TypeScript + Vite                                            (Apache-2.0)
desktop/    planned Tauri 2 shell and updater (ADR-0001)                         (Apache-2.0 code)
packs/      data packs with their own per-pack licenses
docs-site/  Astro + Starlight product site (GitHub Pages)
```

## Prediction methodology

Phase 0 evaluates five deterministic **candidates**: climatological, Elo ordinal-logit, independent Poisson, time-decayed Dixon-Coles, and bivariate Poisson. Log loss is primary; Brier, ECE with reliability bins, and RPS are also reported on chronological tournament folds. No candidate is called a champion until forward evidence earns that status. Phase 1 runs the same five candidates on chronological English Premier League season folds (2022-23, 2023-24, 2024-25); every candidate beats the climatological baseline on log loss, and still none is crowned. Full methodology: [Methodology](https://udhawan97.github.io/Golavo/methodology/prediction/).

> We do **not** claim AI, deep learning, head-to-head records, or a "new-manager bounce" improve accuracy without forward evidence.

## Data sources & licenses

| Source | Role | License | In product? |
|---|---|---|---|
| [martj42/international_results](https://github.com/martj42/international_results) | men's senior full internationals | CC0-1.0 | ✅ Phase 0 pinned pack |
| Transfermarkt-derived datasets · DataHub football mirrors | rejected: downstream labels do not cure upstream provenance/ToS risk | — | 🚫 rejected |
| [openfootball](https://github.com/openfootball/football.json) | English Premier League (historical) | CC0-1.0 | ✅ Phase 1 pinned pack |
| Wikidata · Wyscout · OpenLigaDB | possible later research/adapters | varies | ⏳ out of scope |
| Football-Data.org · API-Football | proprietary data adapters | proprietary ToS | ⏳ out of Phase 0 |

Attribution strings and the full field-level license matrix live in [NOTICE](NOTICE) and the [Legal & brand docs](https://udhawan97.github.io/Golavo/legal/).

## Privacy & security

Phase 0 has no account, telemetry, ads, BYOK keys, AI calls, or updater. Sourcepack construction performs an explicit network download; normal core and API reads use local files. Keychain storage, authenticated desktop sidecars, signed packs, and signed updates are **planned (ADR-0001)**. See [SECURITY.md](SECURITY.md).

## Roadmap

| Phase | Deliverable |
|---|---|
| **0 — Data-feasibility spike** | ingest real matches, one reproducible sealed forecast, backtested & scored, every fact cited |
| **1 — Engine + ledger** | expanded warehouse, planned hash-chained ledger, calibration harness |
| **2 — Source-mode web app** | Matchday, Fixture Room, Forecast Theatre, After the Whistle |
| **3 — BYOK depth** | football-data.org + API-Football typed-feature adapters, confirmed-lineup forecasts |
| **4 — Desktop + release** | Tauri shell, signed updater, notarized DMG + signed EXE, docs site |
| **5+** | scorers & corners, AI Deep Read, fact engine, cups & UEFA depth |

Full detail with entry/exit criteria and kill switches: [Roadmap](https://udhawan97.github.io/Golavo/roadmap/).

## Contributing

Issues and PRs welcome — start with [CONTRIBUTING.md](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md). Golavo's **code** is Apache-2.0; data packs carry their own licenses and manifests.

## License

Golavo's code is licensed under the **Apache License 2.0** ([LICENSE](LICENSE)). Data packs are licensed separately; the Phase 0 martj42 pack is CC0-1.0.

---

<sub>Golavo is not affiliated with, endorsed by, or sponsored by FIFA, UEFA, any league, club, or competition. Competition names are used factually to identify matches. No official logos, emblems, mascots, trophy imagery, crests, or kit designs are used.</sub>
