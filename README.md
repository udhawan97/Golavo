<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/brand/animated/golavo-lockup-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="assets/brand/animated/golavo-lockup-light.svg">
  <img src="assets/brand/animated/golavo-lockup-light.svg" alt="Golavo" width="440">
</picture>

### The numbers remember everything. The beautiful game still keeps the last word.

**Local-first, open-source soccer match intelligence.**
A deterministic engine owns every probability. AI only ever cites, explains, and researches — it never edits a number. Every forecast is *sealed before kickoff* and *scored after full time*.

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

Golavo is the football app whose headline feature is that **it can be checked**. It builds a probabilistic forecast for a match — result, exact-score matrix, and (where data allows) goalscorers and corners — then **seals** that forecast with its model version, feature snapshot, and the content hashes of every source it used. After the match it scores the sealed forecast and adds the result to a public calibration record. Every fact it tells you carries a citation, and missing data is shown as missing, never guessed.

**What Golavo is not:** a livescore app (open-core results are delayed), a betting tool (no odds, no picks, no "locks," no bankroll advice), a redistributor of licensed data feeds, or an "AI predictor" (the statistics own the numbers).

## The Local vs AI contract

| | The statistical engine | The AI layer (optional) |
|---|---|---|
| **Owns** | Every probability, score matrix, and count distribution | Narrative, scenario explanation, research |
| **May** | Rerun when a *confirmed* new fact becomes a typed feature | Surface cited facts and propose typed features for the engine |
| **May never** | — | Silently change a probability, or state a number not in its evidence bundle |

When AI research confirms a fact (e.g. a key player ruled out), it becomes a **typed feature**, the statistical model **reruns**, and the UI shows the delta — e.g. `P(home) 42% → 45% · Kane confirmed out ✓`. Silent adjustment is structurally impossible, not merely discouraged.

## How a forecast is made

```
sources ──► immutable snapshot (sha256) ──► typed features ──► statistical model
   │                                                                   │
   └── every value keeps its source id ─────────────────►  sealed forecast (hash-chained)
                                                                       │
                                              full time ──►  scored vs actual ──► calibration record
```

## Coverage — the honest version

Open-core data is **results-grade and redistributable**. Depth (lineups, injuries, corners, xG) is **bring-your-own-key (BYOK)**: it stays on your machine and is never redistributed. Free access is not the same as open data — see [Data sources & coverage](https://udhawan97.github.io/Golavo/data/coverage/).

| Scope | Results / tables | Goalscorers | Lineups / injuries / corners / xG |
|---|---|---|---|
| **World Cup, Euros, Copa América, AFCON, Asian Cup, Nations League + qualifiers** | ✅ open (CC0) | ✅ open (CC0) | ⛑️ BYOK / partial |
| **Top-5 leagues (PL, La Liga, Bundesliga, Serie A, Ligue 1)** | ✅ open (delayed) | ⛑️ BYOK | ⛑️ BYOK |
| **Champions League** | ✅ open | ⛑️ BYOK | ⛑️ BYOK |
| **Domestic cups, Europa/Conference League, Club World Cup** | 🟡 partial / BYOK | ⛑️ BYOK | ⛑️ BYOK |

International football is Golavo's flagship: **results, scorers, and shootouts are open (CC0) and fresh**. xG appears nowhere in the open core — no legal free source exists.

## Run modes

| Mode | Who it's for | Status |
|---|---|---|
| **Source (local web app)** | developers, researchers | Phase 2 |
| **Desktop (macOS DMG / Windows EXE)** | everyone; signed auto-updates, backup & rollback | Phase 4 |

```bash
# Source mode (planned developer workflow)
git clone https://github.com/udhawan97/Golavo.git && cd Golavo
make dev          # starts the FastAPI core + Vite UI locally on 127.0.0.1
```

## Architecture

Tauri 2 desktop shell with a FastAPI/Python sidecar; React + TypeScript UI; a Parquet + DuckDB analytics warehouse; SQLite for settings, provenance, jobs, and an immutable forecast ledger. See [ADR-0001](docs/adr/0001-architecture.md) and the [Architecture docs](https://udhawan97.github.io/Golavo/architecture/).

```
core/       Python modeling library — ingest, warehouse, models, ledger, facts   (Apache-2.0)
server/     FastAPI app — routes, jobs, evidence bundles, AI gateway             (Apache-2.0)
ui/         React + TypeScript + Vite                                            (Apache-2.0)
desktop/    Tauri 2 shell, capabilities, signed updater                          (Apache-2.0)
packs/      versioned, signed data packs — core-cc0 and overlay-odbl kept apart
docs-site/  Astro + Starlight product site (GitHub Pages)
```

## Prediction methodology

A time-decayed **Dixon-Coles** / **bivariate Poisson** champion over an **Elo** and league-average baseline. Goalscorer allocation is coherent with the team-goal matrix; corners use a negative-binomial model. Everything is forward-backtested with a leakage audit; nothing ships unless it beats the baselines on out-of-sample Rank Probability Score and log loss. Full math and model cards: [Methodology](https://udhawan97.github.io/Golavo/methodology/prediction/).

> We do **not** claim AI, deep learning, head-to-head records, or a "new-manager bounce" improve accuracy without forward evidence.

## Data sources & licenses

| Source | Role | License | In product? |
|---|---|---|---|
| [openfootball](https://github.com/openfootball/football.json) | club fixtures/results backbone | CC0-1.0 | ✅ |
| [martj42/international_results](https://github.com/martj42/international_results) | internationals: results, scorers, shootouts | CC0-1.0 | ✅ |
| [Wikidata](https://www.wikidata.org/wiki/Wikidata:Licensing) | entity resolution & historical facts | CC0-1.0 | ✅ |
| [Wyscout public events](https://figshare.com/collections/Soccer_match_event_dataset/4415000/5) | model development priors | CC BY 4.0 | 🔬 dev only |
| [Open-Meteo](https://open-meteo.com/en/terms) | optional weather features | data CC BY 4.0 | ✅ optional |
| [OpenLigaDB](https://www.openligadb.de) | optional Bundesliga/DFB-Pokal overlay | ODbL 1.0 | 🧱 isolated overlay |
| Football-Data.org · API-Football | depth (lineups, stats) | proprietary ToS | 🔑 BYOK only |
| StatsBomb Open Data | — | restrictive user agreement | 🚫 excluded |

Attribution strings and the full field-level license matrix live in [NOTICE](NOTICE) and the [Legal & brand docs](https://udhawan97.github.io/Golavo/legal/).

## Privacy & security

No account. No telemetry. No ads. The only default network call is the update check, and you can turn it off. BYOK keys live in your OS keychain — never in the database, logs, or exports. Localhost sidecar is bound to `127.0.0.1` behind an ephemeral port and a per-launch token. Data/model packs and updates are signature-verified. See [SECURITY.md](SECURITY.md).

## Roadmap

| Phase | Deliverable |
|---|---|
| **0 — Data-feasibility spike** | ingest real matches, one reproducible sealed forecast, backtested & scored, every fact cited |
| **1 — Engine + ledger** | warehouse, hash-chained ledger, calibration harness, all 5 leagues + internationals |
| **2 — Source-mode web app** | Matchday, Fixture Room, Forecast Theatre, After the Whistle |
| **3 — BYOK depth** | football-data.org + API-Football typed-feature adapters, confirmed-lineup forecasts |
| **4 — Desktop + release** | Tauri shell, signed updater, notarized DMG + signed EXE, docs site |
| **5+** | scorers & corners, AI Deep Read, fact engine, cups & UEFA depth |

Full detail with entry/exit criteria and kill switches: [Roadmap](https://udhawan97.github.io/Golavo/roadmap/).

## Contributing

Issues and PRs welcome — start with [CONTRIBUTING.md](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md). Good first issues are labeled in the tracker. All of Golavo is Apache-2.0, so the code and the science stay freely reusable.

## License

Golavo is licensed under the **Apache License 2.0** ([LICENSE](LICENSE)).

---

<sub>Golavo is not affiliated with, endorsed by, or sponsored by FIFA, UEFA, any league, club, or competition. Competition names are used factually to identify matches. No official logos, emblems, mascots, trophy imagery, crests, or kit designs are used.</sub>
