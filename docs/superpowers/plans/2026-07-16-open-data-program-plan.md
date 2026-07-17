# Open-Data Program Implementation Plan (10 phases, chronological)

> **Progress — updated 2026-07-17.**
> **Phase 1 (The Fixture Key): SHIPPED** on main (`52a4c08`; parser `f7d7d7f`, unlock
> `52e8edc`, docs `f3e563a`, review fixes `47e6a39`). The season outlook runs for all
> five leagues; full core+server suite **847 passed**; all six governance validators,
> `ruff check .`, the byte-identical index rebuild and the docs-site build are green.
> Deliberately **not** done in Phase 1, and not claimed anywhere: no runtime refresh
> adapter reads the five .txt repos (results move only when the packs are rebuilt —
> registry entries therefore ship with no `refresh` block), no postponement pick
> re-bind, no Playwright/axe pass, no installed-app QA. Those remain open Phase 1 tasks.
> **Phases 2–10: not started.** Phase 2's data (goalscorers/shootouts) is already
> bundled and current through 2026-07-15, so it needs no new source work.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan phase-by-phase. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Scope note (writing-plans scope check):** this program covers ten independent
> subsystems. Per the skill's rule, each phase below is an independently shippable
> plan skeleton — file map, interfaces, right-sized tasks, gates — and the phase
> being started next gets expanded into a full bite-sized red-green plan in its own
> session before any code is written. Phase order is the contract; nothing may be
> reordered without re-checking the dependency notes.

**Goal:** ship the ten roadmap features (roadmap items 1, 3, 4, 7, 8, 9, 10, 11, 12, 13 of `docs/handoff/open-data-feature-roadmap-2026-07.md`) in dependency-and-deadline order, every one powered exclusively by verified free / open-license / free-tier data.

**Architecture:** every phase follows the house pattern — pinned hash-manifested source pack (or per-user consent-gated lane for non-redistributable data), registry entry with license class, deterministic core computation behind the leak-safe view, typed contract, honest blocked/unknown states, display-only until a pre-registered experiment says otherwise.

**Tech stack:** existing only — Python 3.12 core/FastAPI server/PyInstaller sidecar, React+TS UI, Tauri 2 shell, pandas/pyarrow, pytest/vitest/Playwright. No new runtime dependencies anywhere in this plan.

## Fact-check ledger (all 10 verified free & implementable, 2026-07-16/17)

| # | Phase | Data | License / tier | Verified evidence (primary) |
|---|---|---|---|---|
| P1 | Fixture Key | openfootball england/deutschland/espana/italy/europe 2026-27 .txt | CC0-1.0 | raw files fetched; 380/306/380/380/306 fixtures counted; LICENSE.md CC0; weekly auto-update bot commits Jul 2026 |
| P2 | Golden Boot | martj42 goalscorers.csv + shootouts.csv | CC0-1.0 | already bundled + hash-pinned in `packs/martj42-internationals/manifest.json`; upstream commits Jul 10–15 2026 |
| P3 | Golavo Ratings | none new (CC0 core results) | n/a | no lawful FIFA-ranking source exists (verified); own Elo is clean-room from CC0 data |
| P4 | Club Seals | none new (P1 packs) | CC0-1.0 | same P1 evidence; kickoff times present in .txt but **no timezone token** — day-precision first, tz upgrade later |
| P5 | Matchday Sky | Open-Meteo forecast API | output CC-BY 4.0; free tier non-commercial, keyless, <10k calls/day | terms + live call verified; 16-day horizon; all 5 hourly vars returned; **no issued-at in response — client records fetch time** |
| P6 | Reference Desk | Wikidata (WDQS build-time) | CC0 | licensing page verbatim; P286/P54+P580/P582 live-queried (Spain = **Q42267**, not Q676899); UA header mandatory, 5 parallel queries/IP |
| P7 | Long Memory | footballcsv england/deutschland/espana | CC0-1.0 | LICENSE.md CC0 verified; spans verified: **eng 1992-93→2020-21, deu 1963-64→2020-21, esp 2012-13→2020-21**; header is `Round,Date,Team 1,FT,Team 2`; en-dash scores in 2020-21 |
| P8 | Anatomy of a Match | Pappalardo/Wyscout figshare | CC-BY 4.0 | figshare API license field verified; events.zip 77.3 MB via `ndownloader.figshare.com/files/14464685` (follow the 10-second presigned redirect immediately) |
| P9 | Ten Matches, Tracked | SkillCorner opendata | MIT | license verified; new layout `data/matches/{id}/` (4 files); tracking `.jsonl` behind **Git LFS** (use `media.githubusercontent.com`, ~90 MB/match) — plan precomputes, never ships raw |
| P10 | Event Lab | StatsBomb open-data | proprietary free agreement: no redistribution, non-commercial, per-user download OK | LICENSE.pdf read in full; per-file raw fetch verified; Euro 2024 = 55/282, Women's Euro 2025 = 53/315; events ≈ 3.4 MB/match |

## Global constraints (apply to every phase)

- Match-index rows remain **CC0-only** (`match_index.py _CLEARED_LICENSES`); everything non-CC0 lives in its declared class store (enrichment / odbl-pack / by-sa-pack / research-pack / per-user lane) and never joins the index.
- Every new source gets a `data/sources/registry.json` entry (license, class, pin, attribution, recheck-by) **before** adapter code; `scripts/validate_sources.py`, `validate_license_isolation.py`, and THIRD_PARTY_NOTICES regeneration must stay green.
- Nothing becomes a model input in this program. All new data is display/context/facts; the leak-safe view (`ingest/snapshot.py leak_safe_training_view`) is untouched except where a phase explicitly says otherwise, and `assert_no_future_rows` invariants must hold in every new test.
- Additive schema changes only; bump contract versions, never mutate `ACCEPTED_SCHEMA_VERSIONS` semantics.
- Attribution obligations shipped in-pack + NOTICE: GeoNames-style CC-BY lines for Open-Meteo ("Weather data by Open-Meteo.com" link next to displayed values), Pappalardo citation, SkillCorner credit, MIT notice.
- No betting framing anywhere; "Unknown / no lawful source" is a rendered state, never a gap-fill.
- TDD per task; commit per green step; worktree runs need the primary-checkout PYTHONPATH guard (known gotcha) and never `pytest | tail` (exit-code trap).

---

## Phase 1 — "The Fixture Key" · 2026-27 season unlock

**Window:** now → **Aug 14** (hard-ish: La Liga opens Aug 16, EPL Aug 21). Roadmap #1. Depends on: nothing. Unblocks: P4.

**Files:**
- Create: `core/golavo_core/ingest/domestictxt.py`, `scripts/build_domestic_fixtures_packs.py`, `core/tests/test_domestictxt.py`, `core/tests/test_season_unlock.py`, `packs/openfootball-{eng-pl,esp-ll,deu-bl,ita-sa,fra-l1}-2026-27/` (pinned .txt + manifest v2)
- Modify: `data/sources/registry.json` (three repo entries: england, deutschland, espana/italy, europe), `packs/snapshots.json`, `core/golavo_core/ingest/match_index.py` (fold fixture rows, `is_complete=false`, `kickoff_precision="day"`, keep local time string in a new nullable `kickoff_local_hhmm` column), `core/golavo_core/competitions.py:112-117` (derive `simulation` capability from `certify_schedule` result instead of the static literal), `server/golavo_server/refresh_sources.py` (`_CONFIG` + `APPROVED_SOURCE_IDS` for the three repos, path allowlists pinned to `2026-27/*.txt`), `ui/src/views/Leagues.tsx` (unblocked copy), `ui/src/lib/contract.ts`
- Test: `core/tests/test_domestictxt.py`, `core/tests/test_season_outlook.py` (extend), `server/tests/test_refresh_*.py` (extend), `core/tests/test_leak_safe_view.py` (extend: fixture rows never train)

**Interfaces:**
- Produces: `parse_domestic_txt(text: str, competition_id: str, season: str) -> list[TxtFixture]` where `TxtFixture` = frozen dataclass (`date: date, kickoff_local_hhmm: str | None, home: str, away: str, ft: tuple[int,int] | None, ht: tuple[int,int] | None, matchday: int`); `build_domestic_fixture_rows(...) -> pd.DataFrame` matching `INDEX_COLUMNS`.
- Grammar locked by fact-check (write golden tests from these exact bytes): header `= <league> 2026/27`; `#`-comment metadata; matchday marker `▪ Matchday N` (U+25AA); date lines 2-space indent, year only on the matchday's first date (year-carry rule); kickoff `HH:MM` 4-space indent shared downward within a time group (omitted time = previous time); teams have **no** country suffixes; unplayed = no score suffix; played = `4-2 (1-0)` with HT optional; **CRLF and LF both occur across seasons**; alignment is not fixed-width (regex, not columns).

**Tasks (right-sized; each ends independently testable):**
- [ ] 1. Parser: golden-file tests from verified 2026-27 EPL + Bundesliga excerpts (year-carry, time-group carry, U+25AA, CRLF, long-name misalignment, played-row `FT (HT)`) → implement `domestictxt.py` → green.
- [ ] 2. Pack builder: pin the five files at current upstream commits, manifest v2 `license: CC0-1.0, license_class: core`; registry entries; `validate_sources.py` green.
- [ ] 3. Index fold: fixture rows join the five league packs with stable ids; `certify_schedule` returns `complete_fixture_list=true` for all five (test asserts the certificate on the real packs); leak-test: fixture rows (`is_complete=false`) never appear in any `training_rows` output.
- [ ] 4. Capability wiring: replace the static `blocked` literal with certificate-derived status; blocked reason preserved verbatim for leagues whose certificate fails; `GET /api/v1/capabilities` reflects it; season outlook + schedule difficulty go live behind the same flip.
- [ ] 5. Refresh: `_CONFIG` entries (same two allowed hosts, commit-pinned); end-to-end recorded-fixture refresh test — a .txt updated with a played score settles the corresponding pick.
- [ ] 6. Postponement hardening: when a refreshed generation moves a fixture's date, re-bind picks by `(competition, season, matchday, home_norm, away_norm)` and mark `rescheduled` instead of voiding; test with a synthetic date move.
- [ ] 7. UI: Leagues copy, Games-home upcoming window now showing club fixtures, Playwright + axe on the unblocked outlook page; installed-app QA macOS + Windows.

**Gates:** byte-identical index rebuild in CI; bundle budget (+≤1 MB — five .txt files are ~40 KB each); no-leak invariant; all existing 985+ tests green.
**Rollback:** revert packs + index rebuild; capability derivation keeps honest `blocked` if certificate fails, so partial upstream data can never fake an unlock.

---

## Phase 2 — "Golden Boot" · scorers & shootouts surfaces

**Window:** Aug 3 → Aug 21 (parallel with P1 — different files). Roadmap #3. Depends on: nothing (data already bundled).

**Files:**
- Create: `core/golavo_core/facts/scorers.py`, `core/tests/test_scorer_facts.py`, `ui/src/components/ScorersPanel.tsx`
- Modify: `core/golavo_core/facts/registry.py` (new families + `REGISTRY_VERSION` bump + `DATASET_BY_TEMPLATE`), `server/golavo_server/main.py` (new `GET /api/v1/competitions/{id}/scorers`), `server/golavo_server/matches.py` or a small `scorers.py` reader over `data/index/goalscorers.parquet`/`shootouts.parquet`, `ui/src/views/Leagues.tsx` (internationals section), `ui/src/lib/contract.ts`
- Test: `core/tests/test_scorer_facts.py`, `server/tests/test_scorers_api.py` (new)

**Interfaces:**
- Produces: `top_scorers(competition_id, as_of, min_goals) -> list[ScorerRow]` (leak-safe: rows ≤ as_of only); 4 new fact families (proposed: `tournament_top_scorer_form`, `scorer_minute_signature`, `shootout_keeper_curse` [coincidence], `late_goal_specialist`) each with `min_sample`, `staleness_days`, dataset citation.
- Constraint: side tables exist **only** for martj42 internationals (`facts/packs.py`) — every surface renders "internationals only" scope honestly; family additions widen `family_size()` (multiple-comparison budget) — the registry bump is a reviewed change with updated suppression tests.

**Tasks:**
- [ ] 1. Reader + leak-safety tests over goalscorers/shootouts parquet (as_of cutoff respected, name canonicalization via existing alias map).
- [ ] 2. Fact families red-green (template fns in `facts/scorers.py`; registry validation, cap and suppression audits green; AI whitelist round-trip test: new `nb_*` numbers cite datasets).
- [ ] 3. Route + contract + `ScorersPanel` (era/scope labels; empty states); vitest + Playwright.

**Gates:** `_validate_registry()` green; red-team suite still green (player names flow through the untrusted-text sanitizer).

---

## Phase 3 — "Golavo Ratings" · in-house national-team Elo

**Window:** Aug 24 → Sep 11. Roadmap #4. Depends on: nothing (P2 patterns help).

**Files:**
- Create: `core/golavo_core/ratings.py`, `core/tests/test_ratings.py`, `ui/src/views/Ratings.tsx`
- Modify: `core/golavo_core/models/candidates.py` (expose the Elo update constants — do **not** change fit behavior), `server/golavo_server/main.py` (`GET /api/v1/ratings/international?as_of=`), `server/golavo_server/` new thin `ratings.py` using `SnapshotReader` (owns cache key + repoint retry per v0.15.0 architecture), `ui/src/App.tsx` route, `ui/src/lib/contract.ts`, Model Lab hub link
- Test: `core/tests/test_ratings.py`, `core/tests/test_properties.py` (extend), `server/tests/test_ratings_api.py`

**Interfaces:**
- Produces: `elo_trajectory(rows: pd.DataFrame, as_of: datetime) -> RatingsTable` — replay of the existing Elo update over completed rows ≤ as_of, emitting per-team `(rating, n_matches, last_match_date)` plus monthly checkpoint series (reuse `_strength_trends` checkpoint-loop shape from `analytics.py`, Elo instead of Poisson).
- Honesty spec: label "Golavo Ratings — model-estimated from results; not the FIFA ranking"; property test: appending future rows never changes the table at an earlier `as_of` (byte-identical); confederation coverage note rendered (friendlies density varies).

**Tasks:**
- [ ] 1. Trajectory engine red-green (determinism, as_of property, K/home-adv constants shared with `EloOrdinalLogitModel`).
- [ ] 2. Route via `SnapshotReader` (per-minute as_of cache like competition analytics) + contract.
- [ ] 3. Ratings page (table + per-team sparkline from checkpoints, uncertainty note, provenance chip); Playwright + axe.

---

## Phase 4 — "Club Seals" · put club predictions on the record

**Window:** Sep 14 → Oct 2 (after P1 has soaked through ≥3 real matchweeks). Roadmap #9. Depends on: **P1**.

**Files:**
- Modify: `server/golavo_server/seal.py` (replace `_SOURCE_PACKS: dict[str,str]` with `resolve_training_pack(source_id, competition_id) -> PackRef | None`; eligibility drops the `source_kind=="international"` short-circuit in favor of "resolves to exactly one CC0 pack"), `server/golavo_server/settlement.py` (club settlement from refreshed openfootball results, fail-closed on cross-source disagreement where a second source exists), seal copy strings, `ui/src/components/SealingGuide.tsx`
- Test: `server/tests/test_seal_api.py` (extend: club window freeze-time tests), `core/tests/test_leak_safe_view.py` (club fixture trains only on own competition — the scoping already exists; assert it through the seal path)

**Interfaces:**
- Consumes: P1 per-league 2026-27 packs (one pack per competition — this is what makes single-pack resolution possible; the old blocker was five leagues behind one `source_id`).
- Honesty spec: `kickoff_precision="day"` rows keep the existing midnight-UTC-close window (already implemented and tested — conservative, honest); a **later** optional task upgrades precision by converting `.txt` local `HH:MM` + GeoNames venue tz → `kickoff_utc` with `kickoff_precision="exact"` — shipped only with per-row provenance (`tz_source`) and freeze-time tests, since the .txt carries **no timezone token** (fact-checked).

**Tasks:**
- [ ] 1. Pack-resolution refactor red-green (internationals behavior byte-identical; club rows resolve per-competition; ambiguous → ineligible with typed reason).
- [ ] 2. Club eligibility + seal windows (day-precision) + abstention floor unchanged; ledger/audit tests.
- [ ] 3. Settlement from refresh + voiding rules for postponements (reuse P1 task 6 identity re-bind).
- [ ] 4. (Optional, gated) exact-kickoff upgrade via venue tz; separate commit, separate test file.

---

## Phase 5 — "Matchday Sky" · pre-kickoff weather (Open-Meteo)

**Window:** Oct 5 → Oct 16. Roadmap #7. Depends on: nothing technically; after P4 for schedule room.

**Files:**
- Create: `server/golavo_server/weather_source.py` (the only module allowed to call `api.open-meteo.com`; GET-only; host allowlist; no key), `server/golavo_server/weather_store.py` (per-user store under user-data `weather/`, one JSON per (match_id, fetched_at)), `server/tests/test_weather_lane.py`
- Modify: `docs/contracts/conditions_snapshot.schema.json` (**additive** `weather` variant: `status:"forecast"` object `{provider:"open-meteo", fetched_at_utc, kickoff_utc, temperature_2m_c, precipitation_mm, precipitation_probability_pct, wind_speed_10m_kmh, weather_code, attribution_url, model_input:false}` alongside the existing const-locked `blocked` variant — the blocked shape is verified to be all-const, so this is a new branch, not a mutation), `server/golavo_server/conditions.py:508-517`, `server/golavo_server/context_registry.py` (weather capability `partial` with reason), `data/sources/registry.json` (open-meteo entry, class `per-user-context`, terms + recheck-by), `ui/src/components/ConditionsSnapshot.tsx` (weather card + mandatory visible "Weather data by Open-Meteo.com" link), Settings consent toggle
- Test: `server/tests/test_weather_lane.py`, `server/tests/test_conditions_api.py` (extend), UI vitest

**Interfaces & honesty spec (locked by fact-check):**
- The API returns **no model-issue timestamp** (`generationtime_ms` is compute duration) → `issued_at := fetched_at_utc` recorded client-side; the display gate is `fetched_at_utc < kickoff_utc`, enforced in `conditions.py`, tested with frozen time. Completed matches never show fetched-after-kickoff data; matches with no pre-kickoff capture render the existing blocked state with a new reason code `no_pre_kickoff_capture`.
- Fetch triggers: explicit user action on a match page + the existing followed-match while-open refresh tick; ≤16-day horizon; per-user keyless (each user spends their own free-tier budget); consent default **off**; fail-closed on any network/schema error.

**Tasks:**
- [ ] 1. Schema branch + conditions renderer red-green (blocked variant byte-identical for old data).
- [ ] 2. Fetch lane (allowlist, size caps, typed errors, recorded-fixture tests — no live network in CI).
- [ ] 3. Store + pre-kickoff gate + follows integration; freeze-time tests.
- [ ] 4. UI card + attribution link + consent toggle; Playwright + axe; installed-app QA.

---

## Phase 6 — "The Reference Desk" · Wikidata manager/venue facts

**Window:** Oct 19 → Oct 30. Roadmap #10. Depends on: nothing.

**Files:**
- Create: `scripts/build_wikidata_reference_pack.py` (build-time WDQS SPARQL, mandatory descriptive User-Agent, ≤5 parallel, retry-on-429; emits reviewed, revision-pinned extract), `core/golavo_core/facts/reference.py`, `core/tests/test_reference_facts.py`
- Modify: `packs/wikidata-context-*/` → new dated pack with property allowlist extended to **P286 (head coach)** and **P54 (member of sports team)** with P580/P582 qualifiers (P1083 capacity already allowlisted), `data/sources/registry.json` (bump pin), `core/golavo_core/facts/registry.py` (2–3 context families, e.g. `manager_tenure_context`, `venue_era_context`), Match Cockpit notebook surfaces automatically
- Test: `core/tests/test_reference_facts.py` + extract-builder unit tests with recorded SPARQL fixtures

**Honesty spec (locked by fact-check):**
- QIDs are hand-reviewed into the allowlist (the check that caught Q676899 = **Italy**, Spain = **Q42267**, is the process — never trust label search alone).
- Tolerate unknown-value snaks (Italy's current P286 is one); sanity-filter date qualifiers (garbage like year 112020 observed live); every fact carries `as_of` = pack revision date and renders "as recorded in Wikidata on <date>", never "current"; no current-squad claims (P54 end-dates verified laggy).

**Tasks:**
- [ ] 1. Extract builder red-green on recorded fixtures (snak tolerance, date filter, revision pinning).
- [ ] 2. Reviewed pack build + registry bump + license isolation green (CC0 folds into enrichment tier).
- [ ] 3. Fact families + notebook surfacing + sanitizer round-trip (names are untrusted text).

---

## Phase 7 — "The Long Memory" · club history via footballcsv

**Window:** Nov 2 → Nov 13. Roadmap #11. Depends on: nothing.

**Scope correction from fact-check (this is the honest pitch):** adds **Bundesliga 1963-64→2009-10** and **England 1992-93→2009-10** (espana adds ~nothing: 2012-13+ already overlaps bundled data). Not 19th-century history; not current seasons (repo dormant since 2020-21 — fine, this phase is deliberately historical).

**Files:**
- Create: `core/golavo_core/ingest/footballcsv.py`, `scripts/build_footballcsv_history_packs.py`, `core/tests/test_footballcsv.py`, `packs/footballcsv-{eng,deu}-history/`
- Modify: `data/sources/registry.json`, `packs/snapshots.json`, `core/golavo_core/competitions.py` (historical-era coverage notes), Leagues history sections (all-time tables computed from the index, era-badged), `ui/src/views/Leagues.tsx`
- Test: `core/tests/test_footballcsv.py` (golden seasons), `core/tests/test_match_index.py` (extend)

**Parser spec (locked by fact-check):** header `Round,Date,Team 1,FT,Team 2`; date `Sat Aug 17 2013`; score separator is ASCII hyphen in older files and **EN DASH (U+2013) in 2020-21**; team-name style drifts (`Norwich City FC` vs `Fulham`) → canonicalization through the existing alias machinery with a reviewed mapping table, **no fuzzy auto-merge**; rows are CC0 → they may fold into the core index as search/backtest/history rows (`seal`-ineligible, era-badged).

**Tasks:**
- [ ] 1. Parser red-green (both separators, both name styles, golden 1963-64 + 2013-14 + 2020-21 seasons).
- [ ] 2. Packs + registry + identity-mapping review (test: zero unmapped team names per bundled season; fail the build otherwise).
- [ ] 3. Index fold + all-time-table computation + era-badged UI sections; byte-identical rebuild gate.

---

## Phase 8 — "Anatomy of a Match" · per-match Wyscout artifacts + the pack downloader

**Window:** Nov 16 → Dec 4. Roadmap #13. Depends on: nothing. **Builds the generic opt-in pack lane that P9 and P10 reuse.**

**Files:**
- Create: `scripts/build_wyscout_match_artifacts.py` (maintainer-side: download `events.zip` 77 MB from the figshare ndownloader URL — follow the presigned redirect immediately, it expires in ~10 s; compute per-match artifacts for all 1,941 matches), `server/golavo_server/packs_lane.py` + `packs_state.py` (**generic** per-user pack download lane: URL+sha256 from the registry, staged generations, activate/rollback/delete — generalizes the proven OpenLigaDB jobs/state pattern; job lane per v0.15.0 `job.Lane`), `core/golavo_core/research/match_artifacts.py`, `docs/contracts/match_research_artifact.schema.json`, `server/tests/test_packs_lane.py`, `core/tests/test_match_artifacts.py`
- Modify: `data/sources/registry.json` (pack download descriptor), Settings pack manager section (`ui/src/views/Settings.tsx`), `ui/src/components/MatchResearch.tsx` (per-match panes: pass network nodes/edges ≥3 passes at median touch locations, shot map with locations/outcomes — **no xG claim**, possession-chain progression, existing research-xT grid reference), `ui/src/lib/contract.ts`
- Test: `server/tests/test_packs_lane.py`, `core/tests/test_match_artifacts.py`, Playwright on the research pane

**License/redistribution decision (verified):** CC-BY 4.0 permits redistribution → the compact artifact pack (a few KB per match, ~15–30 MB total) is **redistributed by Golavo** as a GitHub-release asset with the Pappalardo citation inside the pack; users opt-in download via the new lane; the 77 MB raw zip never ships and raw events never leave build time.

**Tasks:**
- [ ] 1. Generic pack lane red-green (download→sha256→stage→activate→rollback; isolation policy file per pack class; license-isolation validator extended).
- [ ] 2. Artifact builder + schema (deterministic: same zip → byte-identical artifacts; era badge `2017/18 Wyscout research data (CC BY 4.0, Pappalardo et al.)` embedded).
- [ ] 3. Cockpit research panes with capability chips + "No lawful event feed for this match" empty state; AI fold: artifact numbers enter the evidence bundle as typed `research_*` ids (whitelist round-trip test).

---

## Phase 9 — "Ten Matches, Tracked" · SkillCorner tracking showcase

**Window:** Dec 7 → Dec 18. Roadmap #12. Depends on: **P8** (pack lane + artifact pattern).

**Files:**
- Create: `scripts/build_skillcorner_artifacts.py` (maintainer-side: fetch the 10 matches' `_dynamic_events.csv` ~4 MB + `_phases_of_play.csv` + `_match.json` via raw URLs; tracking `.jsonl` via `media.githubusercontent.com` LFS URLs **only at build time**; compute per-match summaries: width/depth/compactness per phase, speed distributions, off-ball-run counts re-surfaced from their aggregates), `core/tests/test_skillcorner_artifacts.py`
- Modify: registry (MIT pack descriptor — MIT permits redistribution with the copyright notice shipped in-pack), Model Lab or MatchResearch section for the covered A-League 2024/25 matches, contract
- Test: `core/tests/test_skillcorner_artifacts.py`, pane vitest

**Honesty spec:** in-artifact limitation notes verbatim ("~97% ID accuracy; extrapolated frames flagged"); 10 matches → a showcase labeled as such, artifacts keyed to those match ids only; never generalizes, never enters a forecast. Raw ~90 MB/match tracking never ships — compact summaries only (<5 MB pack).

**Tasks:**
- [ ] 1. Build script red-green on one recorded match fixture (LFS media URL path, `is_detected` handling, smoothing note).
- [ ] 2. Ten-match pack + registry + release asset; lane install test reuses P8 harness.
- [ ] 3. Showcase pane + credit line; Playwright + axe.

---

## Phase 10 — "The Event Lab" · StatsBomb opt-in (Tier B, per-user)

**Window:** Jan 2027. Roadmap #8. Depends on: **P8** lane concepts; **owner provenance decision first** (ADR — the registry currently records statsbomb as rejected; this phase's first commit is the ADR superseding that with the verified per-user reading).

**Files:**
- Create: `docs/adr/00XX-statsbomb-per-user-event-data.md`, `server/golavo_server/statsbomb_source.py` + `statsbomb_state.py` (per-user direct download from `raw.githubusercontent.com/statsbomb/open-data/master/...` — competitions.json → matches/{comp}/{season}.json → events/{match_id}.json ~3.4 MB each; host allowlist; size caps; user is the licensee), `packs/overlay-statsbomb/policy.json` (isolation policy: storage boundary `overlays/statsbomb`, forbidden sinks = index/training/sealing/settlement/calibration/**exports**), `server/tests/test_statsbomb_lane.py`, `core/tests/test_statsbomb_artifacts.py`
- Modify: registry entry (class `per-user-research`, terms URL, recheck-by, **registration-request URL surfaced**: statsbomb.com/resource-centre), `scripts/validate_license_isolation.py` (new class), Settings (per-competition download picker: Euro 2024 = 55/282, Women's Euro 2025 = 53/315, WC 2022, Messi La Liga, FA WSL…), event-lab pane (shot maps with **real StatsBomb xG labeled "StatsBomb xG"**, pass networks, 360 frames where present)
- Test: lane tests (consent per step, no export path exists — a test proves the exporter refuses the namespace), red-team additions (event free-text through sanitizer)

**License guardrails (from the read agreement):** app never redistributes/bundles/exports a byte; user-initiated download only, consent screen quotes the non-commercial + no-redistribution terms and links the registration request; StatsBomb logo/attribution rendered on the pane (publication duty technically triggers on publishing, but rendering it is both prudent and required-by-us); revocability documented in the ADR (feature degrades to "source withdrawn" state if the repo disappears).

**Tasks:**
- [ ] 1. ADR + registry + consent copy (owner sign-off checkpoint — this is the one phase that starts with a decision, not code).
- [ ] 2. Download lane red-green (recorded fixtures; per-competition scoping; sha-less upstream → size+schema gates instead).
- [ ] 3. Isolated store + artifacts (shot map / pass network per match, computed locally from the user's copy).
- [ ] 4. Event-lab pane + export-refusal proof + red-team cases.

---

## Program-level self-review (per writing-plans)

- **Coverage:** roadmap items 1→P1, 3→P2, 4→P3, 7→P5, 8→P10, 9→P4, 10→P6, 11→P7, 12→P9, 13→P8. All ten present; women's items (2, 5, 6) deliberately excluded per owner's selection.
- **Ordering rationale:** P1 is deadline-bound (season starts Aug 16–28) and unlocks P4; P2/P3 are data-already-local quick wins scheduled around P1; P5–P7 are independent mid-size lanes in rising-effort order; P8 builds the shared pack-downloader before P9/P10 need it; P10 is last because it alone requires a provenance-decision reversal and carries revocation risk.
- **Type consistency:** the pack lane introduced in P8 (`packs_lane.py`) is the same interface P9 ships through and P10's policy/isolation mirrors; `resolve_training_pack(source_id, competition_id)` from P4 is not used by any later phase; `kickoff_local_hhmm` from P1 is consumed only by P4's optional task 4.
- **Placeholder scan:** each phase names exact files, verified data mechanics, and testable task boundaries; full red-green step expansion happens per-phase at execution time per the scope note — that expansion is the required next step before writing any code for a phase, not optional.
