# Codex review prompt — Golavo (2026-07-10)

Paste everything below the line into Codex (or another reviewing agent with repo access). It is self-contained.

---

You are acting as a **principal engineer, football data scientist, open-data licensing reviewer, and adversarial product critic**. Your job is to **review and try to break** an existing open-source project — not to praise it, and not to rewrite it. Be skeptical, specific, and evidence-based. Prefer "here is the concrete failure case" over general advice.

## The subject

**Golavo** — a local-first, open-source soccer match-intelligence app. A deterministic statistical engine owns every probability; optional local or BYOK cloud AI provides cited narrative only and never changes a number. Every forecast is *sealed before kickoff* (model + feature version + source hashes) and *scored after full time* into a public calibration record. It is explicitly **not** a betting product.

- **Code:** https://github.com/udhawan97/Golavo (public). License: **Apache-2.0** throughout.
- **Docs/site:** https://udhawan97.github.io/Golavo/
- **Status:** pre-alpha, **Phase 0 (data-feasibility spike)**. The repo today is a *scaffold + plan*: README, full docs site (methodology, coverage, AI contract, privacy, legal), CI/CD (CI + signed release + Pages), issue/PR templates, animated brand, and package skeletons — `core/` (Python modeling lib), `server/` (FastAPI `/health`), `ui/` (React+Vite shell), plus `desktop/`, `packaging/`, `packs/`, and `docs/adr/0001-architecture.md`. **No forecast engine is implemented yet** — that is deliberate.

## What to inspect

1. Clone and read the repo (structure, README, `docs-site/src/content/docs/**`, `docs/adr/**`, `docs/research/free-open-data-sources.md`, CI workflows, package skeletons).
2. Read the data-source findings in the appendix below (verified against primary sources on 2026-07-10) and cross-check them.
3. Review the **plan and the scaffold as they stand**, then produce prioritized findings.

## Baseline decisions already made (challenge them, don't restate them)

- Architecture: Tauri 2 desktop shell + FastAPI/Python sidecar; React/TS UI; Parquet+DuckDB warehouse; SQLite settings + immutable hash-chained forecast ledger (ADR-0001, "Option A").
- Prediction: time-decayed **Dixon-Coles / bivariate Poisson** champion over an **Elo** + league-average baseline; negative-binomial corners; coherent goalscorer allocation; forward-only backtesting with a leakage audit; nothing ships unless it beats baselines on out-of-sample RPS + log loss.
- AI: engine owns probabilities; AI only cites/explains; confirmed AI facts become typed features and rerun the model; numeric-whitelist validation; local (Ollama/llama.cpp) + BYOK cloud; no chain-of-thought exposure.
- Data: three tiers (see appendix) with legal isolation enforced in CI (an ODbL-isolation guard already exists).
- Licensing: Apache-2.0 (chosen over AGPL to maximize adoption/portfolio value).

## Review dimensions — for each, find the strongest objection and a concrete failure case

1. **Data feasibility & licensing.** Is the three-tier model (open core / free-local / BYOK) legally sound and actually sufficient to ship a trustworthy Phase-0 forecast? Scrutinize the appendix: is DataHub's PDDL re-licensing of football-data.co.uk data safe to redistribute? Does the ODbL share-alike on the Kaggle European Soccer DB or OpenLigaDB contaminate anything if isolation slips? Where will data quality/freshness actually bite? What breaks the "sealed forecast" if the only current open source (DataHub PDDL) lags or changes format?
2. **Prediction science.** Is Dixon-Coles/bivariate-Poisson the right champion given the *available* open data (mostly results, sparse current corners, no open club xG)? Where is leakage most likely to sneak in? Is the calibration approach coherent across W/D/L + exact-score + counts? What claims (manager effects, form, "new-manager bounce") are unsupported and should stay off?
3. **Architecture.** Is Tauri 2 + PyInstaller sidecar worth its complexity for Phase 0, versus a source-mode web app or pure-Rust? Name the specific failure modes (sidecar lifecycle/orphans, Windows updater force-exit, signing-key loss) and whether the plan's mitigations are adequate. What is over-engineered for a pre-alpha?
4. **AI contract.** Can the "AI never changes a number" guarantee actually hold under the described validation? Find a way to make AI smuggle an unsupported number past the numeric whitelist, or to make prompt injection change a displayed probability. Is the typed-feature-rerun loop robust?
5. **Security & privacy.** Localhost sidecar token, key storage, pack signing, update manifest, prompt-injection surface. What is the most realistic local-attacker or malicious-pack scenario, and does the design stop it?
6. **Legal/brand.** Is the nominative-fair-use position on competition names and the "no likenesses/crests/trophies" stance actually safe? Any Apache-2.0 + data-license interaction problems (e.g., shipping ODbL data alongside Apache code)?
7. **Roadmap realism.** Is Phase 0 (one reproducible sealed forecast, backtested, every fact cited) achievable with the verified open data? Are the kill criteria real? What is the single most likely reason this project stalls?
8. **Scaffold correctness.** Review the actual repo files: CI workflows, the license-isolation guard script, package manifests, the docs for over-claims vs the verified coverage. Flag anything that would fail, mislead, or rot.

## Required output

- **Executive verdict** (≤200 words): the strongest single argument against building this as planned, and whether the Phase-0 scope is the right de-risking move.
- **Findings table**, most-severe first: *Severity (Critical/High/Med/Low) · Dimension · Claim · Concrete failure case · Recommendation · Confidence*.
- **Top 5 risks** with a trigger and a kill/mitigation for each.
- **≤5 blocking questions** only if genuinely unresolved.
- A final **"what would change my assessment"** paragraph.

## Rules

- Label every material claim **Verified** (you checked a primary source/file), **Inference**, or **Assumption**.
- Do **not** invent coverage, licenses, accuracy numbers, or costs. If you can't verify, say so.
- Cite repo files by path and data claims by source. Be concrete; avoid generic advice.
- This is a review. Do not rewrite the codebase or the plan; identify what is wrong, risky, unsupported, or missing.

## Appendix — verified free/open data sources (2026-07-10)

Three tiers (full detail in the repo at `docs/research/free-open-data-sources.md`):

**Tier A — OPEN (redistributable):** DataHub.io core league CSVs (**ODC-PDDL**, current 2025/26, incl. shots/**corners**/cards) · ISDB/OSF (**CC0**, 216k matches 2000–2018, results only) · footballcsv (**CC0**, results, stale ~2020/21) · Kaggle European Soccer DB (**ODbL**, lineups+events+corners, 2008–2016, isolate — share-alike) · DFL/Bassek 2025 (**CC-BY**, tracking+events, research-scale) · DBpedia (**CC-BY-SA**, reference) · plus the prior CC0/CC-BY backbone (openfootball, martj42, Wikidata, Wyscout). Context: weather (Meteostat/NOAA/ERA5/NASA POWER/DWD, CC-BY/CC0), venue geo (GeoNames CC-BY, OSM ODbL).

**Tier B — FREE, NOT redistributable (local personal fetch only):** football-data.co.uk (current results + corners/shots/cards) · Understat (current club **xG**, unofficial scrape) · FPL API (PL minutes/goals) · American Soccer Analysis (MLS/NWSL xG) · TheSportsDB · ClubElo · RSSSF (historical). Golavo may fetch these to a user's machine and show them locally, but must never redistribute/export them.

**Tier C — RESTRICTED (avoid):** FBref/Sports-Reference (rich but redistribution-prohibited, 10 req/min), Sofascore, FotMob (scraping forbidden), StatsBomb (excluded per its user agreement).

**Gap check (open + redistributable + current):** results ✅; corners/shots/cards ✅ (DataHub PDDL — new); club lineups ⚠️ (historical/free-local only); club **xG** ❌ (free-local or research-scale only); injuries ❌.
