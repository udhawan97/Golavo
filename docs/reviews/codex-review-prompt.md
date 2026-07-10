# Golavo — complete research dossier for critical review

Paste everything below the line into Codex (or another reviewing agent). It is **self-contained**: the full data-source research and the current plan are inline, so you can critique them directly rather than re-gathering. Spot-checking is welcome; wholesale re-research is not the task.

---

You are a **principal engineer, football data scientist, open-data licensing lawyer, and adversarial product critic**. Below is (A) the project and its current state, (B) the decisions already made, (C) the *complete* verified data-source research, and (D) what to review and how to report. Your job: **find what is wrong, risky, unsupported, legally shaky, or missing.** Do not rewrite the project. Be specific and evidence-based; prefer a concrete failure case over generic advice.

## A. The project

**Golavo** — a local-first, open-source soccer match-intelligence app. A deterministic statistical engine owns every probability; optional local or BYOK cloud AI provides *cited* narrative only and never changes a number. Every forecast is **sealed before kickoff** (model + feature version + source content-hashes) and **scored after full time** into a public calibration record. It is explicitly **not** a betting product (no odds framing, picks, "locks", or bankroll advice).

- **Code:** https://github.com/udhawan97/Golavo (public) · **Site/docs:** https://udhawan97.github.io/Golavo/ · **License:** Apache-2.0 throughout.
- **Status:** pre-alpha, **Phase 0 (data-feasibility spike)**. The repo is a *scaffold + plan*: README, docs site, CI/CD (CI + signed release + Pages), animated brand, and skeletons for `core/` (Python modeling lib), `server/` (FastAPI `/health`), `ui/` (React+Vite), `desktop/`, `packaging/`, `packs/`, and `docs/adr/0001-architecture.md`. **No forecast engine is implemented yet — deliberate.**

## B. Decisions already made (challenge them; don't merely restate)

- **Architecture:** Tauri 2 desktop shell + FastAPI/Python (PyInstaller) sidecar; React/TS UI; Parquet+DuckDB warehouse; SQLite for settings + an immutable, hash-chained forecast ledger. (ADR-0001, "Option A", staged: source-mode web app for Phases 0–2, desktop in Phase 4.)
- **Prediction:** time-decayed **Dixon-Coles / bivariate Poisson** champion over an **Elo** + league-average baseline; negative-binomial corners; goalscorer allocation coherent with the score matrix; forward-only (rolling-origin) backtesting with a leakage audit; **nothing ships unless it beats the baselines out-of-sample on RPS and log loss.** No claim that AI, deep learning, H2H, form, or a "new-manager bounce" helps without forward evidence.
- **AI contract:** the engine owns all probabilities; AI only cites/explains/researches; confirmed AI facts become *typed features* and rerun the model (delta shown); a numeric whitelist rejects any number not in the evidence bundle; local (Ollama/llama.cpp) + BYOK cloud; no chain-of-thought exposure.
- **Data:** a **three-tier model** (open core / free-local / BYOK) with legal isolation enforced in CI (an ODbL-isolation guard already exists in `scripts/check_license_isolation.sh`).
- **Licensing:** Apache-2.0 (chosen over AGPL to maximize adoption / portfolio value).

## C. Complete data-source research (verified 2026-07-09/10)

**Method:** four rounds of discovery + adversarial verification; ~55 sources fetched and checked against their **primary** license/terms pages (not marketing). Facts (scores, fixtures) are non-copyrightable in most jurisdictions, which is why several "re-licensed" compilations exist — flagged below as *provenance risk*.

### Tier A — OPEN (free + a license that permits redistribution) → shippable open core

| Source | License | Data | Coverage | Fresh | Caveat |
|---|---|---|---|---|---|
| **Transfermarkt datasets** (davidcariboo/player-scores, Kaggle) | **CC0** | 12 relational tables incl. **lineups**, **events (goals/cards/subs)**, appearances, valuations, transfers | 40+ comps incl. **WC 2026, Euro, Copa América, AFCON, Asian Cup**; ~79k games | **CURRENT** (weekly) | ⭐⭐ Keystone. Transfermarkt-sourced → provenance risk. |
| **DataHub.io core league CSVs** | **ODC-PDDL** | results + **shots, corners, cards**, HT, odds | EPL 1993/94→**2025/26** + others | **CURRENT** | Re-licenses football-data.co.uk → provenance risk. |
| **openfootball** | CC0 | fixtures/results | top leagues, incl. 2025/26 | season-lag | (original audit) |
| **martj42/international_results** | CC0 | results + **scorers** + shootouts | all internationals 1872→now | ~48h | (original) flagship internationals |
| **ISDB (OSF)** | CC0 | results | 216k matches, 52 leagues, 2000–2018 | stale | ML-oriented historical |
| **footballcsv** | CC0 | results | England tiers 1–5 + ES/DE | ~2020/21 | historical |
| **European Soccer DB** (Kaggle hugomathien) | **ODbL** (share-alike) | results + lineups + events + **corners** + FIFA ratings + odds | 11 EU leagues 2008–2016 | stale | isolate (copyleft); commercial ambiguous |
| **Wikidata** / **DBpedia** | CC0 / CC-BY-SA | reference facts (entities, managers, venues) | all eras | current | DBpedia SA copyleft |
| **DFL/Bassek 2025** (Nature) · **SoccerTrack v2** | CC-BY / CC-BY+MIT | **tracking + events** | research-scale (few / 10 amateur matches) | static | model-dev only |
| **Wyscout** (figshare, Pappalardo) | CC-BY | event data | top-5 2017/18 + WC2018 + Euro2016 | frozen | model-dev |
| **Mendeley Brazil Série A**, **Harvard national-team migration** | CC-BY / CC0 | results/attendance; migration | Brazil 2003–19; WC 1930–2018 | static | niche |
| Weather: **Meteostat, NOAA/GHCN, ERA5, NASA POWER, DWD** | CC-BY / CC0 | weather | global | current | redistributable (unlike Open-Meteo's non-commercial free API) |
| Venue geo: **GeoNames** (CC-BY), **OpenStreetMap** Nominatim/Overpass (ODbL) | CC-BY / ODbL | coordinates/altitude | global | current | OSM share-alike |

### Tier B — FREE to fetch, NOT redistributable (per-user local fetch; never ship/export)

football-data.co.uk (current results + **corners/shots/cards**/odds) · **Understat** (current club **xG**, unofficial scrape) · **FPL API** (PL minutes/goals, keyless) · **American Soccer Analysis** (MLS/NWSL/USL **xG**) · **TheSportsDB** (broad, ambiguous terms) · **ClubElo** (Elo ratings, no license) · **RSSSF** (deep historical, non-commercial) · `soccerdata` Python lib (Apache-2.0 *code*, scraped *data* not open) · commercial free-tiers/trials (Sportmonks, SportsDataIO, SoccersAPI, Entity Sports, Highlightly, FootyStats, Live-Score, TheStatsAPI, API-Futebol, BSD).

### Tier C — RESTRICTED / avoid

**FBref/Sports-Reference** (richest free data — lineups, minutes, **xG**, scorers — but redistribution/mining prohibited, 10 req/min) · **Understat**, **Sofascore**, **FotMob** (scraping/redistribution forbidden) · **StatsBomb Open Data** (bespoke agreement bars redistribution + commercial use of derived analysis — excluded) · **eatpizzanot/soccer-dataset** (self-declared CC-BY but *license-laundering* over API-Football + football-data.co.uk; invalid) · **EasySoccerData** (conflicting MIT/GPL, scrapes Sofascore) · **sportsopendata.net** (CC-BY but abandoned 2016/17).

### BYOK (keyed adapters, user's own key; private/local display only)

**football-data.org** (free tier: 12 comps, delayed, attribution string required, no post-cancellation reference) · **API-Football** (free tier season-limited; terms grant *no publication license* and bar resale). **OpenLigaDB** (ODbL) is a separate isolated Bundesliga/DFB-Pokal overlay.

### Field-level coverage × best open source

| Data type | Best OPEN + current | Free-local fallback | Status |
|---|---|---|---|
| Fixtures / results / tables | Transfermarkt (CC0), DataHub (PDDL), openfootball | football-data.co.uk | ✅ |
| Goalscorers / events (goals, cards, subs) | Transfermarkt `game_events` (CC0); martj42 (internationals) | FBref | ✅ |
| Lineups / minutes | Transfermarkt `game_lineups` (CC0) | FBref, FPL | ✅ (provenance caveat) |
| Corners / shots / cards | DataHub PDDL | football-data.co.uk | ✅ |
| **xG** | — (only research-scale tracking) | Understat, ASA, FBref | ❌ open; free-local only |
| Injuries / suspensions | — | (none open) | ❌ |
| Women's football | — | (SoccerMon fitness only) | ❌ |
| Weather / venue context | Meteostat/NOAA/ERA5; GeoNames/OSM | — | ✅ |

## D. What to review, and the output format

For **each** dimension, state the strongest objection and a concrete failure case:

1. **Data feasibility & licensing.** Is the three-tier model legally sound and *sufficient* for a trustworthy Phase-0 forecast? Scrutinize the **provenance risk**: Transfermarkt datasets (CC0) and DataHub (PDDL) both re-license third-party-sourced data whose upstream ToS bar scraping — is relying on "facts aren't copyrightable" safe for a shipped, redistributed open core, or a latent takedown/relicense risk? Does ODbL share-alike (European Soccer DB, OpenLigaDB, OSM) contaminate the open core if isolation slips? What happens to a *sealed* forecast if the single current open source changes format or lags?
2. **Prediction science.** Is Dixon-Coles/bivariate-Poisson the right champion given the data actually available open (mostly results + now CC0 lineups/events, but **no open xG**)? Where is leakage most likely (e.g. Transfermarkt's weekly refresh overwriting history; valuations that update post-hoc)? Is the calibration coherent across W/D/L + exact-score + counts? Which advertised features should stay *off* for lack of forward evidence?
3. **Architecture.** Tauri 2 + PyInstaller sidecar vs a source-mode web app or pure-Rust for Phase 0 — is it worth the complexity now? Name the concrete failure modes (sidecar orphan/lifecycle, Windows updater force-exit, signing-key loss) and whether the mitigations suffice. What is over-engineered for pre-alpha?
4. **AI contract.** Can "AI never changes a number" actually hold? Construct a way to slip an unsupported number past the numeric whitelist, or to make prompt-injection (via fetched research pages) alter a displayed probability or exfiltrate a key. Is the typed-feature→rerun loop robust and non-circular?
5. **Security & privacy.** Localhost sidecar token, OS-keychain key storage, signed data/model packs, update manifest, prompt-injection surface — describe the most realistic malicious-pack or local-attacker scenario and whether the design stops it.
6. **Legal / brand.** Is the nominative-fair-use stance on competition names (no crests/kits/trophies/likenesses) safe? Any Apache-2.0-code + data-license interaction problems (shipping CC0/CC-BY/ODbL data alongside Apache code; attribution/NOTICE completeness)?
7. **Roadmap realism.** Is Phase 0 (one reproducible sealed forecast, backtested, every fact cited) achievable with the verified open data? Are the kill criteria real? What is the single most likely reason this stalls?
8. **Scaffold correctness.** Review actual repo files (CI workflows, the license-isolation guard, package manifests, docs vs the verified coverage above) and flag anything that would fail, mislead, or rot.

**Produce:**
- **Executive verdict** (≤200 words): the strongest single argument against building this as planned, and whether Phase-0 scope is the right de-risking move.
- **Findings table**, most-severe first: *Severity (Critical/High/Med/Low) · Dimension · Claim · Concrete failure case · Recommendation · Confidence.*
- **Top 5 risks**, each with a trigger and a kill/mitigation.
- **≤5 blocking questions**, only if genuinely unresolved.
- A closing **"what would change my assessment"** paragraph.

**Rules:** label every material claim **Verified / Inference / Assumption**; do **not** invent coverage, licenses, accuracy numbers, or costs — say so if unsure; cite repo files by path and data claims by source; be concrete. This is a review — identify what is wrong, risky, unsupported, or missing; do not rewrite the code or the plan.
