# Golavo Expansion Plan — Free & Open Only

**Date:** 2026-07-12 · **Baseline:** `main @ 8e88230aff4fd40aa614661e02aac020e151a766` (verified: worktree = local main = origin/main, clean tree, v0.3.3)
**Status:** PLAN ONLY — nothing implemented. Produced after Loop 0 (repo reality check, 4 parallel evidence agents), Loop 1 (live re-verification of every candidate source/library, 6 parallel agents, all primary URLs fetched 2026-07-12), and a 6-round interview.
**Method labels:** [V] Verified (read the code / fetched the page) · [I] Inference · [A] Assumption · [S] Stale.

**Interview record (owner's decisions):**
1. First focus: **more live games**. 2. World Cup upgrade first, **including tournament simulation now**. 3. Heavy analytics as **optional downloadable packs**. 4. **Both** share-alike packs accepted (ODbL + CC BY-SA), isolated. 5. Stats: model report cards, team strength/form, season outlook, event & tracking analytics, **plus "insights mainstream apps don't have"** (write-in). 6. Research analytics **mixed into match pages**, not a separate lab (owner overrode recommendation; mitigations below). 7. New artifacts: **Post-Match Review**, **Conditions Snapshot**. 8. AI: explain disagreement, post-match writer, missing-evidence spotter, cited Q&A, **plus a quarantined words-only "AI opinion"** (owner chose the guardrailed variant over a true second prediction engine). 9. Attribution: **repo/docs only**, no in-app credits screen for now (owner overrode recommendation). 10. Complexity: **modular, few curated packs**.

---

## 1. Executive recommendation

### The clock fact that shapes everything
The 2026 World Cup final is **2026-07-19** (semis Jul 14/15, third place Jul 18). Golavo's index ends **2026-07-11** and contains **zero still-forecastable fixtures today** [V]. `openfootball/worldcup.json` (CC0, auto-updated multiple times per day, 100/104 matches scored, semifinals resolved to France–Spain and England–Argentina, exact kickoff times with UTC offsets) can give Golavo the last four matches of this World Cup [V]. This is the only week in four years where Golavo can seal genuine pre-match World Cup forecasts. Everything else is sequenced around not missing it.

### Now (this week — Phase W)
- **World Cup sourcepack** from `worldcup.json` pinned at commit `056c53e…` (or newer HEAD at build time): exact UTC kickoffs, venue/round context, placeholder rejection (`W101`/`L101`), martj42 cross-check that fails closed on any completed-result disagreement, **excluded from model training** (fixture/schedule truth only).
- **Exact seal windows**: seals stay open until true kickoff instead of closing at midnight UTC the day before.
- **Refresh completion (slices 3–6)**: a consent-first in-app refresh that actually reaches the runtime index — needed to pick up the final's participants after the semis. Fallback if it slips: a point release (v0.3.5) on Jul 16–17 with a re-pinned pack.
- **Tournament Outlook v1**: exact enumeration of the remaining 4-match bracket (deterministic, no randomness needed), with a pre-registered, disclosed knockout draw-resolution rule. Labeled simulation/research — never a seal.
- **Post-Match Review v1** (deterministic scorecard): can land during or just after the tournament; reviews are honest retrospectives, so they don't expire the way seals do.

### Next (Phases 0–3, July–September)
- **Phase 0 (thin, parallel, non-blocking): governance** — machine-readable source registry, THIRD_PARTY_NOTICES.md + LICENSES/ + CITATIONS.bib, Syft SBOM on releases, pip-audit/cargo-deny/npm-audit + npm license gate in CI, provenance validator extended to per-class license policy, first Hypothesis property tests.
- **Phase 2: club-season readiness** — venue/timezone truth (stadiums + GeoNames) to fix the local-time-mislabeled-as-UTC defect, 2026-27 fixtures when upstream publishes (decision gate on Football.TXT parsing), standings engine, optional ODbL OpenLigaDB pack (opt-in, isolated).
- **Phase 3: the stats the owner picked** — model report cards, team strength/form trends, season outlook, challenger harness (penaltyblog strictly dev-only), contract hardening (OpenAPI export + generated-type drift gate + Schemathesis).

### Later
Research packs folded into match pages (Wyscout events → pass networks/shot maps/xT; SkillCorner tracking summaries), pack manager UI, Fjelstul CC BY-SA archive, AI extensions (engine-score narration → post-match writer → missing-evidence spotter → quarantined opinion → cited Q&A last), Wikidata alias enrichment.

### Research-only
IDSSE (validation of spatial artifacts only; 2.63 GB for 7 matches is not a user feature), SoccerTrack v2 (host currently gated), VAEP (heavier than xT; dormant reference implementation).

### Reject (for now, with reasons)
DuckDB and TanStack Query (no measured problem; benchmark-gated re-entry), socceraction as a dependency (dormant; numpy<2 pin conflicts with Golavo's numpy 2.4.6 [V]), Meteostat weather (live license contradiction: /license says CC BY 4.0, FAQ says CC BY-NC 4.0 [V] — blocked until upstream clarifies in writing), martj42 women's results (still no license [V]), Open-Meteo hosted API (free tier non-commercial [V]), StatsBomb/ClubElo/football-data.org/FBref-Understat-etc. (terms verified incompatible [V]), all logo/badge/kit imagery (trademark/copyright, unaffected by data licenses).

### Where I challenged the owner (and the outcome)
1. **"AI gives its own take with likely scores, filling gaps"** → would have made AI a second prediction engine and legalized fabrication. Owner accepted the guardrailed alternative: AI narrates the engine's own score matrix, plus a **quarantined, off-by-default, zero-digits, never-persisted "AI reading" panel** that may lean in words only, citing evidence, with gaps named rather than filled.
2. **Tournament sim "now"** → accepted, but descoped to **exact enumeration of the remaining bracket** (deterministic, small, testable in days) rather than a rushed full 104-match simulator. The full simulator generalizes later on the same engine.
3. **Research analytics mixed into match pages** (owner overrode my separate-Lab recommendation) → honored with **mandatory mitigations**: per-match capability chips, era badges ("2017/18 research event feed"), visually distinct research sections, and "no lawful source for this match" empty states. Revisited in §10.
4. **No in-app credits page** (owner overrode) → legally workable **only because** every redistributed pack will carry its own license + attribution files and NOTICE/THIRD_PARTY_NOTICES ship in the repo and release assets. Flagged as a cheap Later item; becomes practically mandatory if ODbL/CC BY-SA packs ship in-app downloads (§6, §10).

---

## 2. Current-state evidence map

Everything below is [V] against `8e88230` unless labeled otherwise.

### 2.1 What exists and where (load-bearing symbols)

| Subsystem | Evidence |
|---|---|
| Model families (5, frozen) | `core/golavo_core/models/candidates.py:17-23` (`FAMILIES`); fits chronological + time-decayed, `assert_no_future_rows` in every `.fit()` (`:61,89,149`) |
| Council (2 voices + baseline, no blending) | `core/golavo_core/analysis.py:49-74,117-149`; UI `ui/src/views/ModelLab.tsx:73-105` |
| Score matrix coherence | `core/golavo_core/score_matrix.py` — checked on every artifact load (`artifacts.py:77-81`) and at seal time (`artifacts.py:372`) |
| Metrics | log loss (primary), Brier, RPS, ECE, Wilson reliability bins — `core/golavo_core/evaluation.py:89-141`; chronological folds incl. WC2026 (`:17-36,57-68`); club folds per league |
| Seals | content-addressed `fa_*` + audit.jsonl; integrity verified on every read (`core/golavo_core/artifacts.py:126-178`); scored/voided via immutable successors (`:471-554`) |
| Replay/preview vs seal separation | distinct type `MatchAnalysis`, `ma_*` evidence ids, never ledgered (`analysis.py:183`, `evidence.py:683-687`) |
| Facts engine isolation | AST-scan import ban + runtime no-write proof — `core/golavo_core/facts/invariant.py:28-110` |
| AI guardrails | numeric whitelist binding value+unit+citation (`core/golavo_core/ai/whitelist.py:174-212`), betting lexicon + secret patterns, 4-layer injection defense (`ai/sanitize.py`, `ai/prompts.py:118-131`), 16-case red team (`core/tests/test_phase5_redteam.py`), fail-closed envelopes (`server/golavo_server/ai_gateway.py:151-176,356-438`) |
| API surface | 18 routes in `server/golavo_server/main.py`; one write route (`POST /seal`), one network route (`GET /fixtures/check`) |
| UI | hash-router `ui/src/App.tsx:94-136`; GamesHome / MatchSearch / Match Cockpit (`MatchDetail.tsx`) / ForecastDetail / Leagues / Model Lab / Settings; Casual-vs-Expert = presentation depth only (`hooks.ts:116-135`) |
| Packaging | Tauri 2 shell spawns ~73 MB PyInstaller onefile sidecar; token via env; lazy heavy imports + background warm threads (`server/golavo_server/sidecar.py:158-180`, `main.py:23-26`) |
| CI | provenance CC0 allowlist, byte-identical index rebuild, license-isolation grep, pytest/vitest/Playwright+axe, sidecar smoke macOS+Windows (`.github/workflows/ci.yml`); release gated on version-spot check + signing (`release.yml`) |

### 2.2 Known-gap recheck (the eight the brief asked about)

1. **Exact kickoff — gap confirmed, worse than briefed.** martj42 rows: honest 00:00 UTC day proxy (`ingest/snapshot.py:137`) → **the seal window closes at midnight UTC *before* match day** (`seal.py:147-152`, tested `test_seal_api.py:140`), discarding the entire match-day window. openfootball club rows: venue-local `time` **stamped as UTC without conversion** (`ingest/openfootball.py:186-191`) — a mislabel, and the index schema (`ingest/match_index.py:32-50`) has **no timezone/precision column**.
2. **Refresh — half-built, confirmed.** Merge engine `server/golavo_server/refresh.py:39-102` and reader repoint `server/golavo_server/matches.py:73-85` are implemented **and tested but have zero non-test callers**. No refresh route exists; the only network route is the read-only `GET /api/v1/fixtures/check`. Readers already prefer `refresh_dir()` (`matches.py:30-57`, `seal.py:84-107`) — the writer side (trigger, download→pinned-pack builder, UI status, atomic swap) is absent. Stale copy: `ui/src/views/Leagues.tsx:26` claims internationals "refresh on demand" — false today.
3. **Cold cost — real, managed, untested.** ~25 s pandas/pyarrow import in the frozen sidecar + ~30-40 s onefile self-extract on first launch (`main.py:23-26`, `desktop/src-tauri/src/lib.rs:5-9`); mitigated by lazy imports + `_warm_search`/`_warm_calibration` threads (`sidecar.py:158-180`). No perf regression tests or budgets exist.
4. **Contracts — handwritten both sides.** TS mirror `ui/src/lib/contract.ts` (+ runtime guards in `api.ts`); JSON Schemas in `docs/contracts/` enforced in Python at runtime; **no OpenAPI export, no drift test**; `match_analysis.schema.json` is loaded by no code (docs-only).
5. **Manifests & license enforcement.** Manifests carry source_id/url/upstream_ref/retrieved_at/per-file sha256/license; hash-verified at **build, CI, and every runtime pack load** (`ingest/snapshot.py:25-34`). License allowlist is **build/CI-time only** (`scripts/validate_provenance.py:22` and `match_index.py:53`, both `{"CC0-1.0"}`); runtime displays but does not enforce license. `packs/core-cc0` and `packs/overlay-odbl` are **README-only placeholders** [V]. Isolation gate is a self-described "basic grep lint" (`docs-site/.../data/sources.md:21-23`).
6. **SBOM / notices — absent.** No THIRD_PARTY_NOTICES, no LICENSES/ dir, no SBOM, no pip-audit/cargo-deny/npm-audit anywhere in `.github/` [V]. Attribution today = `NOTICE` + per-forecast provenance chips (`ui/src/components/Provenance.tsx:31-57`) + docs-site sources page.
7. **Coverage.** 75,079 rows, 6 packs, all CC0 (`data/index/matches_index.meta.json`): men's internationals (seal-able, one pack) + EPL/La Liga/Bundesliga/Serie A/Ligue 1 through completed 2025-26 (search/backtest only, not seal-able — `seal.py:40-46`). No standings (deliberate — `Leagues.tsx:5-7`), no cups, no women's data, zero upcoming fixtures as of today.
8. **Analytics artifacts & AI schemas.** Evidence bundles (`docs/contracts/evidence_bundle.schema.json`) with typed `allowed_numbers`; facts notebook (`facts.schema.json`) with predictive/context/coincidence labels and suppression audit; no event/tracking artifacts of any kind.

### 2.3 Stale plans/documentation (do not treat as authority)

| Document | Verdict |
|---|---|
| `docs/handoff/architecture-rethink-plan.md` | **Stale** — header still says "PLAN ONLY — nothing implemented" but its Phase 0/1 shipped in v0.3.0–0.3.3; its §0–§2 "reality check" misdescribes current code (`/matches/{id}/analysis` exists; nav is Games/Leagues/Model Lab); §13.3 schema-version mechanics were implemented differently (`ANALYSIS_SCHEMA_VERSION` separate). Needs a SUPERSEDED banner. |
| `docs/handoff/phase10-ui-redesign-plan.md` | Stale header ("PLAN ONLY") contradicted by its own shipped-appendix. |
| ADR-0001 + `core/golavo_core/__init__.py:5` | "Parquet + **DuckDB** views" — DuckDB is not a dependency and never was; aspirational language. |
| `CHANGELOG.md:65-66` | Claims clippy runs in CI — it does not (`cargo check` only). |
| `ui/src/views/Leagues.tsx:26` | "Refreshes on demand" — refresh is not wired. |
| Other `codex-phase*.md`, audits, eval reports | Honest point-in-time records; fine as history. |

---

## 3. Final source matrix

Verified date for every row: **2026-07-12** (live fetches; primary license files/pages, not badges). Pin strategy default: **vendor bytes into a hash-manifested sourcepack pinned to an upstream commit/dump-date; never fetch at runtime except the consent-first refresh**.

### 3.1 Core (bundled, drives product surfaces)

**openfootball/worldcup.json** — maintainer: openfootball org (Gerald Bauer + "Yo Robot" auto-gen). Software: n/a (data repo). Data: **CC0-1.0** (full text; LICENSE.md blob byte-identical across all 8 family repos; README public-domain dedication). License URL: `https://github.com/openfootball/worldcup.json/blob/master/LICENSE.md`. Pin: commit (brief's `056c53e…` **is today's HEAD**, committed 2026-07-12T15:03Z). Fields: date, `time` with explicit UTC offset ("15:00 UTC-4"), round, knockout `num` (only knockouts have `num` — 0/72 group matches do), team1/team2, score {ft,ht,et,p}, goals arrays, group, city-level `ground`; separate `worldcup.stadiums.json` with stadium name/capacity/**coords/timezone**; squads/teams/groups files. Coverage: 1930–2026; 2026: 100/104 scored, semis resolved, final+3rd still `W101/L101` placeholders. Freshness: multiple auto-commits/day during tournament. Redistribution/commercial: unrestricted. Attribution: none required (we credit anyway). Share-alike: no. Hosted dep: none. Offline: perfect. Provenance risk: bot-generated, per-match key set varies, community-maintained. Reliability: high during tournament; historical files stable. Bundle impact: 2026 file ≈ 42 KB; full history ≈ low MB. **Classification: CORE (fixture/schedule truth; excluded from model training initially; cross-checked against martj42, fail-closed).**

**martj42/international_results** — already in use. Data: **CC0-1.0** (LICENSE verified; repo pushed 2026-07-11, active). Pin: commit (current pack `273c731…`). Coverage: men's full internationals 1872→present, date-only (00:00 proxy). **Classification: CORE (training/results truth — unchanged).**

**openfootball/football.json** — Data: **CC0-1.0**. Coverage: top-5 leagues, seasons through **2025-26 complete; no 2026-27 exists** [V]; idle since 2026-05-30 (yorobot regenerates from .txt repos). Parsing hazards [V]: `score` is sometimes a bare array (Golavo already treats non-`ft` shapes as incomplete — correct); naive local `time` without offset. **Classification: CORE (historical club results — unchanged), plus watch-item for 2026-27.**

**openfootball .txt family** (`europe`, `world`, `south-america`, `champions-league`, `internationals`, `clubs`) — all **CC0-1.0** (byte-identical LICENSE.md) [V]. Format: Football.TXT, not JSON. `europe` is where 2026-27 fixtures are landing first (fr/nl/pt already present; head 2026-07-08). `champions-league`: through 2025-26, active. `clubs`: names/aliases/founding/stadium/city — **stale ~18 months** (head 2025-01-03; provably outdated grounds) — aliases are the durable value. `internationals`: mirror of martj42; 2026 WC file is fixtures-only, frozen pre-tournament — **do not use for 2026 results**. **Classification: candidate CORE adapters (Phase 2 decision gate: only if a minimal Football.TXT fixture parser is justified); `clubs` = enrichment candidate with staleness surfaced; `internationals` = redundant, reject.**

**GeoNames** — Data: **CC BY 4.0** (readme.txt in the dump dir is authoritative). License URL: `https://download.geonames.org/export/dump/readme.txt`. Pin: dump files by date + sha256 (`cities15000.zip` 3.1 MB, `countryInfo.txt`, `timeZones.txt`; daily refreshed upstream). Attribution: "Data from GeoNames (geonames.org), CC BY 4.0". Commercial/redistribution: yes with attribution. No share-alike. Offline: bulk files, no service dependency (web-service credit limits don't apply to dumps). **Classification: CORE ENRICHMENT (city coords/country/timezone; second cleared license tier `CC-BY-4.0` with enforced attribution).**

**Wikidata** — structured data **CC0** (`https://www.wikidata.org/wiki/Wikidata:Licensing`); weekly dated JSON dumps (pin by dump date); WDQS only for building pinned extracts, never runtime. NOT CC0: prose, Commons media (per-file licenses) — excluded. Attribution: requested not required ("Data from Wikidata"). **Classification: CORE ENRICHMENT, Later (team aliases/multilingual names/stable ids; property-level provenance; no auto-merge of identities — human-adjudicated alias tables only).**

### 3.2 Isolated optional packs (share-alike; opt-in download; never joined to core or each other)

**OpenLigaDB** — Data: **ODbL v1.0** (stated on homepage + `https://www.openligadb.de/lizenz`, links canonical ODbL text; commercial explicitly allowed; attribution "Datenquelle: OpenLigaDB (www.openligadb.de)"; share-alike for derivative databases; Produced Works need only a source notice). API: free, **no auth**, Swagger at `https://api.openligadb.de/`, 22 GET endpoints; **`matchDateTimeUTC`** reliable (ignore null `timeZoneID`); `getlastchangedate` for cheap polling. Coverage: bl1/bl2/bl3 through 2026/27, DFB-Pokal, `wm26` (live, updated today), Frauen-Bundesliga, more. Operator: **one private individual** (Marcel Siegel), community-entered results, no SLA/status page, duplicate league shortcuts exist (`wm26` vs stale `wm2026*`) — pin canonical shortcuts + validate match counts. **Classification: ISOLATED OPTIONAL PACK (ODbL class): cross-check + Bundesliga detail. The pack we redistribute must itself be ODbL, carry the license URI + attribution, and never merge with CC0/CC BY or CC BY-SA stores.**

**Fjelstul worldcup** — Data+code: **CC BY-SA 4.0**, but the grant lives **only in README + DESCRIPTION — no LICENSE file, no CITATION file** [V]. **No v1.2.0 tag exists**; v1.2.0 is the DESCRIPTION version — **pin commit `f942c6b`** (last data commit, 2023-07-20). Coverage: 27 CSVs (matches, players, managers, referees, stadiums, events, awards, squads, standings…), **22 men's (1930–2022) + 8 women's (1991–2019)** tournaments; README's "9 women's" claim is inconsistent with the repo data [V]. **WorldCups.ai carries different terms (CC BY-NC-SA + subscriber 2026 data) — never substitute it.** Attribution block required (author, ©, license link, repo link, modification note). **Classification: ISOLATED OPTIONAL PACK (CC BY-SA class), Later — WC history/archive artifacts; snapshot README+DESCRIPTION alongside the data as license evidence.**

### 3.3 Research packs (historical only; per-match artifacts; loud era labels)

**Pappalardo/Wyscout events** — **CC BY 4.0 verified per-article** on figshare (collection wrapper shows null — the articles carry the license). ~86 MB compressed; 1,941 matches (2017/18 big-5 + WC2018 + Euro2016); citation: Pappalardo et al., Sci Data 6:236 (2019) + PlayeRank paper. koenvo processed mirror: faithful, kloppy-loadable, but **no LICENSE file of its own** and dormant — prefer building our pack from figshare primary; treat koenvo as tooling reference. **Classification: RESEARCH PACK #1 (pass networks, shot maps, possession chains, xT).**

**SkillCorner opendata** — **MIT** (plain LICENSE) [V]; contents today: **10 A-League 2024/25 matches** (brief was right; the "9 matches 2019/20" description circulating elsewhere is stale) — tracking 10 fps extrapolated, dynamic events, phases of play, season aggregates; documented limitations (~97% ID accuracy, smoothing advised, `is_detected` flag); active (last commit 2026-06-03). Credit SkillCorner (+ PySport as courtesy). ~160 MB repo. **Classification: RESEARCH PACK #2 (tracking summaries: width/depth/compactness, speeds, off-ball runs).**

**IDSSE** — **CC BY 4.0** on figshare, DFL-authorized; 7 Bundesliga/2.BL matches, DFL-schema XML, **2.63 GB**; attribution = name DFL + cite Sci Data 12:195 (2025); companion repo code has no license (don't reuse its code). **Classification: RESEARCH-ONLY (validation of spatial pipelines; not a user-facing pack initially — size/value ratio too poor).**

**SoccerTrack v2** — MIT code / CC BY 4.0 data on paper, but **primary Hugging Face host returns 401 (gated/private) today** [V]; size unpublished; single-researcher hosting. **Classification: RESEARCH-ONLY, blocked — recheck availability later.**

### 3.4 Software (runtime candidates)

| Library | License [V] | State [V] | Classification |
|---|---|---|---|
| RapidFuzz 3.14.5 | MIT | healthy; wheels cp312/313 macOS-arm64 ≈1.1 MB, win ≈1.5 MB; zero deps; bus factor 1 | **ADOPT (Phase W/2)** — search suggestions only; never identity/merge decisions |
| openapi-typescript 7.13.0 | MIT | core active-but-slowed; openapi-fetch/react-query **officially frozen** (discussion #2559) | **ADOPT dev-only (Phase 3)** — generator only, as a CI drift gate; handwritten guards stay authoritative |
| Schemathesis 4.22.4 | MIT | very healthy; OpenAPI 3.1 + ASGI/FastAPI direct | **ADOPT test-only (Phase 3)** |
| Hypothesis 6.156.6 | MPL-2.0 | very healthy; `[numpy,pandas]` extras; now ships platform wheels (Rust ext) | **ADOPT test-only (Phase 0)** |
| kloppy 3.19.0 | BSD-3-Clause | healthy (PySport); Wyscout v2/v3 + SkillCorner + Sportec deserializers | **ADOPT pack-build-time (Phase 4)** — used by pack builders, not the runtime sidecar |
| penaltyblog 1.11.0 | MIT | active but fragile: solo maintainer, mandatory scraper/betting deps, **`socks` placeholder-package red flag on PyPI** [V] | **DEV-ONLY, isolated venv, never in any pyproject** — parity checks/challengers; scrapers/implied/betting/fpl modules forbidden |
| floodlight 1.2.0 | MIT | aging (tiny team, py `<3.14` cap, numpy ^2.1 OK) | **EVALUATE at Phase 4 start** — else compute the 4 simple metrics ourselves |
| socceraction 1.5.3 | MIT | **dormant** (last release 2024-08; numpy<2, py<3.13 — cannot co-install with numpy 2.4.6) | **REJECT as dependency; reference for reimplementing xT** |
| DuckDB 1.5.4 | MIT | healthy; wheel ≈15.5 MB (sidecar +~21%) | **REJECT for now; benchmark-gated re-entry** (§10) |
| TanStack Query 5.101.2 | MIT | healthy | **REJECT for now** — existing `getJson` cache already coalesces duplicates [V]; adopt only if measured problems appear |

### 3.5 Supply-chain tooling (CI/release only)

Syft v1.46.0 (Apache-2.0; one `syft dir:.` → SPDX+CycloneDX covering pip/npm/cargo), pip-audit v2.10.1 (Apache-2.0), cargo-deny 0.20.2 (MIT OR Apache-2.0; licenses/bans/advisories/sources), `npm audit --omit=dev` + `license-checker-rseidelsohn` 5.0.1 (BSD-3-Clause, maintained fork, `--onlyAllow` gate). All verified active within the last 5 weeks. **Classification: ADOPT (Phase 0).** One coherent release gate; no redundant scanners.

### 3.6 Excluded (re-verified 2026-07-12; recheck triggers noted)

- **martj42/womens-international-results** — still **no LICENSE** (API `license: null`, no file) [V]. Recheck monthly; adopt only on explicit open license.
- **Meteostat** — MIT code healthy; data **contradiction live**: `/license` = CC BY 4.0, `/faq` = "CC BY-NC 4.0" [V]; new keyless bulk Parquet (beta) exists; **no historical-forecast archive** → weather could only ever be context, and only after written license clarification. Blocked.
- **Open-Meteo** — AGPL source, CC BY data, **hosted free tier non-commercial** (`/en/terms`) [V]. Only ever as a user-supplied optional adapter with disclosed terms; not planned.
- **StatsBomb open-data** — user agreement forbids redistribution + commercial use, revocable, logo-attribution duty [V]. Excluded.
- **ClubElo** — publishes **no license or terms at all** (site is HTTP-only) [V]. Excluded.
- **football-data.org** — proprietary API service; post-cancellation data restriction [V]. Excluded.
- FBref/Understat/Sofascore/FotMob/Transfermarkt/unofficial FPL/scraper mirrors/DataHub mirrors — excluded (scraping/license-laundering).
- Club badges/competition logos/kit/trophy/player imagery — excluded (trademark/publicity/copyright are not licensed by any data grant).

---

## 4. Statistics & artifact plan

Global rules (apply to every row): every number carries a typed id + source ids; "Unknown / not available from a lawful source" is a first-class rendered state; **model-implied goals are never labeled xG**; research shot-quality estimates are labeled "research xT/shot value (2017/18 event data)", never "observed xG"; nothing becomes a model input without a pre-registered leakage-safe experiment beating a baseline on chronological held-out data.

### 4.1 Prediction evaluation (extends what exists)

| Item | Definition | Baseline / validation | Label / forbidden claims | AI may explain? |
|---|---|---|---|---|
| Log loss, Brier, RPS, ECE, reliability | already implemented (`evaluation.py:89-141`) | vs climatological baseline per fold | already honest | Yes (whitelisted) |
| **Skill score** (new) | `1 − LL_model / LL_climatology` per competition+fold; needs ≥50 test matches per cell else "insufficient sample" | climatology; report CIs via bootstrap over matches (seeded) | "relative to a team-blind baseline"; forbid "accuracy %" framing | Yes |
| **Model report card** (new) | per family × competition: folds, n, log loss, skill, ECE, rank stability | pre-registered: primary metric = log loss (already fixed) | must show n and fold dates; forbid cross-league strength comparisons (`evaluation.py:343` already warns) | Yes |
| **Disagreement index** (new) | existing `max_delta_p` + modal-agreement flag, tracked over the ledger as a time series | descriptive only | "models disagree" is a fact, not a signal; forbid "disagreement = value" | Yes |

### 4.2 Team strength & form (no new data needed)

Rolling attack/defence/Elo trajectories: re-fit at month-end cutoffs using only rows ≤ cutoff (the fit function already enforces this); render as trend lines with shaded uncertainty from fit weights; min 8 matches in window else "insufficient sample". Leakage risk: none if cutoffs honored (property test: recompute at T must be byte-identical when future rows are appended). Label: "model-estimated strength, this competition only". Forbidden: cross-league comparisons; "form" implying player availability knowledge. AI: yes.

### 4.3 Tournament Outlook (Phase W) — precise spec

- **Inputs**: remaining bracket from the worldcup pack (semis resolved; final/3rd from `W101/L101` → recompute when resolved); per-match joint score matrices from the two council voices fit at `cutoff = now`, trained on martj42 only (worldcup pack is not training data).
- **Method**: **exact enumeration** over the ≤4 remaining matches (2^2 semi outcomes × … — enumerable analytically from matrices; no RNG). Per team: P(reach final), P(champion), P(third). Rendered per voice (Elo view vs Dixon-Coles view) + baseline — **no blended single number**, consistent with council philosophy.
- **Knockout draw-resolution rule (pre-registered, disclosed)**: P(A advances) = P(A wins in 90') + P(draw at 90') × P(A wins beyond 90'), where P(A wins beyond 90') = A's share of non-draw probability in a rescaled ET matrix (same λs × 1/3, same machinery), and 50/50 on penalties after an ET draw. Deterministic, documented on the artifact, versioned (`outlook_rule: "ko-2026.07.1"`).
- **Sample-size / availability**: needs only fitted models + fixtures. Missing fixture (unresolved placeholder) → that branch renders "awaiting semifinal results", never a guess.
- **Uncertainty**: probabilities are model outputs; artifact carries both voices' numbers so the spread IS the uncertainty display.
- **Baseline**: climatological bracket (all matches 33/33/33 → equal advance shares) shown as reference.
- **Validation**: unit tests — enumeration sums to 1 across champions; degenerate matrices (P(win)=1) propagate exactly; rule version stamped. Backtest gate before the sim is ever called "evaluated": after the tournament, score the outlook's champion distribution against reality via log loss vs the climatological bracket (one data point — labeled as such).
- **Label**: "Tournament outlook — a simulation from current model fits. Not a sealed forecast. Individual matches can still be sealed."
- **Forbidden**: entering the ledger; being scored as if sealed (unless a separate `outlook` artifact class with its own honest track record is added later); any "chance to win" framing without the rule version + voices shown. AI: may narrate numbers verbatim.

### 4.4 Season Outlook (Phase 3; blocked on 2026-27 fixtures + standings)

Standings engine first (points/GD/tiebreaks per competition — competition-specific tiebreak rules are data, must be encoded per league and tested against a completed season [V]-able from packs). Then: seeded Monte Carlo (fixed seed in artifact; 10k iterations; largest-remainder rounding for display) over remaining fixtures using council voices → P(title/top-4/relegation) per voice. Gates: standings reproduce 2024-25 final tables byte-exact for all 5 leagues before any simulation ships; sim is labeled like the tournament outlook. Missing fixtures upstream → the league renders "2026-27 fixtures not yet published by our lawful source" (first-class Unknown).

**Implementation evidence (2026-07-15):** the pinned La Liga and Serie A 2024-25
captures each contain only 370 completed matches, so the originally written
five-league 2024-25 gate cannot be satisfied without inventing ten results per
competition. The implemented gate therefore uses 2023-24, the latest season that
is structurally complete across all five, and explicitly encodes disciplinary
points adjustments. The API retains the incomplete 2024-25 captures as typed
`past_result_gaps` states. The 10,000-run engine, rule-specific tie-breaks,
largest-remainder display rounding, and three separate voices are implemented;
the live 2026-27 surface remains blocked until its double-round-robin fixture
certificate passes.

### 4.5 Event analytics (Phase 4; research pack #1, per-match precomputed artifacts)

**Implementation evidence (2026-07-15):** Golavo now bundles a compact,
isolated CC-BY research pack covering all 1,941 matches and 3,251,294 events as
seven team-only competition-era summaries. The shipped surface deliberately
does not carry player identities, raw events, or pass networks. It exposes
progressive passing, shot rates, a disclosed same-team event-run proxy, and an
own 12×8 research-xT calculation behind collapsed league-page disclosure. Every
panel names its historical era and states that it never enters forecasts or
simulations. The larger per-match/player research design below remains future
work, not a claim about v0.13.0.

For each covered match (1,941): **pass networks** (nodes = starters, edges = completed passes ≥3, positions = median touch location), **shot maps** (Wyscout tags; no xG claim — shot locations/outcomes only, optional "research shot-value" if we ship our own grid-xT), **possession chains** (chain = uninterrupted team possession; progression = Δ distance-to-goal), **xT** (own reimplementation of the standard 12×8 grid transition model, trained on the pack itself, versioned; socceraction as reference only). Sample floors: pass network needs full-match event coverage (drop else); xT model trained once on 2017/18 corpus, frozen, documented. Chronological availability: historical only — **never blended into live match models**. Missing: any live match renders "No lawful event feed for this match." Labels: era badge "2017/18 Wyscout research data (CC BY 4.0, Pappalardo et al.)". AI: may summarize with whitelisted numbers.

### 4.6 Tracking analytics (Phase 4; research pack #2)

Width/depth/compactness (team bounding stats per phase), space control (Voronoi share at sampled frames), off-ball runs + speeds (SkillCorner's own aggregates re-surfaced), pressure proxies (SkillCorner dynamic events). Honor documented accuracy limits in-artifact ("~97% ID accuracy; extrapolated frames flagged"). 10 matches only → artifacts exist per covered match; nothing generalizes. AI: summarize only.

### 4.7 Conditions Snapshot (owner-picked artifact; Phase 2)

Fields: venue (stadiums file), city coords + altitude (GeoNames), kickoff local time + timezone (worldcup pack offset or GeoNames tz), **rest days** (days since each team's previous indexed match — computable today), **travel distance** (haversine between consecutive match cities for each team — internationals/tournaments where city data exists). No weather until Meteostat licensing clears; then context-only. Leakage: rest/travel are knowable pre-match (safe as displayed context); they do NOT enter models without the standard experiment gate. Missing any field → the row renders "unknown". Label: "Context, not a model input." AI: may cite.

### 4.8 "Not on mainstream apps" differentiators (owner write-in)

All cheap, all honest, all deterministic: calibration receipts on every forecast ("forecasts at ~60% have landed 5 of 9 times — small sample"); upset base rates ("teams this far behind in rating have won 18% of 1,203 historical matches"); what-moved deltas (exists); seal-vs-replay honesty labels (exists); provenance receipts (exists — surface louder); disagreement index; rest/travel context. These extend the facts registry (pre-registered templates, multiple-comparison bound — `facts/registry.py`) rather than inventing a new mechanism.

---

## 5. AI evidence contract (extension of the shipped one)

Unchanged foundations [V]: deterministic artifact first; evidence bundle with typed `allowed_numbers` (id, value, unit, display, source_ids); whitelist binds value+unit+citation; betting-lexicon + secret gates; injection defenses (strip/fence/system-rule/output-gate); fail-closed envelopes; AI output never written to any ledger; local AI free/keyless; BYOK optional; no probability mutation possible by construction (facts layer statically write-isolated; bundles are pure functions of sealed artifacts).

Additions, in guardrail order:

1. **Engine-score narration** ("AI take, honest version"): the bundle already carries the score matrix; add matrix top-k scorelines as typed numbers (`sm_*` ids). AI explains *why the engine* favors them (attack/defence rates, home adv — all whitelisted). No new mechanism, no new risk.
2. **Missing-evidence spotter**: bundle grows a typed `absences[]` section (no lineups; kickoff precision = day-proxy; n below floor; no event feed). AI may only name absences that exist in the bundle — a fabricated absence fails citation checks.
3. **Post-Match Review writer**: input = the deterministic review artifact (what each voice said, outcome, per-model log loss/Brier for this match, calibration context). Same whitelist. Review artifact is persisted; narration is not.
4. **Quarantined AI opinion** (owner-selected): separate envelope kind `opinion`; **hard rules**: (a) scanner runs in zero-digits mode — ANY digit token rejects (spelled-out numbers already rejected by the existing gate); (b) every claim must cite ≥1 evidence/fact id; (c) "gap-filling" is structurally impossible — claims referencing non-bundle facts are dropped, and named gaps come only from `absences[]`; (d) off by default, per-session opt-in; (e) banner: "AI speculation — not a Golavo forecast. Golavo's numbers are on the left."; (f) never persisted, never sealed/scored, excluded from exports; (g) betting lexicon + injection defenses unchanged.
5. **Cited Q&A** (last): retrieval strictly over evidence bundles + notebooks of the match(es) in view; answers restate typed numbers only; refuses beyond-evidence questions with the missing-evidence pattern. Ships only after 1–4 are stable.

**Red-team additions** (extend `test_phase5_redteam.py`): opinion smuggles digits/spelled numbers/scorelines → reject; opinion cites nonexistent id → drop claim; opinion invents injury/lineup "news" → citation gate drops; research-pack free text (player names from Wyscout tags) attempts injection → sanitize path + fence (already exists) + new fixture cases; Q&A prompt asks for probabilities AI "would assign" → refusal template; narration of outlook mixes voices into a blended number → whitelist has no blended id, rejects. **Fail-closed**: any gate failure → `local_only`/omission, never a degraded answer.

---

## 6. Attribution & contributor-credit architecture (owner chose repo/docs; no in-app screen now)

1. **Machine-readable source registry** — `data/sources/registry.json` (new, schema-validated): one entry per source: `source_id`, name, contributors (derived only from LICENSE/CITATION/repo metadata/paper author lists — never invented), repo/homepage URL, SPDX or data-license id, exact license URL, citation key, pin (commit/dump-date), retrieval time, files+sha256, modifications, required attribution text, **classification** (`core | enrichment | odbl-pack | by-sa-pack | research-pack | dev-only | benchmark-only | rejected`), recheck-by date for rejected/blocked entries (womens-results, Meteostat).
2. **THIRD_PARTY_NOTICES.md** — generated by a script from the registry (data) + Syft output (code deps); committed; regenerated in CI and diff-checked.
3. **LICENSES/** — full texts: CC0-1.0, CC-BY-4.0, ODbL-1.0, CC-BY-SA-4.0, MIT, Apache-2.0, BSD-3-Clause, MPL-2.0 (as adopted).
4. **CITATIONS.bib** — Pappalardo 2019, PlayeRank, Bassek 2025 (IDSSE), Fjelstul 2023, Dixon & Coles 1997 (already cited in docs), SkillCorner/PySport credit note.
5. **Manifest v2** — packs gain `attribution`, `license_url`, `citation_key`, `license_class`; validator requires them for non-CC0 classes.
6. **Pack-carried notices** — every redistributable pack ships its license text + attribution file **inside the pack** (this is what makes the no-in-app-screen choice legally workable for CC BY/ODbL/CC BY-SA).
7. **Docs-site** — `data/sources.md` regenerated from the registry; methodology pages gain citations.
8. **Release SBOM** — `syft dir:. -o spdx-json -o cyclonedx-json` attached to every release next to SHA256SUMS.
9. **CI gate** — fails if: a pack's `source_id` is missing from the registry; classification/license/attribution/hash/citation fields absent for its class; THIRD_PARTY_NOTICES is stale; a Python/Node/Rust dep falls outside the license allowlist (pip-audit/cargo-deny/license-checker-rseidelsohn) or has known critical advisories.
10. **In-app**: existing provenance chips stay; a Settings "Open Data & Contributors" screen is a **Later** item generated from the registry (revisit trigger: the first in-app pack download shipping — see §10).

---

## 7. License-isolation architecture

**Classes and stores:**

| Class | Licenses | Store | Join policy |
|---|---|---|---|
| `core` | CC0-1.0 | bundled `data/index/` (+ refresh dir) | joins freely within class |
| `enrichment` | CC-BY-4.0 (GeoNames; later Wikidata CC0 folds into core) | bundled side tables, attribution enforced | may join core **read-only** for display/context; enrichment never silently creates identity merges |
| `odbl-pack` | ODbL-1.0 (OpenLigaDB) | separate parquet store under user-data `packs/odbl/…` | never joined into core/BY-SA; cross-checks compare and report, they don't merge rows |
| `by-sa-pack` | CC-BY-SA-4.0 (Fjelstul) | separate store | never joined into core/ODbL |
| `research-pack` | CC-BY-4.0 (Wyscout, SkillCorner…) | per-match artifact files, precomputed at pack build | outputs are artifacts keyed to match ids; raw tables never join the index |
| `dev-only` | any OSI (penaltyblog, Schemathesis…) | dev venv/CI only | never in runtime pyproject or sidecar |
| `rejected` | — | registry entry only | CI greps forbid imports/URLs |

**Enforcement:**
- Build-time: `validate_provenance.py` becomes class-aware (per-class allowed licenses + required fields) instead of the single CC0 set.
- Index-build: `match_index.py`'s `_CLEARED_LICENSES` stays CC0-only for match rows; enrichment tables get their own cleared set + required-attribution check.
- **Runtime (new, closes the "grep lint" gap):** pack loader stamps every loaded frame with `license_class` metadata; a join guard in the loading API raises on any cross-class join attempt; seal/export paths write `license_class` into provenance. Cheap assertions, tested.
- CI: `check_license_isolation.sh` extended per class (odbl/by-sa dir greps; core import bans; meta license list check); plus a test that builds a toy ODbL pack and proves the index build refuses it.
- Exports: any export containing ODbL/BY-SA-derived **data** carries the license + attribution block; Produced Works (rendered forecasts/screens) carry a source notice (ODbL §4.3 satisfied).

---

## 8. Phased roadmap

Effort scale: S ≤ 1 day · M = 2–4 days · L = 1–2 weeks (solo maintainer + Claude).

### Phase W — World Cup fast-track (NOW; hard deadlines Jul 14/15 semis, Jul 19 final)

**User value:** Golavo has real matches to forecast again this week; seals with correct pre-kickoff windows; a champion-odds outlook; honest post-match scorecards.

**W1a — pack + exact kickoff + seal window (M, critical path, target: before Jul 14 15:00 EDT builds; must-land Jul 17 for the final):**
- New `scripts/build_worldcup_pack.py`: pin worldcup.json commit; parse `date` + `time "H:MM UTC±O"` → true `kickoff_utc`; capture round/`num`/city + stadium tz/coords from `worldcup.stadiums.json`; **reject `^[WL]\d+$` placeholder fixtures**; emit manifest v2 (`license_class: core`, CC0).
- Core ingest: new `source_id=openfootball-worldcup-json` loader; index schema adds `kickoff_precision ∈ {exact, day}` (+ meta bump); **fixture-overlay semantics**: worldcup pack contributes upcoming fixtures + kickoff/venue enrichment; **martj42 remains sole training source** (`training_eligible=false` on worldcup rows / overlay applied post-training-selection — mechanism chosen at implementation, invariant tested either way).
- **Cross-check gate (fail-closed):** for every (date, normalized home/away, tournament=World Cup) pair completed in both sources, full-time-equivalent scores must agree or the build/refresh aborts listing offenders. Implementation note: verify martj42's score convention (it records the post-extra-time score; worldcup.json splits ft/et/p) with fixtures from this tournament before trusting the comparator — acceptance test required.
- Seal path: `resolve_pack_dir` maps the new source to its pinned pack; eligibility uses true kickoff when `kickoff_precision=exact` (existing `kickoff-1s` cutoffs and `as_of < kickoff` gates all keep working — they just stop being midnight-crippled).
- Affected files: `scripts/build_worldcup_pack.py` (new), `core/golavo_core/ingest/{worldcup.py (new), match_index.py, snapshot.py}`, `server/golavo_server/{seal.py, matches.py}`, `data/index/*` (rebuilt), `packs/openfootball-worldcup/` (new), CI index-rebuild step, `NOTICE`.
- Tests: parser fixtures (offsets, placeholders, et/p scores, missing keys); cross-check agree/disagree; seal window at exact kickoff (freeze-time tests); index rebuild byte-identical; no-training-leak invariant (worldcup rows never in `training_rows` output).
- Rollback: revert index + pack dirs; schema change is additive (old readers ignore the column, `ACCEPTED_SCHEMA_VERSIONS` untouched).
- Allowed claims: "exact kickoff from a public-domain source; seal window open until kickoff." Forbidden: "live scores", "official FIFA data", any lineup claims.

**W1b — refresh slices 3–6 (M, target Jul 15–17; fallback = point release):**
- `POST /api/v1/refresh` (consent-first; UI button in Settings + a "new fixtures available" banner action): download pinned upstreams (martj42 + worldcup.json raw at recorded refs) → build pack in `refreshed_pack_dir()` (net-new in-server builder — `build_sourcepack.py` isn't in the wheel [V]) → `merge_refreshed_index` → `repoint_to_refreshed` (both already exist and are tested [V]) → UI staleness/status chip. Network egress stays: exactly two pinned GitHub raw URLs + explicit user action.
- Fix `Leagues.tsx:26` copy either way.
- Tests: end-to-end refresh against recorded fixtures (no live network in CI); collision/failure paths render errors, never partial swaps (atomic via existing repoint design).
- Rollback: refresh dir is user-writable and deletable; readers fall back to bundled index [V existing behavior].

**W2 — Tournament Outlook v1 (M, detachable — ships only if gates pass by Jul 17):**
- `core/golavo_core/outlook.py` (new): exact enumeration + KO rule `ko-2026.07.1` (spec §4.3); route `GET /api/v1/tournaments/worldcup-2026/outlook`; UI panel on Games home + league page. Per-voice numbers, baseline reference, simulation label.
- Tests: probability conservation; degenerate propagation; placeholder branch renders "awaiting semifinals"; determinism (byte-identical across runs).

**W3 — Post-Match Review v1 (S/M, can land right after the final):**
- Deterministic review artifact (`pr_*`): per completed match with ≥1 seal or on-demand replay — what each voice said, outcome, per-voice log loss/Brier, calibration context, honest "replay, not a forecast" label when no seal existed. Persisted beside notebooks. UI section on Match Cockpit.

**Phase W gates:** license/provenance loop (new pack passes class-aware validator); deterministic fixture tests; no-leak invariant incl. new source; bundle budget (+<3 MB for the pack; sidecar size unchanged); installed-app QA on macOS **and** Windows (seal a semi, refresh, see the final appear after Jul 15); CI green from clean checkout. **Pros:** once-in-4-years product moment; fixes the two worst honesty gaps (dead seal window, unwired refresh). **Cons:** deadline pressure; mitigated by W1a-first sequencing and W2 detachability.

### Phase 0 — Governance (parallel with W; S+M total; must not block W)
Scope: §6 items 1–9 + Hypothesis first targets (whitelist scanner fuzz, canonical-bytes/rounding, coherence tolerances, `training_rows` cutoff property) + SUPERSEDED banners on the two stale plan docs + CHANGELOG clippy-line fix + ADR DuckDB-language fix. Audits start non-blocking (warn) → blocking after one clean week. Rollback: none needed (additive).

### Phase 2 — Club-season readiness (L; late July–August)
- Venue/timezone truth: stadium tables (worldcup.stadiums.json now; openfootball `clubs` stadium names flagged historical; GeoNames coords/tz) → **fix `openfootball.py:186-191`**: convert venue-local time + venue tz → true UTC; `kickoff_precision` honest per row; backfill index.
- 2026-27 fixtures: **decision gate Aug 1** — if yorobot hasn't regenerated football.json 2026-27, implement a minimal Football.TXT *fixtures* parser against `openfootball/europe` (scope: fixtures only, top-5, golden-file tests); else just re-pin football.json.
- Standings engine + per-league tiebreak rules, validated against 2023-24, the latest season complete across all five pinned league captures; later seasons remain explicit gap states.
- Optional **OpenLigaDB ODbL pack** (opt-in download; §7 isolation; cross-check surface: "our source vs OpenLigaDB" comparison chip, no row merging). RapidFuzz "did you mean" in search (navigation only).
- Conditions Snapshot v1 (rest days, travel distance, venue/altitude/local kickoff).
- Gates: canonical-team fragmentation checks extended; standings gate above; ODbL store proven un-joinable by test; installed-app QA.

### Phase 3 — Stats & trust the owner picked (L; September)
Model report cards + skill scores; strength/form trend pages; season outlook (once fixtures exist); challenger harness (pre-registered protocol doc + penaltyblog dev-venv parity checks: our Poisson/DC/RPS vs theirs on identical inputs; any adopted challenger must beat the frozen five on chronological held-out log loss and stay interpretable); contract hardening (export `openapi.json` in CI, `openapi-typescript` generated types drift-gate, Schemathesis fuzz suite: malformed ids, pagination extremes, invalid provider config, 500-shape, schema drift).

### Phase 4 — Research packs in match pages (L–XL; October+)
Pack manager (Settings section: download/verify(sha256)/remove; size shown; registry-driven); Wyscout pack build (kloppy at build time → per-match artifact JSONs; xT reimplementation trained+frozen on the corpus); SkillCorner pack; Match Cockpit research sections with capability chips + era badges + distinct styling; search filter "has research data". Fjelstul BY-SA archive pack (WC history pages) after. floodlight evaluated at start (else own metrics). Gates: per-artifact schema + AI-fold whitelist compliance; bundle budget unchanged (packs are downloads); a11y (axe) on new sections.

### Phase 5 — AI extensions (M–L; rolling after Phase 4 starts)
§5 order: engine-score narration → missing-evidence spotter → post-match writer → quarantined opinion → cited Q&A. Each lands with its red-team cases; opinion panel additionally behind a settings toggle default-off.

### Performance track (benchmark-gated, any time)
Build the benchmark harness first (cold start, first search, warm search, RSS, binary size — source mode AND frozen, macOS+Windows). Only if pandas/pyarrow first-search p50 in the frozen app exceeds ~3 s warm-thread-adjusted, prototype DuckDB behind the same interface and compare; pandas stays for modeling regardless. TanStack Query only on measured duplicate-fetch/stale-UI defects.

---

## 9. Loop acceptance gates (no feature advances unless)

1. **License/provenance loop**: registry entry complete; class-aware validator green; pack carries license text + attribution; hashes verified; NOTICE/THIRD_PARTY_NOTICES regenerated.
2. **Deterministic fixture tests** green (parser goldens, byte-identical index rebuild, artifact canonicalization).
3. **Statistical gate**: any model-facing change beats its pre-registered baseline on chronological held-out data, or is rejected and recorded (challenge report either way).
4. **Leakage loop**: `assert_no_future_rows` + new-source training-exclusion tests + replay-poisoning tests green; any new feature knowable-before-kickoff argued in the artifact spec and tested.
5. **Budgets**: bundled app delta < 5 MB per phase unless explicitly approved; cold-start p50 not regressed >10% (harness from the performance track, once it exists — until then, manual timing note in the PR).
6. **AI red-team**: full suite incl. new cases green; fail-closed verified.
7. **Attribution/SBOM completeness**: CI gate §6.9 green.
8. **Clean checkout + full CI** green on macOS+Windows runners.
9. **Installed-app QA**: real macOS + Windows builds exercised for every user-visible change (checklist per phase; seal→refresh→outlook flow for Phase W).

---

## 10. Adversarial rebuttal (arguing against my own plan) and revisions

1. **"The WC fast-track is a deadline-driven rush onto your most sacred surface (seals)."** Strongest objection. Mitigations already in the plan: W1a touches ingestion/eligibility, not artifact mechanics; the seal gates (`as_of < kickoff`, integrity, coherence) are untouched and already tested; W2/W3 are detachable; the fallback for the final is a boring point release. **Revision: none — but explicit rule added: if W1a's cross-check or leak tests are not green by Jul 17, ship nothing and let the window close.** Honesty outranks the demo.
2. **"Tournament sim now adds little — 4 matches."** True on volume; but exact enumeration makes it small, deterministic, and reusable, and the owner explicitly chose it. **Revision: W2 is last in the W queue and cuttable without notice.**
3. **"Mixing research analytics into match pages will mislead"** (I recommended a separate Lab; owner overrode). Residual risk: a 2017/18 pass network beside a live forecast reads as current. **Revisions: (a) research sections are collapsed by default with the era badge on the collapsed header; (b) the section header names the season of the data, not just the source; (c) revisit after the first pack ships — if confusion appears, the separate-Lab option returns to the table.**
4. **"No in-app credits page while shipping ODbL/BY-SA packs is legally thin."** Pack-carried notices + repo/docs satisfy the letter (ODbL Produced-Works notice included in exports). **Revision: hard trigger added — the release that ships the first in-app pack download must include the registry-generated credits screen (it's an S-size task by then). Owner's 'repo/docs only' stands until that trigger.**
5. **"Fjelstul is a weak pack: README-only grant, frozen 2023, women's data ends 2019."** Agreed. **Revision: demoted below SkillCorner/Wyscout in Phase 4 ordering; ships only with the license-evidence snapshot; its women's coverage must be labeled '1991–2019 only'.**
6. **"IDSSE 2.63 GB for 7 matches is a vanity integration."** Agreed. **Revision: research-only (pipeline validation), no user-facing pack. Already reflected in §3.3.**
7. **"OpenLigaDB is a single-person hobby service — you're adding a dependency on one stranger's IIS box."** It's opt-in, isolated, cross-check-only, and cache-everything; core never depends on it. **Revision: pack builder must tolerate total OpenLigaDB absence forever (feature renders 'source unreachable').**
8. **"penaltyblog in any form invites the scraper/odds stack and a junk `socks` dep into the project."** **Revision: it never enters any pyproject or lockfile — a documented `dev-tools/challenger-venv/requirements.txt` with hash pins, CI-optional, plus a standing rule in CONTRIBUTING that its scrapers/implied/betting/fpl modules are forbidden imports.**
9. **"openapi-typescript is slowing; you may be adopting a decaying tool."** It's dev-only CI tooling with handwritten guards remaining authoritative; worst case we delete one CI step. Accepted.
10. **"Wikidata/clubs enrichment duplicates identity machinery you already own."** Largely true today. **Revision: Wikidata moved to Later-if-needed (concrete trigger: cross-source alias collisions during Phase 2/4 that the existing alias tables can't adjudicate). openfootball `clubs` used only as an alias source, stadiums ignored (stale).**
11. **"Five stats areas + packs + AI extensions is too much for one maintainer."** The phase gates are the throttle; nothing after Phase W has a deadline. **Revision: explicit WIP rule — at most one phase in flight after W.**

---

## 11. Final implementation plan

### Must (authorization unlocks immediately)
- **W1a** WC pack + exact kickoff + seal window + cross-check (critical path; target Jul 13–14, hard stop Jul 17)
- **W1b** refresh slices 3–6 (target Jul 15–17; fallback point-release recipe pre-written)
- **Phase 0** governance (parallel, non-blocking)

### Should (next, in order)
- **W2** Tournament Outlook v1 (cuttable) · **W3** Post-Match Review v1
- **Phase 2** venue/tz fix → 2026-27 fixtures (Aug 1 decision gate) → standings → Conditions v1 → RapidFuzz suggestions → OpenLigaDB ODbL pack
- **Phase 3** report cards → strength trends → season outlook → challenger harness → contract hardening (OpenAPI drift gate + Schemathesis)

### Later
- **Phase 4** pack manager → Wyscout pack (networks/shots/chains/xT) → SkillCorner pack → Fjelstul archive → floodlight decision
- **Phase 5** AI ladder (narration → absence-spotter → review-writer → quarantined opinion → cited Q&A)
- In-app credits screen (hard trigger: first in-app pack download release) · Wikidata aliases (trigger: unresolvable collisions)

### Research-only
IDSSE (pipeline validation) · SoccerTrack v2 (blocked on host) · VAEP (after xT, if ever)

### Reject (standing, with re-entry conditions)
DuckDB & TanStack Query (re-entry: benchmark harness shows p50 miss) · socceraction dependency (re-entry: none; reference only) · Meteostat (re-entry: written license clarification) · Open-Meteo hosted (re-entry: terms change) · martj42 women's results (re-entry: license added) · StatsBomb/ClubElo/football-data.org/scrape-mirrors (re-entry: real license change) · badges/logos/kit imagery (re-entry: none foreseeable)

### Dependency graph & critical path
```
W1a ──► W1b ──► (final's fixtures resolve Jul 15) ──► seal final Jul 19
  │                                   
  ├──► W2 (outlook; needs W1a fixtures + models)     Phase 0 ──► (parallel, feeds CI gates for all)
  └──► W3 (review; needs results via W1b or release)
Phase 2 venue/tz ──► club exact kickoff ──► season outlook (also needs 2026-27 fixtures + standings)
Phase 3 contract hardening ◄── Phase 0 registry/SBOM
Phase 4 pack manager ◄── Phase 0 registry; research packs ◄── pack manager
Phase 5 each AI item ◄── its deterministic artifact
```
Critical path this week: **W1a → W1b → semis sealed Jul 14/15 → refresh after semis → final sealed Jul 19.**

### Non-overlapping file ownership (for parallel implementation)
- Lane A (pack/ingest): `scripts/build_worldcup_pack.py`, `core/golavo_core/ingest/*`, `packs/*`, `data/index/*`
- Lane B (server): `server/golavo_server/{refresh,matches,seal,main,fixtures}.py`
- Lane C (outlook/review engine): `core/golavo_core/{outlook,review}.py` (new files only)
- Lane D (UI): `ui/src/views/*`, `ui/src/components/*`, `ui/src/lib/{api,contract}.ts` (contract edits serialized — contract-first: schema/type diffs land before dependent UI)
- Lane E (governance): `data/sources/registry.json`, `NOTICE`, `THIRD_PARTY_NOTICES.md`, `LICENSES/`, `CITATIONS.bib`, `.github/workflows/*`, `scripts/{validate_provenance,gen_notices}.py`
- Rule: contract files (`docs/contracts/*`, `contract.ts`) change by exactly one lane per slice, first.

### Effort & risk
| Item | Effort | Risk | Dominant risk |
|---|---|---|---|
| W1a | M | Med | martj42/worldcup score-convention mismatch → cross-check design; deadline |
| W1b | M | Med | net-new in-server pack builder; atomicity |
| W2 | M | Low-Med | KO rule scrutiny; cuttable |
| W3 | S/M | Low | none |
| Phase 0 | M | Low | audit noise at first |
| Phase 2 | L | Med | tz backfill correctness; upstream 2026-27 timing |
| Phase 3 | L | Med | challenger-protocol discipline |
| Phase 4 | L–XL | Med | pack-manager surface; misread-as-live risk (§10.3) |
| Phase 5 | M–L | Med | opinion-panel guardrails |

### Exact acceptance criteria (Phase W; later phases carry §8/§9 gates)
1. From a clean checkout: build worldcup pack at a pinned commit; `pytest`, index byte-identical rebuild, provenance validator all green.
2. Installed macOS + Windows apps show the two semifinals as upcoming with **exact local+UTC kickoff**, seal-eligible until kickoff minute; sealing produces a `fa_*` artifact whose provenance names the worldcup pack, commit, hashes, CC0.
3. Placeholder final is **absent** until semis resolve; after in-app refresh (or fallback release), the resolved final appears and is sealable; refresh failure leaves the app on the previous index with an honest error.
4. Cross-check demo test: a doctored disagreeing result aborts the build/refresh with a message naming the fixture.
5. Training-exclusion test: model fits are byte-identical with and without the worldcup pack present.
6. Outlook (if shipped): per-voice champion probabilities sum to 1, rule version displayed, labeled simulation, absent from ledger/calibration.
7. No AI change in this phase beyond narration of new typed numbers; red-team suite green.
8. NOTICE + registry updated for the new pack; CI green; version bumped via the 14-spot script; CHANGELOG entry.

---

*Interview answers, loop reports, and all verification evidence (with URLs and dates) are embedded above. This plan supersedes `docs/handoff/architecture-rethink-plan.md` for expansion decisions; that document remains a historical record of the v0.3.0 pivot.*

**Waiting for authorization. No code or repository state was changed.**
