# Golavo Architecture Rethink — Match Cockpit Pivot Plan

> **⚠️ SUPERSEDED (2026-07-12).** This plan was written at v0.2.6 (`49a346e`) and
> its Phase 0/1 recommendations were **implemented** in v0.3.0–v0.3.3 (Match
> Cockpit pivot, Games-first home, Model Lab, on-demand leak-safe council). Its
> "current-state" claims below (§0–§2, and the §13.3 schema-version mechanics)
> now misdescribe the shipped code — e.g. `GET /api/v1/matches/{id}/analysis`
> exists, the nav is Games/Leagues/Model Lab, and `ANALYSIS_SCHEMA_VERSION` is a
> separate field. Read it as a historical record of the pivot's rationale, **not**
> as an authority on today's architecture. For forward expansion decisions see
> [`expansion-plan.md`](expansion-plan.md).

**Status:** SUPERSEDED — Phase 0/1 implemented in v0.3.0–v0.3.3 (was "PLAN ONLY").
**Prepared:** 2026-07-12, against `main` @ `49a346e` (v0.2.6), worktree clean.
**Method:** five-lane repository inspection (UI, core engine, server+data, docs+tests, primary-source license audit) before any proposal. Every material claim below carries a file:line reference or is marked UNVERIFIED.

---

## 0. Reality check (required pre-work)

### 0.1 What genuinely exists and works

- **Five registered model families, honest evaluation.** `FAMILIES` in `core/golavo_core/models/candidates.py:17-23` — climatological, elo_ordlogit, poisson_independent, dixon_coles, bivariate_poisson. All five run on every backtest fold side-by-side (`evaluation.py:195-205`) with log loss, Brier, RPS, ECE and Wilson-interval reliability bins (`evaluation.py:89-141`). No champion is ever declared (`models/__init__.py:1`, `evaluation.py:285`).
- **Chronological, leak-closed backtesting.** Cutoff = window start − 1s; `training_rows` fails loudly on any future row (`test_phase0.py:47`); Dixon-Coles decay tuning is itself leak-free (`evaluation.py:154-171`). Per-league folds for EPL/La Liga/Bundesliga/Serie A/Ligue 1 + three international tournaments.
- **Sealed, content-addressed, immutable artifacts.** `fa_<sha256[:20]>` ids, canonical bytes, idempotent atomic writes, append-only audit log, integrity verified on every read (`artifacts.py:121-295`, `test_write_safety.py` — 11 tests). Score/void append successors, never mutate.
- **Exact-score matrix, coherent by construction.** The sealed 1X2, expected goals, and the 8×8 display grid + outcome-decomposed tail all derive from one converged matrix; coherence is machine-checked at seal time and on every load (`score_matrix.py:170-272`, `test_phase8_score_matrix.py:85-226`).
- **Deterministic facts engine with real guardrails.** 15 pre-registered templates (`facts/registry.py:52-94`), per-template min samples and staleness, the registry itself as the multiple-comparison control (`registry.py:1-14`), coincidence quarantine capped at 3 and never sent to AI (`facts/evidence.py:18`), number-discipline on every fact string (`guardrails.py:35-49`), and a machine-checked no-write invariant: AST-level import isolation from the engine plus byte-unchanged artifact verification (`facts/invariant.py:47-110`).
- **On-demand, leak-safe notebooks for ANY indexed match** — club or international, past or future — computed at `as_of = kickoff − 1s` (`matches.py:446-490`). This is the one place the codebase already does exactly what the pivot needs.
- **Evidence-whitelisted AI narration, fail-closed.** Every number the LLM emits must byte-match the `display` of a whitelisted, source-attributed number or the whole narration is rejected (`ai/whitelist.py:174-212`, `narration.py:263-264`); one retry then `local_only` (`ai_gateway.py:353`). Off by default; local Ollama/llama.cpp or BYOK OpenAI/Anthropic; keys header-only (`ai_gateway.py:46-60,181-201`). Red-team tests exist (`test_phase5_redteam.py`).
- **75,079-match CC0 index** (verified by direct parquet read): 49,505 internationals (1872→2026-07-11, refreshed daily-ish via the martj42 pack) + 25,574 club matches across exactly the big-5 leagues (2010-14 season starts → May 2026). Goalscorers (47,888 rows, with minutes) and shootouts side-tables — internationals only. 100% CC0 sources; OpenLigaDB response bytes still do not ship and its optional runtime database remains physically separate (`packs/overlay-odbl/policy.json`, ADR-0005).
- **A defensively honest README** — pre-alpha warning, explicit not-done list, "not a betting product" (`README.md:44-49`). The doc-honesty even has a test (`test_v0_2_hardening_core.py:98`).
- **Desktop shell + signed in-app updates** (Tauri 2 + PyInstaller sidecar, consent-first updater since v0.2.1).
- **UI quality machinery**: Casual/Expert drawers, reading-comfort system, Playwright+axe CI gate (30 e2e assertions), vitest-covered insight selection.

### 0.2 What exists only as UI or documentation

- **The "live refresh" is passively wired but never triggered in production.** `merge_refreshed_index` (`refresh.py:39-102`) and `repoint_to_refreshed` (`matches.py:73-85`) have zero production callers — repo-wide grep finds only definitions and tests. `GET /api/v1/fixtures/check` (`main.py:342`) *detects* new upstream fixtures but nothing fetches/splices/repoints at runtime. (Matches the v0.2.5 handoff: slices 1-2 of 6 landed.)
- **Pack signature verification** is documented as planned, not implemented — hashes catch corruption, not forgery (`packs/README.md:6-8`).
- **`golavo_core/ledger/`** is an empty stub; the "hash-chained ledger" remains roadmap.
- **The Phase 10 plan header** still says "PLAN ONLY" while its own status appendix and CHANGELOG confirm it shipped — stale header, shipped feature.

### 0.3 What is technically reusable for the pivot

Nearly everything below the UI:

- The **on-demand notebook path** (`matches.py:446-490`) is the exact template for on-demand model analysis: resolve match → scope history to its source → compute at kickoff−1s → fail closed. Generalizing it from "facts" to "fit five families and return probabilities" is the single highest-leverage build.
- `fit_model`/`Prediction` (`candidates.py:254-264`) are already pure functions of (matches, cutoff) — nothing about them requires sealing.
- `build_score_matrix` + derived markets (`score_matrix.py:83-360`) work on any Poisson prediction.
- The eval fold machinery is a ready-made "which model led this league" read model (`eval_summary*.json` already served at `/api/v1/eval/summary`).
- The evidence-bundle/whitelist pattern extends naturally to multi-model bundles (namespaced ids like the existing `nb_*` fold, `facts/evidence.py:36`).
- The artifact write/verify layer can mint new content-addressed object types (`hr_*`, `lo_*`) without touching `fa_*` semantics.

### 0.4 What blocks the proposed product

1. **Zero future fixtures.** Direct parquet check: 0 rows dated after 2026-07-12. The 238 `is_complete=False` rows are historical data gaps (COVID voids, missing scores), not a schedule. A "Today / upcoming" home screen has literally nothing to render until a fixtures ingest exists. This — not navigation — is blocker #1.
2. **No on-demand probability endpoint.** Probabilities exist only inside sealed artifacts; there is no route that fits a model and returns 1X2 for an arbitrary match (`matches.py` §11 finding). The cockpit's core panel has no backend today.
3. **The refresh loop is unwired** (§0.2) — even eligible internationals can't be sealed today because every indexed fixture is already past (`kickoff_passed`, `seal.py:147-152`). The WC2026 semi-finals are ~July 14-15; the index ends July 11. Immediate, dated proof of the blocker.
4. **Seal eligibility is structurally narrow**: `source_kind == "international"` AND source in `_SOURCE_PACKS` (one entry, `seal.py:46`) AND pre-kickoff. Club leagues are excluded because all five share one `source_id` that maps to no pack (`seal.py:130-136`).
5. **Router/contract ceiling**: hand-rolled hash router, no query strings (`MatchSearch.tsx:33-37`), no nested routes; every new surface needs new guarded endpoints in `api.ts` (`ACCEPTED_SCHEMA_VERSIONS`, `contract.ts:15`).
6. **No standings, no season simulation, no team surface** anywhere (verified absent, all three lanes).
7. **License wall for richer data** — see §11: no lawful redistributable source for club xG, lineups, injuries, or events exists as of 2026-07-12.

### 0.5 Where this brief is wrong or incomplete

1. **"Five named model families … not five independent votes" understates it.** `poisson_independent`, `dixon_coles`, `bivariate_poisson` are literally one class (`PoissonModel`, `candidates.py:134-251`) differing only in the final matrix step — and `poisson_independent` and `bivariate_poisson` produce **identical metrics in every fold of every league** (all six eval reports; the fitted covariance collapses to independence). Honest count: **two voices + one baseline** (Elo, one Poisson goal model with three flavors, climatology). Also: `bivariate_poisson` isn't even seal-eligible at the server (`ALLOWED_FAMILIES`, `seal.py:40` — four families, bivariate excluded). The Model Council design must start from this.
2. **"Selecting a game generates useful local analysis immediately" collides with a deliberate, tested honesty boundary** — "never re-forecast a played match as if it were upcoming" (`artifacts.py:336-340`, `MatchDetail.tsx:5-7` "This view NEVER renders engine numbers"). The brief's own three-object model (forecast / replay / review) is the right resolution — but it must be built as *new object types with their own provenance*, not as a relaxation of sealing. The plan treats the current refusal as an asset to reshape, not a bug to delete.
3. **"Existing club data is primarily results/fixtures" is half wrong**: club packs contain **results only — no future fixtures at all** right now (0 future rows). And internationals *do* have per-goal scorer/minute data (47,888 rows) the brief doesn't mention — enough for real goal-timing and scorer facts on the international side.
4. **The brief's "empty ledger ⇒ empty core experience" is confirmed but the mechanism is subtler**: home (`MatchdayList`) renders `GET /api/v1/forecasts` which silently falls back to bundled *synthetic* sample artifacts (`main.py:74-96`) — so the first-run experience isn't empty, it's **fake-but-labeled**, which is arguably worse for trust than empty.
5. **"The UI normally shows one forecast family rather than a true match-level methodology comparison" — confirmed, with a nuance**: a full five-family comparison *does* exist, but only at league level in Evaluation (`EvaluationSummary.tsx:99-110`). The pivot is partly a relocation of that table to match level, not a from-scratch invention.
6. **The brief omits the live moment**: the 2026 World Cup is running *now* (quarterfinals July 10-11 are the index's last rows). The first shippable increment isn't cockpit UI at all — it's wiring the already-written refresh so the semi-finals are sealable. Cheap, dated, real.

---

## 1. Executive verdict and rebuttal

### Where the pivot is right

- **The primary-job reframe is correct and the evidence is structural, not aesthetic.** Home is a sealed-forecast list whose empty state is "No forecasts sealed yet" (`MatchdayList.tsx:27`); nav is Matchday/Matches/Ledger/Evaluation (`Layout.tsx:58-63`); the ledger ships empty by design (`runtime.py:39-49`); and as of today **zero fixtures are sealable**. The product's front door is an audit room for objects that mostly don't exist. Games-first is right.
- **Sealing as an expert/internal operation is right.** The seal machinery is excellent and invisible-by-default is the correct default. "Track this prediction" as the user-facing verb, `fa_*` semantics untouched.
- **Ledger + Evaluation under a Model Lab is right.** Evaluation is already the best model-comparison surface in the app; it's just addressed to nobody. Renamed and re-homed, it becomes the credibility backbone.
- **The three-object model (forecast / replay / review) is the correct resolution** of "analysis for any match" vs "no leakage." The codebase is unusually well prepared for it: deterministic replay is already tested (`test_phase3.py:82` — byte-identical re-derivation), and the on-demand notebook already computes at a strict pre-kickoff horizon.

### What should not be discarded

- The **no-retro-forecast refusal** as a *default posture* — it becomes labeling discipline instead of display refusal.
- The **immutable artifact/provenance/audit machinery** — everything new (replays, outlooks) should *adopt* content-addressing, not bypass it.
- The **facts↔engine isolation invariant** (`facts/invariant.py`) — the new "model disagreement" insight must be composed at the read-model layer, never inside the facts package, or the invariant dies.
- The **sample-data honesty banner**, the warming states, the contract guards, the a11y gate.
- The **Casual/Expert disclosure system** — it generalizes to the cockpit as-is.

### What must be challenged (and my counter-proposals)

1. **"Model Council" as five seats.** Reject. Three seats: **Ratings (Elo)**, **Goal model (Poisson family — one seat, three flavors disclosed)**, **Baseline (climatology, rendered as a reference band, not a voice)**. Anything else launders one method into fake plurality — the fold data proves two of the five columns are duplicates.
2. **"Consensus or leading view" at the top of the cockpit.** No validated ensemble exists; averaging is statistically unearned (§8). v1 consensus is *descriptive only*: the range of P(outcome) across eligible voices + an agreement/disagreement flag. An ensemble is a later, gated experiment.
3. **League Outlook in the first release.** It has the longest dependency chain (fixtures ingest → standings builder → simulator → backtest → calibration) and the least reusable code. It's Phase 4, not MVP.
4. **Teams as a top-level IA item now.** Defer. A team page that is a filtered match list plus streak facts is a search view wearing a hat. Ship `Games` and `Leagues`; revisit Teams when there's a team-level read model worth a page (§19 open decision D6).
5. **"Bring me any match and help me understand it at analyst level"** — for *club* matches the deterministic story is results-derived only (no lineups/xG/injuries lawfully available, §11). The cockpit must be designed so that a results-only information diet still yields a good page — which is why the Commentator Brief and Model Council carry the launch, and why availability-dependent panels must degrade to explicit "Unavailable — no lawful source" rather than thin content pretending otherwise.

---

## 2. Repo evidence map

Every claim from the brief, verified:

| # | Claim | File/symbol | Verified behavior | Product implication |
|---|---|---|---|---|
| 1 | `/` lists forecast artifacts, not games | `App.tsx:53`; `MatchdayList.tsx:12,141` | CONFIRMED — `fetchForecasts()` → cards → `#/forecast/{id}`; empty state "No forecasts sealed yet"; silently falls back to synthetic samples (`main.py:74-96`) | Home must become Games; kill sample-fallback as the default first-run |
| 2 | Nav = Matchday/Matches/Ledger/Evaluation | `Layout.tsx:58-63` | CONFIRMED — exact labels/order; Settings only via gear/footer | IA restructure §5 |
| 3 | Ledger empty until narrow pre-kickoff workflow | `runtime.py:39-49`; `seal.py:110-154`; `main.py:298` | CONFIRMED — single write route, strict gates | Sealing → expert action; Track Record under Model Lab |
| 4 | Forward forecasting = scheduled men's internationals only | `seal.py:46,130-136` | CONFIRMED — `_SOURCE_PACKS` has one entry; club rows all share unmapped `source_id` | Club previews need the new preview/replay objects, not seal changes |
| 5 | Club + completed matches cannot seal | `seal.py:123-128` (`fixture_complete`), `:130-136` (`unsupported_competition`) | CONFIRMED, typed 422s | Same as #4 |
| 6 | Five model families exist | `candidates.py:17-23` | CONFIRMED | — |
| 7 | Not five independent votes; three share Poisson machinery; climatology baseline | `candidates.py:134-251` (one class, `:210-235` only divergence); eval reports: poisson ≡ bivariate in **every** fold | CONFIRMED and stronger than claimed | Council = 2 voices + baseline (§8) |
| 8 | UI shows one family, no match-level comparison | `contract.ts:93-100`; `ForecastDetail.tsx:365`; comparison only in `EvaluationSummary.tsx:99-110` | CONFIRMED — family is server-chosen at seal, default elo (`artifacts.py:308`) | Model Council panel (§7/§8) |
| 9 | "Three things to know" repeats the Notebook below | `InsightCards.tsx:6-9,29`; `CommentatorsNotebook.tsx:36`; `insights.ts:38-55` | CONFIRMED — same fetch, top-3 subset re-rendered above the full list | Brief redesign with dedupe (§9) |
| 10 | Club data is results/fixtures; no xG/lineups/possession/etc. | parquet read; `matches.py` §7 | PARTLY — results only, **zero future fixtures**; internationals additionally have scorers+minutes (47,888) and shootouts (682) | Fixtures ingest is blocker #1; intl-only fact templates possible now |
| 11 | `expected_goals` is model-implied, not observed xG | `candidates.py:200-208,238`; `evidence.py:264-285` labels "Expected goals" | CONFIRMED — Poisson rates; matrix-mean cross-check | Never label as xG; League Outlook xG columns omitted (§10) |
| 12 | No season simulator / league-table contract | repo-wide greps (3 lanes) | CONFIRMED absent | Build new (§10) |
| 13 | Backtesting/1X2/matrices/calibration/metrics/provenance/AI-whitelist strengths | §0.1 refs | CONFIRMED all | Preserve; recompose |
| 14 | ~75,000 indexed matches | parquet: 75,079 | CONFIRMED | — |
| 15 | (Not in brief) Refresh engine unwired in production | `refresh.py:39-102`; grep: tests only | NEW FINDING | Wire it first; it gates everything live |
| 16 | (Not in brief) `bivariate_poisson` not seal-eligible server-side | `seal.py:40` | NEW FINDING | Council eligibility table must read server truth |
| 17 | (Not in brief) Men's data only, zero women's rows | parquet scan | NEW FINDING | Scope honesty in coverage claims |

---

## 3. Current-to-target capability matrix

| Capability | Disposition | Notes |
|---|---|---|
| Model fitting (`fit_model`, five families) | **Reuse unchanged** | Already pure (matches, cutoff) → Prediction |
| Score matrix + derived markets | **Reuse unchanged** | Works for any Poisson prediction |
| Chronological eval + per-league folds + metrics | **Reuse unchanged** | Feeds Model Lab and council context |
| Artifact write/verify/audit layer | **Reuse unchanged** | Extend with new id prefixes only |
| Facts engine + guardrails + invariant | **Recompose** | New templates (§9.4); taxonomy mapping; engine untouched |
| On-demand notebook path | **Recompose** | Generalize the pattern into on-demand MatchAnalysis |
| Seal flow (`seal.py`) | **Reuse unchanged** | Re-labeled as expert "Track this prediction"; eligibility unchanged in MVP |
| Evidence bundle + AI whitelist | **Refactor (additive)** | vNext: multi-model numbers, brief taxonomy, capability warnings (§12) |
| Refresh engine (`refresh.py`) | **Refactor (wire it)** | Slices 3-6 from the v0.2.5 plan; production trigger + UI status |
| Hash router / `App.tsx` route chain | **Refactor** | Param+query support; redirects for old routes (§5) |
| MatchdayList (home) | **Recompose → Games home** | Card/skeleton/filter code largely reusable |
| MatchSearch | **Recompose** | Becomes Games browse+search backbone |
| MatchDetail | **Recompose → Match Cockpit shell** | Header/facts/eligibility logic carries over |
| ForecastDetail | **Reuse (relocated)** | Becomes the sealed-snapshot detail under cockpit/lab |
| PredictionLedger | **Reuse (relocated)** | → Model Lab › Track Record |
| EvaluationSummary | **Reuse (relocated)** | → Model Lab › Backtests |
| Sample-artifact fallback | **Reject (as default)** | Keep behind an explicit "demo data" toggle; never silent |
| League standings builder | **Build new** | From results; needed by Leagues + Outlook |
| Fixtures ingest (club + intl) | **Build new** | §11 sources; blocker #1 |
| On-demand model analysis endpoint (preview/replay) | **Build new** | The pivot's core (§13) |
| Model Council read model | **Build new** | Composition over existing fits (§8) |
| Season simulator | **Build new — Phase 4** | §10 contract |
| Team pages / TeamOutlook | **Defer** | §19 D6 |
| Observed xG/xGA/xA, lineups, injuries | **Defer indefinitely** | No lawful source (§11); show as Unavailable |
| Betting-style framing | **Reject** | Existing lexicon guards already enforce (`whitelist.py:38-73`) |

---

## 4. Launch user and jobs-to-be-done

| Candidate | Core job | What Golavo has for them today | Gap to delight | Verdict |
|---|---|---|---|---|
| Curious fan | "Who'll win tonight? Quick and pretty." | 10-second summary is buildable; but expects live scores, lineups, club previews with team news | Needs live/licensed data we lack; churns on first "Unavailable" | Not primary |
| **Commentator / content creator** | "I'm covering/watching this match — arm me with accurate, sourced talking points in 10 minutes." | The notebook IS this product: pre-registered facts, base rates, H2H, streaks, source popovers, quarantined trivia "for the pub"; plus honest model probabilities and score scenarios | Needs: any-match access (replay/preview), dedupe fix, richer results-derived templates, export | **PRIMARY** |
| Serious analyst | "Give me xG, events, markets vs models." | Calibration rigor they'd respect | Blocked on data we cannot lawfully ship; they'll leave | Not primary (subset served via Expert mode) |
| **Model enthusiast** | "Which methods work where, and are the probabilities honest?" | Evaluation, calibration, reliability diagrams, abstention, provenance — best-in-class for a local tool | Needs: match-level council, per-league track record surfacing | **SECONDARY** |

**Decision: primary = commentator/content creator; secondary = model enthusiast.**
Rationale: the commentator's job is fully servable from data we already lawfully own (results-derived facts + model probabilities + history), it monetizes attention on *every* match (past and future, club and international), and it names the product's existing crown jewel (Commentator's Notebook). The model enthusiast is the credibility audience and is served by relocating — not building — Evaluation/Ledger. The curious fan gets the 10-second layer for free but is not the design target; the serious analyst is explicitly deferred until the data exists (§11).

---

## 5. Target information architecture and route map

### 5.1 Verdict on the candidate IA

Adopt with two amendments: **Teams deferred out of v1**, and **Search promoted into Games** (not a separate destination — the current `/matches` search becomes Games' browse mode).

```
Games            (home, default)
Leagues          (big-5 hubs + Internationals hub)
Model Lab
  ├─ Methodologies      (new: honest description of the 2+1 voices, family table)
  ├─ Track record       (= PredictionLedger, real seals only)
  ├─ Calibration        (running reliability, from ledger)
  ├─ Backtests          (= EvaluationSummary, per-league folds)
  └─ Audit trail        (artifact browser: fa_/hr_ objects, audit.jsonl view)
Settings         (unchanged, + data-refresh controls)
```

Ledger does not survive as a top-level destination: its user question ("how honest were you?") is a Model Lab question. The brief's condition — "unless user research proves it answers a primary job" — is not met by any evidence in the repo; the ledger has been empty since release.

### 5.2 Route map

| Route | Renders | Status |
|---|---|---|
| `#/` | **Games** home: Today/Upcoming (post-fixtures), Recent results, league quick-links, search | reshaped `MatchdayList`+`MatchSearch` |
| `#/match/:id` | **Match Cockpit** (canonical for past+future) | reshaped `MatchDetail` |
| `#/forecast/:id` | Sealed snapshot detail (unchanged renderer, re-framed heading) | kept — deep links survive |
| `#/league/:slug` | League hub: season match list, standings (Phase 3), Outlook (Phase 4) | new |
| `#/lab` (+ `/lab/track-record`, `/lab/backtests`, `/lab/calibration`, `/lab/methods`, `/lab/audit`) | Model Lab | relocations |
| `#/settings` | Settings | unchanged |
| `#/matches` | 301-style hash redirect → `#/` (search open) | migration shim |
| `#/ledger` | redirect → `#/lab/track-record` | migration shim |
| `#/eval` | redirect → `#/lab/backtests` | migration shim |

Router work (small, contained): extend `useHashRoute` (`hooks.ts:5-20`) to parse `#/path?query` so search/filter state can live in the URL (fixes the sessionStorage workaround at `MatchSearch.tsx:33-37`); keep hash routing (Tauri `file://` friendly); replace the `App.tsx:52-75` if-chain with a small route table.

---

## 6. Complete user-flow specifications

Legend for every journey: **E** entry point → **A** primary action → **H** information hierarchy → **D** required data → **C** deterministic calcs → **AI** optional AI → **T** trust/provenance → **F** failure/missing-data → **✓** completion criterion.

**J1 — Opens Golavo with no match in mind.**
E: launch → `#/` Games. A: scan Today/Upcoming; tap a match. H: (1) next matches with kickoff + competition chips, (2) recent results with final scores, (3) league quick-links, (4) search. D: index + fixtures feed; freshness stamp. C: none beyond sort/group (kickoff asc for upcoming, desc for recent). AI: none. T: footer data chip (Live/Sample) + "index as of {date}" stamp in the header of the Today rail. F: **no fixtures ingested** → rail says "No upcoming fixtures in this snapshot — refresh data or browse recent matches" with a working Recent rail beneath (recent always exists: 430 matches since May); offline → same page from local index, refresh affordance disabled with reason; loading → existing `ListSkeleton`. ✓: one tap from launch to a cockpit.

**J2 — Searches for a future fixture.**
E: Games search box. A: type team; pick fixture. H: grouped Internationals/Club (existing `GROUPS`), Upcoming badge first when query matches a scheduled team. D: index rows incl. future fixtures. C: existing tokenized AND search + alias table. AI: none. T: "Result not in snapshot" badge logic kept (`MatchSearch.tsx:383-394`). F: no future fixture found → row-level explainer "2026-27 club fixtures not yet published in the open feed" (capability-aware, §13 DataCapability); 503 warming state kept. ✓: fixture cockpit open with Preview panel.

**J3 — Selects a past match.**
E: search or Recent rail. A: open cockpit. H: final score hero → At-a-glance (replay) → council → brief. D: index row + on-demand replay + notebook. C: HistoricalReplay: fit all eligible families at `as_of = kickoff − 1s` over the row's own source history; facts at same cutoff. AI: Post-match Analyst Read (review bundle). T: replay banner: "Reconstructed with data available before kickoff — not a forecast that existed at the time" + cutoff timestamp + pack hash. F: team below `MIN_TEAM_MATCHES=10` → council rows show "abstained (insufficient history)" exactly like sealed abstentions; notebook fails closed to `available:false` copy (existing). ✓: user can answer "what would the models have said, and what actually happened?"

**J4 — Ten-second summary.**
E: any cockpit. A: none (top panel is the summary). H: verdict sentence ("Elo and the goal model both lean {Home} — {58}% vs {23}% draw, {19}% {Away}"), one likely-score chip, one uncertainty chip, one "models disagree" flag when true. D/C: council outputs + agreement calc (§8.4). AI: none — this layer is always deterministic. T: object-type chip (Forecast/Preview/Replay/Review) always adjacent to the verdict. F: all models abstain → verdict becomes "Not enough history to model this fixture" + notebook still renders. ✓: comprehension in one viewport, no scroll.

**J5 — Investigates why models disagree.**
E: cockpit "models disagree" flag. A: expand Model Council. H: per-voice rows → disagreement callout ("Elo rates {Home} stronger than recent goals do — rating {ΔP} higher on the win") → per-league track-record chips → link to Lab Backtests. D: council read model + eval summaries. C: pairwise ΔP, JS divergence (expert), which-input attribution (rating diff vs attack/defence rates — descriptive, from `params`). AI: may narrate the contradiction, citing whitelisted numbers only. T: each row carries family version + params_hash on hover (expert). F: single-voice matches (one family abstains) → callout explains the missing voice instead of comparing. ✓: user can articulate *which* method leans where and its league-level credibility.

**J6 — Prepares commentator notes.**
E: cockpit → Commentator Brief. A: read summary 4 (What matters most / Disagreement / Form-matchup edge / Key unknown) then expand full brief; export (J12). H: summary slots → taxonomy groups → quarantined Color box. D: notebook vNext (§9). C: facts engine + new selector with dedupe. AI: optional "Analyst read" appended, clearly separated. T: per-fact source popovers (existing), registry version footer. F: sparse fixture (few H2H) → slots fill from wider scopes with scope labels, never invented; empty group headers suppressed. ✓: user leaves with ≥4 sourced, non-duplicated talking points.

**J7 — Follows a club.**
E: search → team results. A: v1: none dedicated (Teams deferred); the compensating affordance is a league-hub roster link-list + saved search chip (localStorage) on Games. D: existing search. F: n/a. ✓: two taps to any club's next/last match. (Full watchlist/team page: §19 D6, Phase 5 candidate.)

**J8 — Explores a major league.**
E: Leagues nav → league hub. A: browse season matches; later standings/Outlook. H: hub = season selector → match list (matchday-grouped) → standings (Phase 3) → Outlook teaser (Phase 4). D: index rows per competition (exists); standings computed from results (new, deterministic); fixtures for current season. C: standings builder with league tiebreak rules (§10.3). AI: none. T: "computed from results in snapshot {hash}" footer. F: season incomplete in snapshot → standings labeled "through {last date}"; pre-fixtures → hub still full for 16 finished seasons. ✓: any of ~70 league-seasons browsable to cockpit depth.

**J9 — Compares methodologies.**
E: Model Lab › Methodologies + Backtests. A: read voice descriptions; inspect fold tables. H: honest family tree (one Poisson class → three flavors), per-league winners with sample sizes, "no permanent champion" statement backed by fold flips (EPL: Elo 2/3; La Liga: goal models 3/3…). D: existing eval JSONs. C: none new. AI: none. T: links to eval report provenance. F: league without folds → absent row, no interpolation. ✓: user can explain when Elo beats goal models and that bivariate ≡ independent empirically.

**J10 — Enables local or BYOK AI.**
E: Settings › Local intelligence (exists). A: pick provider; run Deep Read from a cockpit. Flow unchanged (off → idle → run → verified render); extended to preview/replay/review bundles. T: existing "AI never changes the numbers" strip; provider/model/prompt_version shown. F: existing disabled/unavailable/local_only ladder (`ai_gateway.py:5-19`). ✓: first verified narration or an honest failure state.

**J11 — Stays offline, AI off.**
E: any. Behavior: 100% of deterministic surface works from the local index/packs (search, cockpit replay/preview, brief, lab); refresh check disabled with reason; AI cards show OffCard. This is the **defining constraint**: every MVP panel must pass a "works from parquet + packs alone" test. ✓: no network sockets opened except loopback (existing posture, `main.py:48-64`).

**J12 — Saves, revisits, exports, shares an analyst brief.**
E: cockpit. A: v1 export = Markdown/clipboard of the brief + council table (deterministic, source-attributed, includes object-type + cutoff + snapshot hash lines); "Track this prediction" (seal) for eligible fixtures = the durable save; revisit via Games › Recent + Lab › Track Record. D: existing artifact store; no new persistence for exports. AI: excluded from export v1 (avoids shipping unverifiable prose); §19 D8. T: export embeds provenance block verbatim. F: export of a preview stamps "PREVIEW — will change with data" banner text. ✓: pasteable brief a creator can use in prep notes.

---

## 7. Match Cockpit panel specification

Order tested against the brief's proposal — adopted with one change: **Commentator Brief moves above Scoreline distribution for the primary persona** (commentator prep beats scenario nerdery; Expert mode restores the analytical order). Panels:

| # | Panel | User question | Displayed fields | Source | Casual vs Expert | Unavailable behavior | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | Identity strip | "Am I on the right match? How fresh?" | teams, competition+stage, kickoff/status, venue+neutral flag, object-type chip (Forecast/Preview/Replay/Review), snapshot freshness | index row (exists: `MatchHeader.tsx`) | same | — (always renderable) | **MVP** |
| 2 | At a glance | "Ten-second read?" | leading view sentence, 1X2 bars (whole-number, existing `ProbabilityBar`), model-implied goals pair, likely score band (from matrix argmax + band), uncertainty chip, missing-input notes | council read model | casual: sentence+bars; expert: adds per-voice mini-table | all abstain → "Not enough history" card; notebook remains | **MVP** |
| 3 | Model Council | "Who says what, and why should I trust them here?" | per-voice: P(H/D/A), expected goals (goal model only), most-likely score, abstained?, league track-record chip (log-loss rank last folds, N), cutoff | new (§8) | casual: 2 voices + baseline band; expert: + flavors (DC/BP/PI sub-rows), JS divergence, params hashes | voice abstains → labeled row, never hidden | **MVP** |
| 4 | Why the lean | "What drives it?" | rating gap (Elo params), attack/defence rates (Poisson params), recent form W/D/L squares, home/away split, opponent-quality note | model `params` (exists in Prediction) + results-derived form series (new, cheap) | casual: 3 bullets; expert: numbers table | rest/travel/weather rows: omitted until sourced (§11) | **MVP (results-derived subset)**; weather/rest = Later |
| 5 | Commentator Brief | "What do I say on air?" | §9 structure | facts engine vNext | casual: 4 summary slots; expert: full taxonomy | sparse → wider-scope fill, labeled | **MVP** |
| 6 | Scoreline & scenarios | "Plausible scores?" | 8×8 heatmap (exists: `ScoreMatrixHeatmap`), tail note, totals bands, double chance | `score_matrix.py` (reuse) | casual: top-3 scores; expert: full grid+bands | non-goal voice leading (Elo) → panel notes "score grid from the goal model" | **MVP** (reuse) |
| 7 | Team comparison | "How do they stack up?" | last-10 form, goals for/against rates, clean-sheet %, H2H aggregate, streaks | results-derived (new aggregations, same guardrail style) | casual: 5 rows; expert: + since-year spans, samples | thin history → row-level "n too small" | **Phase 2** |
| 8 | AI Analyst Read | "Synthesis?" | existing AiDeepRead extended to bundle vNext | ai_gateway (reuse) | same | existing ladder | **MVP for sealed/replay; preview bundles Phase 2** |
| 9 | Data & methods disclosure | "What am I looking at?" | object-type definition, cutoff, snapshot hashes, pack licenses, capability notes ("no lineups: no lawful source"), method links | provenance (exists) + DataCapability (new) | drawer (existing pattern) | — | **MVP** |
| — | Live/in-match panel | — | — | no lawful live feed | — | — | **Rejected** (fabrication risk; Phase-10 precedent: "would be fabricated — Rejected") |
| — | Betting/odds panel | — | — | — | — | — | **Rejected** (product constitution) |

---

## 8. Model Council statistical contract

### 8.1 Voices and grouping

- **Voice A — Ratings**: `elo_ordlogit`. 1X2 only; no score grid (`test_phase8: non_goal_family_has_no_score_matrix`).
- **Voice B — Goal model**: the `PoissonModel` family. Council seat shows **dixon_coles** as representative (best-motivated flavor; low-score corrections); expert sub-rows show poisson_independent and bivariate_poisson with the standing empirical note that BP has never diverged from PI on any fold. Sub-rows are *disclosure*, never votes.
- **Baseline — Climatology**: rendered as a shaded reference band behind the voices' bars ("league base rates: {45}/{27}/{28}"), never a row that "agrees" or "disagrees". Its job is to show how much signal the voices add.

### 8.2 Row contract (per voice)

`{family, flavor?, probs(1X2), expected_goals?, most_likely_score?, abstained + reason, uncertainty, training_cutoff_utc, league_track_record {competition, folds_n, mean_log_loss, rank, last_fold_win?}, params_ref (expert)}` — all fields already derivable from `Prediction` + eval summaries; no new statistics required for MVP.

### 8.3 Consensus: descriptive, not an ensemble

v1 top-of-cockpit "leading view" = the voice with the better league-specific mean backtest log loss (displayed as *"led recent backtests in this league"*), with the other voice's probabilities always one glance away. If they disagree on the modal outcome → no leading view; the header states the disagreement instead. **No averaging.** Reason: an unvalidated mean of two correlated models is a third, worse-understood model wearing a neutral costume.

### 8.4 Disagreement metrics

- Casual: flag when modal outcomes differ OR max |ΔP| ≥ 8 points (threshold pre-registered, revisit after calibration data).
- Expert: max |ΔP| per outcome + Jensen–Shannon divergence.

### 8.5 Ensemble, if ever — the gate

Train per-league log-pool weights (2 voices) on chronological folds; evaluate on a held-out later season never touched during weight fitting; promote only if it beats the better single voice on log loss with a pre-registered margin (≥0.005) AND doesn't degrade ECE. Weights sealed with provenance like any model version. Until passed, "consensus" stays descriptive. (Fold data hints the flip-flopping winners could make a pooled model attractive — EPL Elo 2/3 vs La Liga goal-models 3/3 — but that's exactly the multiple-comparison trap the registry philosophy exists to avoid; pre-register first.)

### 8.6 Preferred-model-per-league

Descriptive chip only, computed from existing `eval_summary_*.json`: rank by mean log loss across that league's folds with N shown. Never auto-selects the sealed family (seal default stays explicit/caller-chosen).

### 8.7 Genuinely diverse future families (Later, at most one per phase)

1. Gradient-boosted ordinal classifier on engineered features (form, rest days, H2H, home split) — different bias class from both voices.
2. Historical-analogue ("climatology conditioned on Elo-gap bucket") — cheap, interpretable, honest uncertainty.
3. Bayesian hierarchical goals model — better shrinkage + parameter uncertainty for Outlook intervals.
Each enters via the same fold gauntlet before earning a council seat.

### 8.8 Abstention

Existing rule (min 10 matches/team in 8y window, `artifacts.py:37,203-210`) becomes per-voice and visible: an abstaining voice renders as "abstained — {home} has {6} qualifying matches" rather than disappearing.

---

## 9. Commentator Brief — taxonomy and non-duplicative selection

### 9.1 Taxonomy mapping (existing 15 templates → new labels)

| New label | Existing templates | New in Phase 2 |
|---|---|---|
| Signal | `home_advantage_base_rate`, `competition_debut_base_rate` (the current "predictive" label renames to Signal — same never-applied guarantee) | scoring-rate trend, draw-rate |
| Matchup | `head_to_head_record` | H2H goal aggregate, BTTS rate |
| Form | `unbeaten_run`, `winless_run`, `win_streak`, `clean_sheet_run`, `home_away_form` | opponent-quality-adjusted form note |
| History | `biggest_win`, `neutral_venue_record` | — |
| Milestone | — | Nth international/meeting milestones |
| Availability | — | **stays empty until a lawful source exists — header suppressed, capability note in disclosure panel** |
| Conditions | — | rest-days differential (computable from index dates now); weather Later (§11) |
| Context | `top_scorer`, `shootout_record` (intl only) | promoted/relegated-side note (club) |
| Color | `day_of_week_streak`, `scoreline_repeat`, `calendar_date_repeat` (quarantine semantics unchanged: capped 3, never to AI) | goal-minute quirks (intl only, from goalscorers.parquet) |
| Unknown | — | generated from DataCapability + abstention states (e.g., "No lineup data exists in Golavo's sources; availability is unknown") |

`Unknown` is a first-class output: the brief must say what it cannot know. These are template-generated from machine state (capability tiers, abstentions, staleness), not free text.

### 9.2 "What matters most" — the four summary slots

Replaces "Three things to know". Slots, each with its own selection rule, drawing from **different sections**:

1. **What matters most** — top fact by the existing closest-first comparator (`insights.ts:38-55` reused) across Signal/Matchup/Form/History.
2. **Model disagreement** — synthesized from the council read model (NOT the facts engine — preserving `facts/invariant.py` isolation means this card is composed at the cockpit read-model layer; the facts package never imports model output). Absent when voices agree; slot then backfills with fact #2.
3. **Form/matchup edge** — best Form or Matchup fact not already used in slot 1.
4. **Key unknown** — top Unknown item; on data-complete fixtures, the least-covered input (e.g., "first meeting since {2014} — H2H sample thin").

### 9.3 The dedupe contract (fixes the structural repetition)

The notebook response carries `summary_fact_ids[]`; the full brief renders those facts **as anchors, not repeats** — summary cards deep-link to the row, and the row shows a "▲ in summary" marker instead of appearing twice at full width. Selection stays pure/deterministic/vitest-covered (extend `insights.test.ts`). Acceptance test: `summary ∩ list-render = ∅` at the DOM level.

### 9.4 New deterministic templates from EXISTING data (pre-registered, before any new provider)

All computable from `matches_index.parquet` + side tables, same guardrail style (min_sample, staleness, number-discipline):

| Template | Scope | Data | Min sample (proposed) |
|---|---|---|---|
| `scoring_rate_trend` (goals/match last 10 vs season) | team | index | 10 |
| `btts_rate` (both teams scored, H2H + team) | team/h2h | FT scores | 8 |
| `draw_rate_context` | team/competition | index | 20 |
| `rest_days_differential` | match | match dates | structural |
| `fixture_congestion` (matches in last 14 days) | team | dates | structural |
| `h2h_goal_aggregate` | head_to_head | index | 4 |
| `milestone_cap` (Nth international / Nth meeting) | team/h2h | index | structural |
| `late_goal_share` (goals after 75') — **internationals only** | team | goalscorers.parquet minutes | 15 goals |
| `penalty_reliance` — **internationals only** | team | goalscorers.parquet penalty flag | 10 goals |
| `promoted_side_note` | team | season membership diff | structural |

Registry bump `REGISTRY_VERSION`, family_size grows accordingly (multiple-comparison control preserved by pre-registration; no data-mined one-offs).

### 9.5 Protections carried forward unchanged

Pre-registration (registry = the control), min samples, staleness suppression + logging, source attribution popovers, coincidence quarantine (cap 3, never to AI), number-discipline, no invented filler (empty groups suppress their headers), no trivia touching probabilities (invariant tests keep running in CI).

---

## 10. League Outlook and season simulation contract

**Phase 4. Blocked until fixtures ingest (Phase 1) is proven.** Scope: EPL, La Liga, Bundesliga, Serie A, Ligue 1.

### 10.1 Table columns (launch set)

Position, points, played; projected points (median); median finish; finish interval (5th–95th percentile); P(title); P(top-4)†; P(relegation); projected GF/GA (model-implied — labeled "model-implied goals", never xG); attack/defence strength index (normalized Poisson rates); strength trend (rate now vs 10 matchdays ago); schedule difficulty (mean opponent strength remaining); per-voice projection deltas (expert drawer); consensus/disagreement note.
† "Top-4" labeled as a table position probability, not "Champions League qualification" — European slot allocation varies by season/coefficients and cup winners; the honest claim is positional.
**xG / xGA / xA columns: omitted.** A one-line capability note explains: "Shot-based xG requires event data with no lawful open source; Golavo does not fabricate proxies." (§11.)

### 10.2 Simulation spec

- **Inputs**: current standings (computed from index results — new deterministic builder), remaining fixtures (from fixtures feed), per-fixture score distributions from the goal model fitted at snapshot cutoff (reuse `PoissonModel` + full matrix, not just 1X2 — settles GD tiebreaks properly).
- **Method**: Monte Carlo, **10,000 runs** default (vectorized numpy sampling from per-fixture matrices; ~380×10k draws is sub-second), fixed seed = f(snapshot hash) → byte-reproducible outputs; store `{seed, n_runs, snapshot_sha, model_version, params_hash}` in an `lo_*` content-addressed artifact via the existing write layer.
- **Tiebreaks, per league** (encoded as data, unit-tested): EPL: Pts→GD→GF→H2H; La Liga: Pts→H2H→GD→GF; Bundesliga: Pts→GD→GF→H2H-away-goals; Serie A: Pts→H2H→GD→GF; Ligue 1: Pts→GD→GF. (Verify exact current rules per league during Phase 4 implementation — rules drift; encode with a season tag.)
- **Promoted teams**: attack/defence prior = shrunk league-entrant baseline (mean of promoted sides' first-season rates over the pack's history), decaying to fitted rates as matches accrue; flagged "thin prior" in the UI for the first ~6 matchdays.
- **Postponements/reschedules**: fixtures feed diff → resimulate on refresh; every Outlook render names its snapshot ("as of {date}, {n} fixtures remaining"). No intra-season memory: each Outlook is a pure function of (snapshot, seed).
- **Correlated uncertainty**: v1 uses point-estimate strengths — intervals will be **too narrow**; the UI must say so ("intervals reflect match randomness only, not rating uncertainty"). v2: parameter bootstrap (refit on resampled match history, e.g. 200 outer draws × 50 inner sims) — gate on runtime budget.
- **Backtest before launch**: replay past seasons from matchdays {10, 19, 28}: coverage of finish intervals (a 90% interval should contain the realized finish ~90% of the time), PIT histograms for points, Brier for title/relegation events. Acceptance gate: relegation-event Brier beats a "current-position-persists" baseline on ≥4 of 5 leagues.
- **Caching/runtime**: `lo_*` artifact per (league, snapshot); recompute only on snapshot change; target <2s cold on the sidecar.

---

## 11. Data / license / coverage matrix

*(Primary-source verification run 2026-07-12 — see agent audit; cross-checked against `docs/research/free-open-data-sources.md`, itself verified 2026-07-10 across 46 sources.)*

### 11.1 Source matrix (primary sources fetched 2026-07-12; quotes <15 words; UNVERIFIED items flagged)

| Source | License/terms (primary link) | Data fields | Competitions/seasons | Status | Refresh | Key? | Rate limits | Redistribute | Cache | Offline bundle | Attribution/SA duties | Restrictions | Provenance risk | Reliability risk | **Classification** |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| OpenFootball football.json | Public domain — "dedicated to the public domain… no restrictions" (github.com/openfootball/football.json README) | results + fixtures (round, date, teams, FT score) — no events/lineups/xG | Big-5 + 2nd tiers, 2010-11→2025-26 | historical + current | daily bot commits; **latest 2026-05-30 — no 2026-27 files yet** | No | n/a (git) | Yes | Yes | Yes | none | none | community-sourced accuracy | fixture-publication lag (R1) | **bundled open core** (already is) |
| martj42/international_results | CC0-1.0 (repo LICENSE) | results, goalscorers (minutes, pens, OG), shootouts | men's full internationals 1872→present | historical + current | near-daily; latest **2026-07-11** | No | n/a | Yes | Yes | Yes | none | none | low | low | **bundled open core** (already is) |
| martj42 women's results | CC0 per same author (UNVERIFIED — verify repo license before use) | results | women's internationals | historical | active | No | n/a | Yes* | Yes* | Yes* | none | none | low | verify | **candidate bundled core** (D11, Phase 2 check) |
| OpenLigaDB | ODbL 1.0 — "Daten … unter der Open Database License" (openligadb.de) | display-only fixtures/results in v1 | current-season Bundesliga 1/2/3 + DFB-Pokal only (`bl1`, `bl2`, `bl3`, `dfb`) | current + community-maintained | user-triggered; optional while-open checks | No | none published | adapted DB remains ODbL-isolated | Yes | per-user only | ODbL attribution + share-alike duties disclosed | no model/seal/settlement/export use | community-entered; conflicts fail closed | medium | **implemented optional isolated overlay; no response bytes ship** |
| football-data.org | proprietary, thin: /pricing + docs policies; **/terms is 404** | fixtures, results, standings (free: scores delayed, no lineups/scorers) | 12 comps incl. big-5, CL, WC, Euros | current | API | Yes (free) | 10/min | **not granted** | **not granted** (silent → assume no) | No | "Data provided by football-data.org" visible | commercial unstated | hosted-service ToS drift | medium | **user-fetched local adapter** (never in releases) |
| StatsBomb Open Data | "StatsBomb Public Data User Agreement" 2023-09-08 (LICENSE.pdf read in full) | events incl. shot xG, lineups, 360 | select tournaments: WC22, Euro 2020/2024, WWC23, WEuro25, Copa América 24, + leagues archive | historical | occasional drops | No | n/a | **No** (§1.2.1) | local only | **No** | StatsBomb logo on publications (§1.4) | **no commercial exploitation** (§1.2.2); revocable (§2.1) | terms ≠ open license | scope-limited | **research-only, user-fetched** (calibration research, never ship) |
| Open-Meteo | data CC-BY 4.0; free API "non-commercial purposes" (open-meteo.com/en/terms) | weather incl. historical to 1940 (ERA5) | global | historical + forecast | API | No | 10k/day, 600/min | Yes (CC-BY) | Yes | Yes (data) | CC-BY attribution | free API tier non-commercial | low | low | **user-fetched local adapter, cache-forever** (Conditions panel, Later) |
| GeoNames (dumps) | CC-BY-4.0, reverified from the official dump README 2026-07-15 | city/place coordinates, timezone, elevation | global | static | pinned bulk snapshot; compact extraction ships | No | none | Yes + credit/change notice | Yes | Yes | Data from GeoNames + license link | display-only context | exact-name collisions fail closed under ADR-0006 | low | **bundled enrichment side table; never called stadium geocoding** |
| Wikidata structured entities | CC0-1.0, reverified 2026-07-15 | stable IDs, reviewed aliases/federations/venue metadata | selected referenced entities only | static | revision-pinned individual entities | No | none | voluntary credit | Yes | selective only | Data from Wikidata | display-only context | QID links require manual review; prose/media excluded | low | **approved selective context, not yet bundled** |
| Natural Earth | public domain, reverified 2026-07-15 | lightweight offline basemap | global 1:110m | static | release/commit + SHA-256 | No | none | voluntary credit retained | Yes | Yes | Made with Natural Earth | display-only map | not a political-boundary authority | low | **bundled enrichment side table** |
| OSM / Nominatim | ODbL + strict usage policy (operations.osmfoundation.org) | geocoding | global | static | ≤1 req/s, must cache | No | 1 req/s | share-alike | required | small extracts | ODbL SA + attribution | policy-bound | low | low | one-time geocode + permanent cache; prefer GeoNames |
| FBref / Sports Reference | ToS pages 403 to bots (itself enforcement evidence); terms via search snippets: scraping banned; **xG removed Jan 2026** (Opta/Stats Perform pullback, press-verified) | (was) xG, lineups, scorers | big-5 | — | — | — | >10/min = block | No | No | No | — | prohibited | fatal | data gone anyway | **reject** |
| Understat | **no published ToS found (UNVERIFIED)**; only a 2018 support email cited by scrapers | xG | big-5 | current | — | — | — | unknown | No | No | — | informal non-commercial | fatal | unknown | **reject** |
| Sofascore / FotMob | ToS (JS-rendered; snippets): bans "scraping, crawling", data mining, resale | live scores, lineups, stats | broad | live | — | — | — | No | No | No | — | prohibited | fatal | — | **reject** |
| TheSportsDB | proprietary ToS: no resale; **app-store publishing requires paid tier** ($9/mo); storage not addressed | events, TV, artwork, crests | broad, crowd-sourced | current | API | test key `123` / paid | 30/min free | No | ambiguous | No | logos "as is" | app distribution needs Premium | crowd-sourced provenance | medium | **user-fetched adapter (dev/personal) / optional BYOK** |
| API-Football (api-sports.io) | terms 403 to direct fetch; snippets: **no license to publish data granted**; rights-holder IP passes through | fixtures, lineups, injuries, odds | broad | current + live | API | Yes | 100/day free | No | user's risk | No | — | publication rights not granted | high | — | **optional BYOK provider only** |
| Fjelstul English Football DB | CC-BY-SA 4.0 | results, appearances 1888-2024 | England | historical | static | No | n/a | share-alike | Yes | isolated | CC-BY-SA | share-alike | low | England-only, no xG | **isolated share-alike pack** (candidate, low priority) |
| Kaggle/HF scrape-derived sets (Transfermarkt injuries, "CC-BY" API mirrors) | downstream labels don't cure upstream terms (license laundering — matches repo research doc verdicts) | varies | varies | — | — | — | — | No | No | No | — | inherited restrictions | fatal | — | **reject** |

Cross-check: the repo's own 46-source audit (`docs/research/free-open-data-sources.md`, verified 2026-07-10) reaches the same verdicts everywhere the two overlap; its Phase-0 "accept exactly one pack" decision was correct then and is correctly superseded now only by adding the already-vendored openfootball packs.

### 11.2 Consequences

1. **Fixtures (blocker #1)**: internationals — martj42 (CC0, already refreshed, active as of yesterday). Club 2026-27 — openfootball when published (CC0, bundleable; watch the repo); **bridge option** if late: football-data.org free tier as a *user-fetched adapter* (fixtures fetched at runtime with the user's free key, cached locally, never redistributed, attribution shown). Ship the adapter capability-gated so the app is honest when it's unconfigured.
2. **Standings**: computable from owned results — no external dependency (Phase 3).
3. **Observed xG/xGA/xA, lineups, injuries, events for current big-5 seasons**: **no lawful open source exists as of 2026-07-12.** FBref's removal of xG (Jan 2026) moved the market *away* from openness. Product stance: Unavailable states + `DataCapability`, StatsBomb research-only for internal calibration research on covered tournaments, BYOK (API-Football) as a user-risk adapter never feeding bundled artifacts. No proxies mislabeled as xG — the model-implied `expected_goals` keeps its existing honest label.
4. **Weather (Conditions panel, Later)**: Open-Meteo historical — CC-BY data, cache-forever, attribute; note the free-API non-commercial tier in docs.
5. **Bundesliga display context**: OpenLigaDB is implemented for current-season Bundesliga 1/2/3 and DFB-Pokal fixtures/results only. It is opt-in, community-labeled, stored in a separate two-generation database, removable, and never joined to the CC0 core. Structured enforcement now supplements `scripts/check_license_isolation.sh`. World Cup, tables, goalgetters, model inputs and settlement are explicit v1 non-goals.

### 11.3 Capability tiers (served by `DataCapability`, shown in UI disclosures)

| Tier | Contents | Example user-visible effect |
|---|---|---|
| **Open Core** (default, offline) | CC0 packs: results, fixtures-when-published, intl scorers/shootouts; standings computed | Full cockpit minus Availability/Conditions; Outlook once fixtures exist |
| **Open Core + share-alike overlay** (opt-in) | + isolated OpenLigaDB Bundesliga/DFB display context | separate community fixture/result preview; ODbL notice shown; core facts unchanged |
| **User-local connector** (opt-in, user-fetched) | + football-data.org fixtures/standings, Open-Meteo weather, TheSportsDB extras | fresher fixtures; Conditions panel; attribution lines |
| **BYOK provider** (opt-in, user key+risk) | + API-Football etc. | user-private enrichment; never persisted into shareable artifacts |
| **AI enabled** (opt-in) | + local/BYOK narration over whitelisted evidence | Analyst Read cards |
| **Unavailable** | everything else (club xG, lineups, injuries, live) | honest "no lawful source" states; Unknown brief items |

---

## 12. AI evidence and safety contract (vNext)

### 12.1 Unchanged invariants (the trust boundary)

Off by default (`resolve_provider`, `ai_gateway.py:100-104`); deterministic numbers never modified (whitelist hard-reject → whole-narration rejection, `narration.py:263-264`); local-first (loopback-validated Ollama/llama.cpp) with BYOK cloud optional; keys header-only; betting lexicon rejected; prompt-injection fencing for untrusted context; one retry then `local_only`. All existing red-team tests keep running.

### 12.2 EvidenceBundle 0.2.0 (additive)

New top-level sections, all deterministic and source-attributed:

```
model_council[]     — per voice: family, probs, expected_goals?, abstained,
                      league_track_record {folds_n, mean_log_loss, rank}
                      → numbers namespaced mc_{family}_{key}
disagreement        — modal_split?, max_delta_p, js_divergence → mc_dis_*
form[]              — last-N series per team (results-derived) → fm_*
league_context      — standings position/points when computed → lc_*
brief               — facts vNext (Signal/Matchup/…/Unknown labels; Color still excluded)
data_quality[]      — capability warnings, staleness, abstentions (machine-generated)
analysis_kind       — forecast | preview | replay | review  (+ cutoffs)
```

`allowed_numbers` grows accordingly; referential-integrity validation (`evidence.py:637-667`) unchanged. Review bundles (post-match) additionally carry actual result + surprise numbers (`prob_assigned`, log loss) — already implemented for scored artifacts (`evidence.py:239-345`), reused.

### 12.3 Narration contract additions

Required output sections: `verified_facts`, `model_reading`, `inference` (explicitly labeled "inference from the above"), `uncertainty`, `missing_evidence`. The schema already separates claims/scenarios; add `claim.kind ∈ {fact, model_output, inference, uncertainty, missing}` and require ≥1 `missing` claim whenever `data_quality[]` is non-empty. "The available evidence does not support a deeper claim" is a first-class, acceptable full response (maps to current fail-closed behavior rather than fighting it). AI must never populate Availability/injury/lineup content — enforced by the whitelist (no such numbers exist to cite) plus a new lexicon check for injury/lineup nouns in `sanitize.py`'s spirit.

### 12.4 Contradiction explanation

When `disagreement.modal_split = true`, the prompt instructs the model to explain the mechanism difference (rating-based vs goals-based) using only `mc_*` numbers — this is inference, labeled as such, never a new probability.

---

## 13. API and schema proposal (contract 0.3.0, additive)

### 13.1 New read models

| Read model | Route | Identity/caching | Notes |
|---|---|---|---|
| **MatchAnalysis** | `GET /api/v1/matches/{id}/analysis` | computed; content-addressed cache key = (match_id, snapshot_sha, engine version) | The cockpit's spine. `analysis_kind`: `preview` (future fixture, latest snapshot, **ephemeral — never enters the ledger**), `replay` (completed match, as_of = kickoff−1s), each carrying `information_cutoff_utc`, per-voice outputs, council summary, score matrix (goal voice), abstentions |
| **ModelComparison** | embedded in MatchAnalysis + `GET /api/v1/lab/methodologies` | static + eval-derived | family tree, honest grouping, per-league fold records |
| **HistoricalReplay** | persisted variant of MatchAnalysis(replay): `hr_<sha[:20]>` artifacts | immutable via existing `_write_artifact` layer | Only persisted on user action ("Save replay snapshot", expert). Leakage tests: (a) replay of a sealable-at-the-time fixture must reproduce a seal's probs byte-for-byte given same pack+as_of (extends `test_phase3.py:82`), (b) `hr_*` files rejected by calibration/ledger loaders (schema `kind` field + loader test) |
| **CommentatorBrief** | `GET /api/v1/matches/{id}/brief` (supersedes `/notebook`, which remains as alias) | precomputed beside seals; on-demand otherwise (existing pattern) | taxonomy labels, `summary_fact_ids[]`, Unknown items, registry version |
| **PostMatchReview** | `GET /api/v1/matches/{id}/review` (completed only) | computed | actual result + surprise metrics vs replay + review facts; **UI-level and schema-level separation from pre-match panels** (distinct `kind`, distinct component, e2e test that review data never renders inside the pre-match column) |
| **LeagueOutlook** | `GET /api/v1/leagues/{slug}/outlook` | `lo_*` artifact per (league, snapshot) | §10 |
| **LeagueHub/Standings** | `GET /api/v1/leagues/{slug}?season=` | computed from index | standings + matchday list |
| **TeamOutlook** | — | — | **deferred** (§19 D6) |
| **DataCapability** | `GET /api/v1/capabilities` | static + snapshot-derived | per-competition tier map: which panels/columns are servable and why not (license/absence), powering every "Unavailable — no lawful source" state honestly |
| **EvidenceBundle 0.2.0** | existing narrative route, new builder | deterministic | §12 |

### 13.2 The three visible objects (labels, timestamps, provenance)

| Object | Chip label | Created | Key timestamps | Provenance | Eligible for forward track record? |
|---|---|---|---|---|---|
| Genuine pre-match forecast (`fa_*`) | **Forecast — sealed {date}** | before kickoff only (unchanged gates) | `sealed_at_utc`, `training_cutoff_utc`, kickoff | full (exists) | **Yes** (only this) |
| Historical replay (`hr_*` / ephemeral replay) | **Replay — reconstructed with pre-kickoff data** | any time after the fact | `as_of = kickoff−1s`, `computed_at_utc`, snapshot sha | pack hashes + engine version | **Never** (loader-enforced) |
| Post-match review | **Review — uses the final result** | after result known | `scored/actual`, `computed_at_utc` | derives from replay + result | n/a |
| Preview (subtype of MatchAnalysis) | **Preview — computed now, will move with data** | pre-kickoff, ephemeral | `information_cutoff_utc = now(snapshot)` | snapshot sha | No — "Track this prediction" (seal) is the promotion path |

This is the resolution of the display-vs-leakage conflict: the invariant that survives is *information-cutoff discipline plus truthful object identity*, not *refusal to render numbers*.

### 13.3 Contract/versioning mechanics

`SCHEMA_VERSION → 0.3.0`, `ACCEPTED_SCHEMA_VERSIONS = ["0.2.0","0.3.0"]` (client, `contract.ts:15`) — additive only; `forecast_artifact.schema.json` untouched; new schemas `match_analysis.schema.json`, `commentator_brief.schema.json` (facts.schema evolves additively: new labels join the enum), `league_outlook.schema.json`, `capabilities.schema.json`. Mock-mode fixtures updated in `ui/src/mocks/` so the no-backend build demos the cockpit honestly (labeled sample data, opt-in).

---

## 14. Migration strategy

- **Artifacts**: `fa_*` files, audit.jsonl, hashes — byte-untouched. Loaders unchanged. New object types live beside them with distinct prefixes and a `kind` discriminator; ledger/calibration loaders gain an explicit prefix filter + test so `hr_`/`lo_` can never pollute the forward record.
- **Ledger/Evaluation**: zero data migration — `PredictionLedger` and `EvaluationSummary` components relocate under `/lab/*` with hash-route redirects from `#/ledger`, `#/eval` (kept ≥2 releases; deep links in old exports keep working).
- **Routes**: `#/forecast/:id` survives verbatim. `#/match/:id` upgrades in place from "directory entry" to "cockpit" — additive panels, no removed information. `#/matches` redirects home.
- **Sample data**: silent fallback (`main.py:74-96`) becomes explicit — first-run shows real (empty-ledger-tolerant) Games home from the real index; synthetic forecast samples only behind a labeled "Explore with demo forecasts" action. The existing sample banner logic reverses polarity: opt-in instead of opt-out.
- **Eval/notebook precompute**: existing `eval_summary*.json` and precomputed notebooks serve unchanged; brief route aliases notebook route during transition.
- **Contract**: 0.3.0 additive; desktop sidecar and UI ship together (existing release discipline), so a version skew window is not a real deployment mode; mock fixtures updated in the same PR as contract bumps (existing guard tests enforce).

---

## 15. Phased roadmap

Phases are sequential gates; each ends in a demonstrably useful flow. "Forbidden claims" bind UI copy, README, and release notes.

### Phase 0 — Wire the refresh (1 short cycle; do first, independent of the pivot)
- **User value**: the app stops being frozen on July 11; WC2026 semis/final become sealable — first live seals ever.
- **Scope**: production trigger for `merge_refreshed_index` + `repoint_to_refreshed` (v0.2.5 slices 3–6): consent-first refresh action in Settings/Games, staleness stamp in UI, sidecar-safe execution.
- **Allowed claims**: "internationals refresh on demand". **Forbidden**: any club-fixture freshness claim.
- **Files**: `server/golavo_server/{refresh,matches,runtime,fixtures}.py`, `main.py` (one POST route), Settings UI, `Layout` footer stamp.
- **Tests**: existing `test_refresh*.py` + a route test + an e2e stamp check. **Gate**: a real seal created on a live upcoming international in a manual QA run.
- **Non-goals**: club data, cockpit. **Rollback**: route removal; refresh dir is already all-or-nothing (`repoint_to_refreshed`).

### Phase 1 — Games home + Match Cockpit (read-only core) **← the MVP spine**
- **User value**: open Golavo → browse/search 75k matches → open any match → council (replay for past, preview for eligible upcoming internationals) + brief + score scenarios. The empty-ledger empty-home problem dies here.
- **Scope**: `MatchAnalysis` endpoint (preview/replay, ephemeral, cached); council read model over existing `fit_model`; cockpit UI (panels 1–6, 8–9 of §7); Games home (recent + search + upcoming-internationals rail); Model Lab relocation + redirects; router param/query upgrade; object-type chips everywhere; sample-fallback polarity flip; brief dedupe (`summary_fact_ids`).
- **Allowed claims**: "analysis for any indexed match, reconstructed with pre-kickoff information". **Forbidden**: "forecasted at the time" for replays; any club upcoming coverage; consensus-as-ensemble language.
- **Files**: new `core/golavo_core/analysis.py` (pure, reuses candidates/score_matrix), `server/.../analysis.py` + route, `ui` (Games, Cockpit, Lab shell, router), contracts 0.3.0, mocks.
- **Dependencies**: none beyond Phase 0 (works fully offline on the frozen index).
- **Tests**: replay≡seal byte-equivalence property test; ledger-pollution rejection; cutoff guards (reuse `training_rows` fail-closed); insight-dedupe DOM test; e2e overflow/axe extended to new routes; contract guards.
- **Gate**: J1–J5 + J9 + J11 pass end-to-end offline; time-to-first-insight <10s from cold launch in manual QA.
- **Non-goals**: fixtures ingest, standings, new fact templates, AI changes. **Rollback**: new routes/views are additive; old routes still render via redirect shims.

### Phase 2 — Fixtures ingest + club previews + Brief vNext
- **User value**: "Upcoming" is real for club leagues; previews for any covered fixture; a visibly smarter brief (new taxonomy + ~10 new results-derived templates + Unknown items); Markdown export.
- **Scope**: fixtures adapter(s) per §11 verdicts (openfootball season files as bundled-open primary; capability-gated alternatives as user-fetched adapters); index schema keeps `is_complete=false` future rows; preview eligibility for club fixtures (min-history rule reused); Brief taxonomy + registry bump; export.
- **Allowed claims**: "upcoming fixtures where an open source publishes them" (+ freshness stamp). **Forbidden**: completeness ("all fixtures"), availability/injury anything.
- **Dependencies**: Phase 1 read models; §11 source decisions.
- **Tests**: ingest determinism + license gate (extend `test_license_gate_is_fail_closed`); registry pre-registration tests; template min-sample tests; export snapshot test.
- **Gate**: J2 completes for a real 2026-27 club fixture; brief renders ≥4 non-duplicated slots on 95% of a 500-match sample.
- **Non-goals**: standings/outlook, ensemble. **Rollback**: fixtures feed is a separate pack — droppable without touching results history.

### Phase 3 — Leagues hub + standings
- **User value**: league browsing (J8) with deterministic standings for ~70 league-seasons.
- **Scope**: standings builder (tiebreak rules as data), league hub UI, DataCapability endpoint powering honest column states.
- **Tests**: standings golden tests vs known final tables (5 leagues × 3 seasons). **Gate**: computed final tables byte-match published history for all goldens.
- **Non-goals**: projections. **Rollback**: standalone view.

### Phase 4 — League Outlook (season simulator)
- Per §10 contract, including the backtest acceptance gate before any user-facing probability ships. **Forbidden claims**: interval overconfidence (v1 must carry the "match randomness only" caveat), any xG label.

### Phase 5 — AI vNext + candidates for Teams/watchlist
- EvidenceBundle 0.2.0, review narration, contradiction explanation; Teams decision re-evaluated with usage data (D6); possible third council voice via the §8.7 gauntlet.

### MVP cut (Deliverable 16)

**MVP = Phase 0 + Phase 1.** Smallest release that proves the thesis: Games-first home, cockpit for any indexed match with honest council + brief + scenarios, seals reframed as expert action, lab consolidated, everything offline-capable. Explicitly **excluded** from MVP: club fixtures ingest, standings, League Outlook, Teams, new fact templates, AI bundle changes, weather/rest enrichment, watchlists. (The brief's warning about over-stuffing the MVP is accepted verbatim.)

---

## 17. Success metrics

| Metric | Definition | Target (MVP) |
|---|---|---|
| Time to first useful insight | cold launch → first cockpit with ≥1 council row + ≥1 brief fact | <10s p50, <30s p95 (local) |
| Match-analysis completion | sessions opening a cockpit that scroll ≥3 panels or expand council/brief | >60% |
| Deterministic coverage | % of opened matches rendering ≥1 non-abstained voice + ≥3 brief facts | >90% (index-wide sample) |
| Disagreement comprehension | in-app microsurvey / QA protocol: user can state which voice leans where | qualitative gate pre-release |
| Repeat use | ≥2 sessions in 14 days (local, no telemetry — measured only via opt-in QA cohort; **no analytics shipped**) | directional |
| Missing-data honesty | every unavailable panel shows a reasoned state; zero fabricated fields | 100% (e2e asserted) |
| Leakage/provenance failures | replay≡seal property violations, ledger pollution, cutoff breaches | **0, CI-enforced** |

(No telemetry exists or ships — "no telemetry" is a README promise. Usage metrics are QA-cohort and self-report only.)

---

## 18. Risk register

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | Fixtures source gap: openfootball 2026-27 files late/stale → "Upcoming" thin for clubs | High | High | Phase-2 multi-source adapter design; internationals rail carries MVP; capability-honest empty states; §11 fallback adapters |
| R2 | Replay misread as "we predicted this" → trust damage | Medium | High | mandatory object chips, distinct visual identity, replay banner copy, e2e test that no replay renders without its label |
| R3 | False plurality regression (3 Poisson flavors read as 3 votes) | Medium | High | council seat model in the contract itself (voices vs flavors), copy review, methods page |
| R4 | Descriptive "leading view" quietly becomes a de-facto ensemble in users' heads | Medium | Medium | wording ("led recent backtests"), always-visible second voice, §8.5 gate for any real ensemble |
| R5 | Outlook intervals overconfident (point-estimate strengths) | High (statistical certainty) | Medium | explicit caveat in v1, bootstrap in v2, backtest coverage gate before launch |
| R6 | License drift (football-data.org ToS, StatsBomb terms change) | Medium | High | §11 matrix pinned with fetch dates; capability tiers make removal non-breaking; CI license-string gate exists (`test_license_gate_is_fail_closed`) |
| R7 | On-demand analysis latency on old hardware (5 fits per cockpit open) | Medium | Medium | content-addressed cache by (match, snapshot, engine); precompute for recent/upcoming; fit cost is small (single league slice) |
| R8 | Facts/engine isolation eroded by the disagreement card | Low | High | card built in cockpit read-model layer; AST isolation test keeps failing any facts→models import |
| R9 | Router rewrite regressions (deep links, e2e) | Low | Medium | keep hash routing, shim redirects, extend existing 30-assertion e2e gate |
| R10 | Migration confusion (Ledger disappears from nav) | Medium | Low | redirects + one-release "moved to Model Lab" toast; docs update |
| R11 | AI narrates Availability/lineups it cannot know | Low (whitelist) | High | no such numbers exist to cite; add lexicon check; red-team case added |
| R12 | Scope creep folding Phases 2–4 into MVP | High | High | this document's MVP cut + acceptance gates as the contract |

---

## 19. Open decisions — provisional recommendations

| # | Decision | Recommendation |
|---|---|---|
| D1 | Preview persistence | **Ephemeral + content-addressed cache only.** Ledger entry requires explicit seal ("Track this prediction"). No auto-sealing — an auto-sealed ledger would flood the track record with unowned predictions. |
| D2 | Expert action naming | Casual verb **"Track this prediction"**; expert/detail language **"Seal auditable snapshot"**. "Preserve pre-match analysis" rejected (vague). |
| D3 | Climatology rendering | Reference band behind bars + line in methods page; never a council row. |
| D4 | Which Poisson flavor holds the goal-model seat | **dixon_coles** (motivated correction, competitive folds), flavors disclosed in expert sub-rows; revisit only via §8.5-style pre-registered gate. |
| D5 | Ensemble | Defer; descriptive consensus in v1; gate per §8.5. |
| D6 | Teams in v1 | **No.** Compensations: saved-search chips + league hub rosters. Revisit at Phase 5 with QA-cohort evidence. |
| D7 | Router | Extend the hand-rolled hash router (params + query); do **not** adopt react-router (dependency austerity is a stated project trait). |
| D8 | AI text in exports | Exclude from v1 exports; deterministic content only. Revisit when narration carries `claim.kind` labels. |
| D9 | Replay artifacts (`hr_*`) persisted by default? | No — compute+cache; persist only on explicit expert save. Keeps the artifact store meaningful. |
| D10 | Sample data | Flip to opt-in demo mode in Phase 1 (real index renders a real home even with an empty ledger, so samples are no longer needed for first-run). |
| D11 | Women's football coverage | Acknowledge as absent (zero rows); add only with a lawful source (martj42 has a separate women's results dataset — evaluate in Phase 2 under the same CC0 pipeline). |
| D12 | WC2026 moment | Ship Phase 0 immediately, before the final (~July 19), to mint the first genuine forward seals on a world-stage fixture. |

---

## 20. Recommended implementation workstreams

Two non-overlapping lanes after this plan is accepted (no implementation prompts here, per the brief):

**Lane A — Backend / data / contracts** (owns: `core/`, `server/`, `packs/`, `docs/contracts/`)
- A0: refresh wiring (Phase 0)
- A1: `analysis.py` core + MatchAnalysis/Brief/Capability endpoints + contract 0.3.0 + property tests (replay≡seal, ledger pollution, cutoff)
- A2: fixtures adapters + license gates + registry vNext templates
- A3: standings builder; A4: simulator + `lo_*` artifacts + backtest harness
- A5: EvidenceBundle 0.2.0 + gateway extensions

**Lane B — UI / product** (owns: `ui/`)
- B1: router upgrade + redirects + Lab relocation (can start against mocked 0.3.0 fixtures the moment contracts merge)
- B2: Games home + cockpit panels 1–6, 8–9 + object chips + sample-polarity flip
- B3: Brief vNext presentation + export; B4: league hub + standings; B5: Outlook table
- Continuous: e2e overflow/axe extension per new route; copy review against forbidden-claims lists

Interface discipline: lanes meet **only** at `docs/contracts/*.json` + mock fixtures; contract PRs precede consuming PRs (the existing contract-guard tests already enforce runtime conformance).

---

*End of plan. Section 11 (data/license matrix) and section 16 are inline above; section numbering follows the brief's deliverables 1–20 with §16 folded into §15 (MVP cut) where the roadmap lives.*
