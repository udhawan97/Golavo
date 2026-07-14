# Golavo — complete research dossier for critical review

Paste everything below the line into Codex (or another reviewing agent). It is **self-contained**: the full data-source research and the current shipped state are inline, so you can critique them directly rather than re-gathering. Spot-checking is welcome; wholesale re-research is not the task.

> Maintenance note (2026-07-11): this dossier previously described Golavo as a scaffold with no engine. That is stale. Golavo's original vision is now **built and released as v0.1.0** (deterministic engine, forward seal→score loop, calibration, exact-score matrix, Fact & Coincidence engine, optional local-first AI, Tauri desktop app). Sections A/B/D below have been rewritten to the shipped reality; Section C (verified data-source research) is unchanged in substance and still governs what is and is not lawfully in scope.

---

You are a **principal engineer, football data scientist, open-data licensing lawyer, and adversarial product critic**. Below is (A) the project and its current shipped state, (B) the decisions already made and executed, (C) the *complete* verified data-source research, and (D) what to review and how to report. Your job: **find what is wrong, risky, unsupported, legally shaky, or missing in the code that actually ships at this commit.** Do not rewrite the project. Be specific and evidence-based; prefer a concrete failure case (with `file:line`) over generic advice.

## A. The project

**Golavo** — a local-first, open-source soccer match-intelligence app. A deterministic statistical engine owns every probability; optional local or BYOK cloud AI provides *cited* narrative only and never changes a number. Every forecast is **sealed before kickoff** (model + feature version + source content-hashes) and **scored after full time** into a public calibration record. It is explicitly **not** a betting product (no odds framing, picks, "locks", or bankroll advice).

- **Code:** https://github.com/udhawan97/Golavo (public) · **Site/docs:** https://udhawan97.github.io/Golavo/ · **Code license:** Apache-2.0; data packs are separately licensed.
- **Status:** **v0.1.0, unsigned pre-alpha — released.** The repo is a *working product*, not a scaffold. Implemented and tested at this commit:
  - **Deterministic core (`core/golavo_core`).** Ingests pinned CC0 sourcepacks into a typed match table; five candidate families (climatological, Elo ordinal-logit, independent Poisson, time-decayed Dixon-Coles, bivariate Poisson); chronological backtests for men's senior full internationals **and** the top-5 European leagues (historical). Forward **seal→score→void** loop writes immutable JSON `ForecastArtifact`s with a content-hash id and an append-only audit log. A real **calibration record** aggregates genuine pre-kickoff seals (starts empty). A goal-based seal additionally carries the **exact-score matrix** it implies (`score_matrix`), machine-checked coherent with the sealed 1X2 and expected goals. A deterministic **Fact & Coincidence engine** (`facts/`) computes source-backed, labelled match facts with a machine-checked no-write invariant.
  - **Optional AI layer (`core/golavo_core/ai`, `server/golavo_server/ai_gateway.py`).** Off by default. A deterministic **evidence bundle** enumerates every number the model may utter; a **numeric whitelist** hard-rejects any narration containing an unsupported number or betting term; keys live only in a request header (never the prompt); a **red-team suite** asserts fail-closed behavior. No live LLM in CI.
  - **Server (`server/golavo_server`).** Read-only FastAPI surface (`/health`, `/api/v1/forecasts`, `/eval/summary`, `/calibration`) plus the optional POST `/narrative`. Loopback bind + per-launch token.
  - **Desktop (`desktop/`, `packaging/`).** Tauri 2 shell + PyInstaller **onefile** sidecar; macOS + Windows bundles built by the release workflow on tag, **unsigned** (signing/notarization gated on absent secrets).
  - **Docs & contracts.** `docs-site/` (Astro), `docs/contracts/` (`ForecastArtifact` + evidence/narration/facts JSON schemas), ADR-0001, and historical implementation handoffs.
  - **Deliberately NOT built (blocked by data or roadmapped):** confirmed lineups, injuries, corners, shots, xG, club-level goalscorers, a club forward loop, cups, typed-feature→rerun, and any signed/notarized release. These have **no lawful open source** (see C) or are gated on secrets/roadmap.

## B. Decisions already made and executed (challenge them; don't merely restate)

- **Architecture:** Python core + read-only FastAPI sidecar + Tauri 2 desktop shell, per ADR-0001. Immutable JSON artifacts + append-only JSONL audit (a cross-artifact hash-chained ledger remains *planned*, honestly labelled).
- **Prediction:** the five families are backtested with **log loss primary** on **chronological** folds; every candidate beats the climatological baseline on every league/international fold in the committed eval summaries. Elo ordinal-logit is the default seal family.
- **Coherence:** sealed 1X2, expected goals, and the exact-score matrix are all derived from **one** fitted joint distribution, so they are coherent *by shared source*; a machine-checked invariant (`score_matrix.py`) enforces it at seal time and on artifact load.
- **AI contract:** the engine owns all numbers; the AI cites/explains only. A numeric whitelist binds value + unit + citation and rejects any number not in the evidence bundle. Local (Ollama/llama.cpp) + BYOK cloud. No chain-of-thought exposure. Off by default.
- **Data:** only pinned CC0 sourcepacks are ingested (martj42 internationals; openfootball top-5 leagues). ODbL (OpenLigaDB) is an **isolated overlay** that ships no data at this commit. The isolation guard is a CI grep lint, **not** legal-isolation enforcement — assess whether that is sufficient.
- **Licensing:** Apache-2.0 (chosen over AGPL to maximize adoption / portfolio value); data packs separately licensed with a NOTICE.

## C. Complete data-source research (verified 2026-07-09/10; unchanged)

**Method:** four rounds of discovery + adversarial verification; ~55 sources fetched and checked against their **primary** license/terms pages (not marketing). Facts (scores, fixtures) are non-copyrightable in most jurisdictions, which is why several "re-licensed" compilations exist — flagged below as *provenance risk*.

### Tier A — OPEN (free + a license that permits redistribution) → shippable open core

| Source | License | Data | Coverage | Fresh | Status at v0.1.0 |
|---|---|---|---|---|---|
| **openfootball** | CC0 | fixtures/results | top leagues, incl. 2025/26 | season-lag | **ingested** (top-5, historical) |
| **martj42/international_results** | CC0 | results + **scorers** + shootouts | all internationals 1872→now | ~48h | **ingested** (results + former names; scorers snapshot-only) |
| **ISDB (OSF)** | CC0 | results | 216k matches, 52 leagues, 2000–2018 | stale | not ingested (historical ML) |
| **footballcsv** | CC0 | results | England tiers 1–5 + ES/DE | ~2020/21 | not ingested |
| **European Soccer DB** (Kaggle hugomathien) | **ODbL** (share-alike) | results + lineups + events + **corners** + FIFA ratings + odds | 11 EU leagues 2008–2016 | stale | **rejected** (copyleft; provenance) |
| **Wikidata** / **DBpedia** | CC0 / CC-BY-SA | reference facts (entities, managers, venues) | all eras | current | not vendored |
| **DFL/Bassek 2025** (Nature) · **SoccerTrack v2** | CC-BY / CC-BY+MIT | **tracking + events** | research-scale | static | model-dev only |
| **Wyscout** (figshare, Pappalardo) | CC-BY | event data | top-5 2017/18 + WC2018 + Euro2016 | frozen | model-dev |
| Weather: **Meteostat, NOAA/GHCN, ERA5, NASA POWER, DWD** | CC-BY / CC0 | weather | global | current | not ingested |
| Venue geo: **GeoNames** (CC-BY), **OpenStreetMap** (ODbL) | CC-BY / ODbL | coordinates/altitude | global | current | not ingested |

### Tier B — FREE to fetch, NOT redistributable (per-user local fetch; never ship/export)

football-data.co.uk (results + **corners/shots/cards**/odds) · **Understat** (club **xG**, unofficial scrape) · **FPL API** (PL minutes/goals) · **American Soccer Analysis** (MLS/NWSL/USL **xG**) · **TheSportsDB** · **ClubElo** · **RSSSF** (non-commercial) · `soccerdata` (Apache code, scraped data not open) · commercial free-tiers/trials.

### Tier C — RESTRICTED / avoid

**Transfermarkt-derived datasets** and **DataHub football mirrors** are **REJECTED** (downstream CC0/PDDL labels do not cure upstream ToS/database-provenance problems). Also rejected: **FBref/Sports-Reference**, **Understat**, **Sofascore**, **FotMob**, unofficial **FPL** endpoints, **European Soccer DB**, **StatsBomb Open Data**, **eatpizzanot/soccer-dataset**, **EasySoccerData**.

### BYOK (keyed adapters, user's own key; private/local display only) — planned, not shipped

**football-data.org** (attribution required) · **API-Football** (no publication license). **OpenLigaDB** (ODbL) is a separate isolated overlay.

### Field-level coverage × best open source

| Data type | Best OPEN + current | Free-local fallback | v0.1.0 status |
|---|---|---|---|
| Fixtures / results / tables | martj42 (internationals) + openfootball (top-5, historical) | — | ✅ ingested |
| Goalscorers / events | martj42 international scorers only | — | snapshot only; not modeled |
| Lineups / minutes | no accepted open source | — | ❌ out of scope |
| Corners / shots / cards | no accepted open source | — | ❌ out of scope |
| **xG** | — (research-scale tracking only) | Understat, ASA, FBref | ❌ open; free-local only |
| Injuries / suspensions | — | (none open) | ❌ out of scope |
| Women's football | — | (SoccerMon fitness only) | ❌ out of scope |
| Weather / venue context | Meteostat/NOAA/ERA5; GeoNames/OSM | — | not ingested |

## D. What to review, and the output format

Review the **shipped v0.1.0 code**, one concrete failure case per finding. For **each** dimension, state the strongest objection with a `file:line` and a concrete reproduction:

1. **Model correctness & coherence.** Do the exact-score matrix marginals reproduce the sealed 1X2 and expected goals on *every* path (seal time, artifact load, and the served API)? Can any goalscorer/scoreline allocation contradict the matrix? Where is chronological leakage most likely (same-day fixtures, cutoff arithmetic, the score→seal training window)? Is the calibration record derivable only from genuine pre-kickoff seals?
2. **Data provenance & legality.** Re-validate every pack from a clean checkout. Is the license-isolation guard sufficient, or a bypassable grep? Can an undeclared file ride inside a "CC0" pack unaudited? Does the *runtime* loader (not just CI) refuse non-CC0 data into the core table? Any provenance/registry drift?
3. **Reproducibility / determinism.** Same snapshot + seed → byte-identical artifacts, on macOS **and** Linux (numeric drift, sort stability, tz, float rounding of the score-matrix grid). Is byte-identity *enforced*, or merely internally consistent?
4. **Security — hardest first.** Can any number flowing into the AI whitelist (matrix cells, facts, scorers) let the model state an **unsupported** number, or reuse a supported number in the wrong semantic role? Can prompt injection (via fetched research or notebook facts) change a *displayed* probability or exfiltrate a key? Assess the localhost token, keychain, pack/updater signing claims, and the server's trust in on-disk artifacts.
5. **Honesty / claims audit at THIS SHA.** Every ✅ / "implemented" / "signed" / coverage / accuracy claim across README, SECURITY.md, docs, docs-site, and handoffs must be true and tested. Flag any drift or overclaim — especially any security control described as active that has no code.
6. **UI / accessibility, desktop lifecycle, release integrity.** Score-matrix heatmap (color-alone?), Casual vs Expert parity of certainty, sidecar orphan/lifecycle on every shipped OS, checksum/signature honesty, and honest unsigned labeling.

**Produce:**
- **Executive verdict** (≤200 words): the single strongest argument against the product as shipped, and whether the deterministic-first, AI-cites-only design actually holds.
- **Findings table**, most-severe first: *Severity (Critical/High/Med/Low) · Dimension · Claim · Concrete failure case (`file:line`) · Recommendation · Confidence.*
- **Top 5 risks**, each with a trigger and a mitigation.
- **≤5 blocking questions**, only if genuinely unresolved.
- A closing **"what would change my assessment"** paragraph.

**Rules:** label every material claim **Verified / Inference / Assumption**; do **not** invent coverage, licenses, accuracy numbers, or costs — say so if unsure; cite repo files by path and data claims by source; be concrete. An empty findings list for a dimension is a valid, honest result. This is a review — identify what is wrong, risky, unsupported, or missing; do not rewrite the code or the plan.
