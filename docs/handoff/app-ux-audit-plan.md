# App UX Audit & Improvement Plan — v0.3.1 → v0.3.2 / v0.4.0

**Prepared:** 2026-07-12, against `main` @ `135de3e` (v0.3.1); key claims re-verified against `4dfa762` (v0.3.2) after it landed mid-audit. **Status: PLAN ONLY — nothing here is implemented.**
**Produced by:** a four-track audit (user flows, UX surface, bugs/health, docs staleness) + a hands-on walkthrough of the mock web build, followed by two adversarial critique passes over this document.

Health baseline at audit time: `tsc --noEmit` clean · vitest 15/15 · ruff clean · core pytest 189 passed · server pytest 124 passed · zero TODO/FIXME markers in source. The app is healthy; this plan is about the gap between *healthy* and *excellent*.

---

## 0. Read this first (executor notes)

### 0.1 ⚠️ v0.3.2 landed mid-audit — reconcile before executing
While this audit ran, a concurrent session landed **v0.3.2 (`4dfa762`, "AI Analyst Read on the cockpit, honest progress, quick toggle")**, touching several files this plan cites: `main.py`, `ai_gateway.py`, `evidence.py`, `evidence_bundle.schema.json`, `AiDeepRead.tsx`, `Layout.tsx`, `index.css`, `ai.ts`, `api.ts`, `MatchDetail.tsx`, `ForecastDetail.tsx`. Re-verified against `4dfa762`:
- **A1 still valid** — the forecast `narrative` route still runs its AI work inline; the **new** `POST /api/v1/matches/{id}/narrative` route (added in v0.3.2) already wraps everything in `run_in_threadpool` — mirror it.
- **A4 still valid** — `var(--seal)` / `var(--info)` remain undefined.
- The server now has **18 routes** (the flow inventory in Phase B was written against 17); AiDeepRead was substantially reworked — **re-verify F6, C1 #20, and any AiDeepRead/Layout/index.css line refs against current `main` before editing.**
- Line numbers elsewhere are valid at `135de3e`; re-grep the quoted string/symbol if a file has moved — every item carries enough context to re-locate it.

Work in a fresh worktree branched from current `main` (you cannot check out `main` inside a worktree; merge via `git -C <primary> merge --ff-only <branch>` then push). Check `git -C <primary> status -s` for further in-flight work before you start.

### 0.2 Repo gotchas (learned the hard way; do not rediscover)
- **Python floor is 3.12** (core pins scipy 1.18.0). Don't relax the pin; don't build a 3.11 venv.
- macOS + hatchling editable installs: if `import golavo_core` mysteriously fails, the venv's `.pth` may carry the hidden flag — `chflags nohidden <site-packages>/*.pth`.
- `vitest run` must not collect `ui/tests/**` (Playwright) — the exclude already exists in `ui/vite.config.ts`; keep it when touching that file.
- Release bumps go through `scripts/bump_version.py` (14 spots, CI-guarded). The **README badge/warning are manual** (see G11). Tags dodge `ci.yml` cancel-in-progress; tag a known-green commit.
- Updater signing key: never regenerate; escrowed outside the repo. No plan item touches signing.
- The web build runs on bundled mocks by default (`ui`: `npm run dev`); live mode needs `VITE_GOLAVO_API`. Playwright e2e + axe run against the mock build.
- **`ui/src/lib/api.ts` is classified as binary by plain `grep`** (it contains UTF-8 `≥ ± →` glyphs) — use `grep -a` (or rg) or your searches over it will silently return nothing.

### 0.3 Verification recipe (run after each phase)
```
cd ui && npm run typecheck && npm test && npm run build
cd ui && npx playwright test          # e2e: overflow + axe
ruff check .
pytest -q                             # collects core/tests + server/tests from repo root
```
Manual smoke: `npm run dev` in `ui/`, walk: home → match (played + upcoming) → forecast (scored/voided/superseded, Casual & Expert) → Lab (all four) → search → settings → 375 px pass (open the Reading-comfort popover!).

### 0.4 Suggested release slicing (v0.3.2 is already taken)
- **v0.3.3** — Phase A (bugs) + Phase C (copy) + Phase E (perf) + Phase H (CI). Low-risk, high-polish, no new flows.
- **v0.4.0** — Phase B (data refresh — a real new capability) + Phase D (visual identity) + Phase F (onboarding/flow guards) + Phase G (docs/site overhaul, last, so screenshots capture the final UI).

---

## 1. Executive summary — the ten things that matter most

1. **Wire the data-refresh engine to users** (B1–B6). It is fully built server-side and has *zero* triggers — no route, no UI — while home/league copy already promises "refreshes on demand". This is also the root cause of the dead-end first-run experience.
2. **Fix the event-loop-blocking AI route** (A1) — a narrative call can freeze `/health` and the whole API for minutes.
3. **Add an error boundary + guard router decoding, and give the startup splash a timeout** (A2, A12) — today a malformed deep link (`#/match/%`) white-screens the entire app, and a dead engine pins users at a 94 % splash forever; neither has any recovery path.
4. **Fix the mobile Reading-comfort popover** (A3) — it renders ~80 px off the left edge of a 375 px screen; controls are clipped and unusable.
5. **De-jargon the casual-facing surfaces** (C1–C3) — ECE/RPS/`P(H/D/A)`/`1X2`/"marginals"/`−ln(p)`/`T−60m` leak expert vocabulary into default views; several headings disagree with their own nav labels.
6. **Make first-run coherent** (F1–F3) — a one-time welcome card, retry buttons on the two dead-end 503 states, and empty states that lead somewhere.
7. **Cut the initial bundle and duplicate fetches** (E1–E4) — route-level code splitting, a tiny request cache, and one lifted notebook fetch per page; plus stop shipping the 23-keyframe animated logo into every header.
8. **Give the calm workbench its texture and glyphs** (D1–D6) — status/fact/voice icons, one-shot seal-stamp motion, drawer reveal ease, a whisper of paper grain; all `prefers-reduced-motion`-gated, all CSS-only.
9. **Overhaul the stale docs surface** (G1–G12) — `matchday.md`, `roadmap.md`, `architecture.md`, `privacy-security.md`, `ui/README.md` all describe the pre-pivot app (one page even denies in-app sealing exists); **every screenshot in the repo predates the pivot**.
10. **Close the CI holes** (H1–H4) — the Tauri shell is never compiled on PRs; the ui job uses `npm install` instead of `npm ci`; axe covers only 4 of 10 routes.

---

## Phase A — Correctness fixes (bugs found; all verified against committed code)

### A1 · HIGH — AI narrative route blocks the asyncio event loop
- **Where:** `server/golavo_server/main.py:423-484` (`narrative`, an `async def`), `server/golavo_server/ai_gateway.py:250-256` (sync `urllib.request.urlopen`, user-configurable timeout up to 120 s × 2 attempts), `ai_gateway.py:192-197` (`subprocess.run(["security", ...], timeout=5)`).
- **Symptom:** while a narration runs, every other route — including `/health` — stalls. Worst case minutes of frozen API. The blast radius is wider than "slow API": **both the startup gate (`ui/src/lib/startup.ts`) and the desktop updater pill poll `/health`**, so one in-flight narration can make a healthy running app look like it is still starting or disconnected. The codebase already knows the fix: `create_seal` and `match_analysis` use `run_in_threadpool`, and the seal docstring (`main.py:350-353`) explicitly contrasts itself with "the older narrative route".
- **Fix:** wrap the blocking work (`_load_artifact` + `build_evidence_bundle` + `generate_narration`) in `await run_in_threadpool(...)`, mirroring `create_seal`.
- **Verify:** server test that starts a narrative with a stubbed slow gateway and asserts `/health` answers < 1 s **concurrently with the in-flight narration**. ⚠️ Touches files under concurrent edit (§0.1).

### A2 · MEDIUM — No React error boundary; router decode can throw in render
- **Where:** `ui/src/main.tsx` (no boundary anywhere in the tree); `ui/src/App.tsx:70,73,77` — `decodeURIComponent(match[1])` runs during render; `#/match/%` or `#/forecast/%zz` throws `URIError` → React 18 unmounts everything → permanent blank page.
- **Fix:** (1) wrap route params in a safe decode (`try { decodeURIComponent } catch { null }` → render the existing not-found `EmptyState`); (2) add one top-level `ErrorBoundary` class component rendering the existing `ErrorState` styling with a "Back to games" link — so *any* future render throw degrades to a recoverable screen instead of white.
- **Verify:** unit test for the safe decode; e2e: navigate to `#/match/%`, assert the not-found state renders and nav still works.

### A3 · MEDIUM — Reading-comfort popover unusable on narrow screens
- **Where:** `ui/src/index.css:988-991` — `.rc__panel { position:absolute; right:0; width:max-content; max-width:min(20rem,88vw) }`, anchored to the `Aa` trigger (`ReadingComfort.tsx`). On a 375 px viewport the trigger's right edge sits ~240 px in, so a 320 px panel extends ~80 px past the **left** viewport edge — theme/text/spacing labels are clipped (reproduced hands-on at 375×812).
- **Fix:** at small widths switch the panel to viewport anchoring — e.g. `@media (max-width: 480px) { .rc__panel { position: fixed; left: 12px; right: 12px; top: <header-height>; width: auto; max-width: none; } }` — or clamp with a transform. Keep the existing desktop behaviour.
- **Verify:** extend `ui/tests/overflow.spec.ts` to *open the popover* at 375 px and assert `document.documentElement.scrollWidth <= clientWidth` **and** the panel's `getBoundingClientRect().left >= 0`.

### A4 · MEDIUM — Undefined CSS tokens silently break AI-panel styling
- **Where:** `ui/src/index.css:589` uses `var(--seal)` (active pipeline dot → transparent) and `:570` uses `var(--info)` (disclaimer icon → falls back to `currentColor`). Neither token is defined in any theme.
- **Fix:** define both per theme or substitute existing tokens (`--gold` for the dot, `--wave` for info). While there, grep for any other `var(--` not present in `:root`/theme blocks. ⚠️ `index.css` is under concurrent edit (§0.1).
- **Verify:** a tiny script or stylelint step to catch undefined custom properties would prevent regressions (optional; manual check is fine).

### A5 · LOW — Status-blind relative kickoff time ("Played" + "in 1282 days")
- **Where:** `ui/src/lib/format.ts:91-103` (`relative()` is pure date math), rendered unconditionally at `ui/src/components/MatchHeader.tsx:44` and `ui/src/views/MatchdayList.tsx:166`. A played match with a future-dated fixture (all synthetic samples) reads "PLAYED · in 1282 days"; a 2012 match reads "5000 days ago" — noise either way.
- **Fix:** make the call sites status-aware: suppress the relative label for played/voided matches (the score + date already say everything), and only show relative time for upcoming matches within a sane window (e.g. ≤ 60 days), else just the date.
- **Verify:** unit tests on the new helper; visual check on a played + an upcoming mock match.

### A6 · LOW — `golavo-updates-last-check` is the one unvalidated localStorage read
- **Where:** `ui/src/lib/updater.ts:189-191` — `Number(raw)` → `NaN` → "Last checked Invalid Date" in Settings/sheet. Every other persisted key is allowlist-validated.
- **Fix:** `Number.isFinite` guard → treat as never-checked.

### A7 · LOW — `fixtures/check` can 500 instead of 503 on odd upstream JSON
- **Where:** `server/golavo_server/fixtures.py:64-66` — `json.loads(...)["sha"]` raises `KeyError`/`TypeError` on a 200 response with unexpected shape; `main.py:397-407` only catches `FixtureCheckError`.
- **Fix:** wrap shape access; raise `FixtureCheckError("unexpected upstream response")` so the route's honest 503 path handles it.
- **Verify:** server test with a stubbed malformed 200.

### A8 · LOW — `check_new_fixtures` walks 75k rows per call
- **Where:** `server/golavo_server/fixtures.py:95-97` — Python-level `iterrows()` over the full index on every call (runs when the opt-in toggle is on, per MatchSearch mount). Seconds of threadpool work.
- **Fix:** vectorize the comparison (pandas boolean mask on the relevant `source_kind`/date columns) or cache the derived set keyed on index identity (mirror the pattern in `server/golavo_server/analysis.py:22-56`).

### A9 · LOW — Unvalidated sessionStorage restore in search
- **Where:** `ui/src/views/MatchSearch.tsx:47-49` — `golavo-search-status` cast to the filter union unchecked; garbage → no chip active, `status=<garbage>` sent (server tolerates). Cosmetic but trivial: allowlist-validate like the other keys.

### A10 · LOW — Score-grid shape is trusted by the renderer
- **Where:** `ui/src/lib/api.ts` contract asserts validate probability sums but never `score_matrix.grid` dimensions vs `max_goals`; `ScoreMatrixHeatmap.tsx:45` (`grid[h][a]`) and `lib/markets.ts:75,93` would TypeError on a short grid. Core always writes `(n+1)×(n+1)` so this needs upstream drift to trigger — but until A2 lands, the failure mode is the same permanent blank page.
- **Fix:** add a dims check to `assertForecast`/`assertMatchAnalysis` so drift surfaces as the loud `ContractError` the README promises. **Ship together with A2** — same white-screen class.

### A11 · INFO — Sidecar `--host ::1` binds a port with the wrong family
- **Where:** `server/.../sidecar.py:33-37,179-187` — `_assert_loopback` accepts `::1` but `_free_loopback_port` binds `AF_INET`. Manual-run-only path; fix or explicitly reject `::1` with a clear message.

### A12 · MEDIUM — Startup splash is an infinite dead-end if the engine never answers
- **Where:** `ui/src/lib/startup.ts:35-42` — `useBackendReady` polls `/health` every 1.5 s **forever**: no max attempts, no timeout, no error branch; `pingHealth` (`api.ts:72-82`) uses `fetch` with no AbortController/timeout. `App.tsx:36` pins `<StartupSplash>` (progress eased to ~94 %) until readiness — so a crashed sidecar, failed extraction, or a hung event loop (see A1) leaves the user staring at a near-full progress bar with no message, retry, or escape. This is a harder dead-end than anything F2 fixes, because the app never renders at all.
- **Fix:** (1) give `pingHealth` an abort timeout (~3 s); (2) after ~30 s of failed polls, switch the splash to an error state — plain words ("The local engine didn't start"), a Retry button (restart polling), and a pointer to logs/reinstall; keep polling in the background so a slow-but-alive engine still recovers.
- **Verify:** unit test the timeout branch; manual: start the UI with no backend in live mode and confirm the error state appears and Retry works.

### A13 · Design ambiguity — the empty-state glyph reads as a spinner
- **Where:** `ui/src/components/states.tsx:4-11` — every `EmptyState` (including the 404) renders `EnsoGlyph`, a thin open circle that a user reads as an infinite loader (observed hands-on: the 404 page appears to be "still loading" forever).
- **Fix (pick one):** style the ensō so it cannot be mistaken for a spinner (visible brush-stroke taper/texture, static), or use distinct glyphs per state kind (not-found → `SearchIcon`, error → `AlertIcon`, genuinely-empty → ensō). Keep `role="status"` semantics.

---

## Phase B — The missing major flow: in-app data refresh (+ the first-run path it unlocks)

**Evidence.** The refresh engine is complete and tested server-side but has **no trigger anywhere**: `server/golavo_server/refresh.py:39` (`merge_refreshed_index`) and `server/golavo_server/matches.py:73` (`repoint_to_refreshed`) are called only by `server/tests/test_refresh*.py`; no route in `main.py` (17 at v0.3.1, 18 at v0.3.2) is a refresh endpoint; the Tauri shell exposes only 6 `updater_*` commands (`desktop/src-tauri/src/lib.rs:210-217`); no UI affordance exists. Consumers already *prefer* a refreshed snapshot if one exists (`matches.py:42-50`, `seal.py:103-105`) — nothing ever writes one. Meanwhile the UI copy promises it: "internationals refresh on demand" (`ui/src/views/GamesHome.tsx:70`), "the one surface that refreshes on demand" (`ui/src/views/Leagues.tsx:26`); and the only related control, Settings → "Keep fixtures up to date", is awareness-only — its own copy tells users new fixtures become forecastable "in the next Golavo update" (`Settings.tsx:78`, `MatchSearch.tsx:336-339`).

**Consequence.** A fresh install has an empty Upcoming rail (bundled club data is historical 2010-2015; internationals snapshot ages), sealing is internationals-only (`server/golavo_server/seal.py:131`), so **the core seal → score → track-record loop is unreachable for a new user**. `CHANGELOG.md:110-112` confirms "no user-facing control yet".

**Design stance (keep the brand promises):** refresh is **user-initiated only** — a button, never a background download. The existing consent toggle stays what it is (a lightweight launch-time *check*); its discovery result gains a path to act. All copy stays honest about scope: refresh covers **internationals** (the source the seal loop uses), not club fixtures.

### B1 — Server: `POST /api/v1/data/refresh`
- Orchestrate: fetch the fresh internationals snapshot → pin it as a pack → run `merge_refreshed_index` → `repoint_to_refreshed` → respond `{refreshed_at, matches_added, upcoming_added, source_sha}`.
- **Honest scope note — the middle step is net-new code, not glue.** What exists: `fixtures.py:_fetch_latest` already downloads the full upstream `results.csv` + commit sha; `merge_refreshed_index` consumes a *pack dir with a hash-correct `manifest.json`* (see `_write_pack` in `server/tests/test_refresh.py:26-50` — the tests fabricate packs, they never download); writable targets exist (`runtime.refresh_dir()` `runtime.py:52`, `runtime.refreshed_pack_dir()` `runtime.py:68`, both `None` in source mode). What does **not** exist in the shipped server: a download→pinned-pack builder. The only pack-builder is `scripts/build_sourcepack.py:105` (used by `watch_and_seal.py:97-108`), which (a) is not in the server wheel (`server/pyproject.toml` packages only `golavo_server`) and (b) writes into `REPO_ROOT/packs/` and registers `packs/snapshots.json` — a git-tree workflow. **B1 must port the pack-pinning logic into `golavo_server` (or `golavo_core`)**, writing into `runtime.refreshed_pack_dir()`, with no `snapshots.json` registration and no git.
- **Update the honesty docstrings this route falsifies:** `main.py:390` ("The ONLY route that reaches the network") and `fixtures.py:4-9` ("the one exception") must be rewritten to name both network paths — and the same fact updated in docs (G5/G12). No CI guard enforces the single-route claim, so it would rot silently otherwise.
- Concurrency: `threading.Lock` (mirror the seal lock), 409 if a refresh is already running, `run_in_threadpool` for the work, never mutate the live index in place (the merge engine already splices into a complete new dir; the repoint is the atomic swap).
- Failure honesty: typed error body `{reason: "offline" | "upstream_changed" | "verify_failed" | ...}`; a failed refresh must leave the previous index untouched.
- Availability: 404/disabled in source-mock mode, like `/shutdown` (`main.py:149-169` shows the pattern).

### B2 — Server: refresh status surfaced
- Extend `GET /api/v1/meta` with `data_refresh: {supported, running, last_refreshed_at, source}` (or add `GET /api/v1/data/status` if meta is under concurrent edit). UI reads this for the Settings line and button state.
- **Contract discipline:** add schema artifacts for the new/extended responses in `docs/contracts/` (a refresh-response schema, and the meta extension). Do it alongside G10's missing `match_analysis.schema.json` so the contracts dir is complete again.

### B3 — UI: Settings → Data grows a real refresh control
- "Refresh match data now" button + "Last refreshed: …" line + progress (indeterminate bar, reuse `.update-progress` styles) + success toast ("Pulled N new fixtures — M upcoming") + typed failure copy. Web/mock build: honest inline note instead of the button (pattern: `AiDeepRead.tsx:96-104`).
- **Rewrite the wait-for-next-release copy** at `Settings.tsx:78` and `MatchSearch.tsx:336-339` to point at the new button ("Refresh now to make it forecastable").

### B4 — UI: empty states route into the flow
- Empty Upcoming rail on Games home (`GamesHome.tsx:70` emptyNote) and empty league upcoming: add a quiet CTA — desktop+live: "Refresh internationals ›" (triggers B1 or deep-links Settings→Data); web preview: keep the current honest note.
- `PredictionLedger.tsx:46-53` "No sealed forecasts yet": link the actual path ("Refresh data → open an upcoming international → Seal") instead of dead-ending.

### B5 — Optional nudge when the check finds news
- If "Keep fixtures up to date" is on and `/fixtures/check` reports new fixtures, show a dismissible pill near the banner: "New internationals available — Refresh?" → B1. No auto-download, ever.

### B6 — Tests & docs for the flow
- Server: route test reusing `test_refresh*` fixtures (success, 409-while-running, failure-leaves-old-index). **Plus new tests for the fetch→pin step** — the existing refresh tests fabricate packs and never exercise a download; stub the upstream and assert manifest hashing, bad-response handling, and that a failed pin leaves `refreshed_pack_dir` absent/previous.
- UI: mock-mode e2e that the button is absent + note present; live-mode unit of the status wiring.
- Docs: G-phase pages get a "Refreshing data" section; CHANGELOG entry.
- Desktop consideration: the sidecar route is enough (UI → HTTP); a Tauri command is **not** required — note this so nobody builds one out of reflex.

---

## Phase C — Copy & clarity (texts easier to read)

Terminology decisions first (apply everywhere; C-items reference them):
| Decide | Use | Retire/limit |
|---|---|---|
| The artifact | **sealed forecast** | "prediction ledger", "artifact" (expert drawers only) |
| The action | **Seal** (verb) | "Track" as a synonym (keep "Track record" as the page name only) |
| The record page | **Track record** | h1 "Prediction ledger" |
| The eval page | **Backtests** | h1 "Evaluation" |
| App chrome | **Golavo · Local football intelligence** | `<title>` "Forecast Audit Workbench" (`ui/index.html:9`) — pre-pivot name |

### C1 — Kill the worst jargon on casual-facing surfaces (the 20-string hit-list)
Verbatim → rewrite table (all verified at cited lines):
| # | Where | Now | Rewrite |
|---|---|---|---|
| 1 | `EvaluationSummary.tsx:95-96` | `ECE` / `RPS` bare headers | `Calibration (ECE)` / `Rank score (RPS)` + `<abbr title>` one-liners |
| 2 | `ScoredPanel.tsx:59` | `−ln(p) of the sealed probability. Lower is better.` | `How surprised the model was by the result — lower means it saw it coming.` |
| 3 | `ForecastDetail.tsx:336-337` | `Beyond N goals a side` / `folded into the tail` | `Very high scores ({n+1}+ a side)` / `grouped into one number` |
| 4 | `ForecastDetail.tsx:358` | chip `exact marginals` | `same grid, re-sliced` |
| 5 | `ForecastDetail.tsx:400-401` | `Each figure is a marginal of the same grid, so it reconciles with the 1X2…` | `Every number here is a re-slice of the score grid above, so it always adds up.` |
| 6 | `PredictionLedger.tsx:155` | `Kickoff (day proxy)` | `Match day` (keep the proxy caveat in the existing footnote `:171`) |
| 7 | `PredictionLedger.tsx:157` | `P(H/D/A)` | `Home / Draw / Away` |
| 8 | `ForecastDetail.tsx:243` | chip `1X2 · regulation` | `Win · Draw · Win — 90 minutes` |
| 9 | `CommentatorsNotebook.tsx:135-136` | `{n} pre-registered hypotheses · registry {v}` | `{n} fixed fact-checks · rule set {v}` |
| 10 | `ReliabilityDiagram.tsx:108` | `● point size ∝ sample count · whisker = Wilson 95%` | `bigger dot = more matches · bars = 95% confidence range` |
| 11 | `ForecastDetail.tsx:307` | `Model uncertainty for this fixture: low` | `How settled the model is here: settled / unsettled` (or keep "low/high" but say "confidence") |
| 12 | `lib/contract.ts:532` `FAMILY_LABELS` | `Elo · ordered logit` | `Elo ratings` in casual surfaces; keep the full name in Methodologies/expert drawers |
| 13 | `lib/contract.ts:546-548` `HORIZON_LABELS` | `T−72h/T−24h/T−60m` chips | `3 days out / 1 day out / 1 hour out` (keep T-form in Expert seal stamp) |
| 14 | `MatchDetail.tsx:243` vs `:264` | title `Track this prediction`, button `Seal this prediction` | one verb: `Seal this forecast` / button `Seal before kickoff` |
| 15 | `MatchDetail.tsx:253` | raw `dixon_coles` in the CTA paragraph | map through `FAMILY_LABELS` → `Dixon–Coles` |
| 16 | `EvaluationSummary.tsx:17` | h1 `Evaluation` | `Backtests` |
| 17 | `PredictionLedger.tsx:22` | h1 `Prediction ledger` | `Track record` |
| 18 | `CommentatorsNotebook.tsx:36` | `Labelled base rates. Reported only — never applied…` | `Historical frequencies — context only; never fed into the forecast.` |
| 19 | `MatchDetail.tsx:249-255` | 62-word seal CTA paragraph | 3 short lines; drop the "immutable/auditable" doubling (trust strip already says it) |
| 20 | `Settings.tsx:101-108` | 75-word AI paragraph (it already leads "Off by default.") | Keep the lead; trim the rest to 2 sentences (local vs BYOK) |

### C2 — Fix the dev-speak and status-blind lines found hands-on
- `MatchDetail.tsx:161-162`: "…this **directory** links to them, it never **re-renders** or restates a number." → "The sealed numbers live on the forecast page — this card only links to them; nothing here restates or recomputes a probability."
- `ScoredPanel.tsx:64` (Brier gloss): plain-words version, same treatment as C1#2.
- "Chance of more than… 0.5 total goals" (`ForecastDetail` markets block): relabel buckets human-first — "At least 1 goal / 2+ / 3+ …" (same numbers).
- A5's status-aware kickoff phrasing is the copy half of that fix.
- Settings toggle copy says fixtures get flagged "on the **Matches** page" (`Settings.tsx:68-71`) — the nav calls it **Search**; align once B3's rewrite lands.

### C3 — Casual mode: finish the job
- Drawer titles stay jargon in casual (`EXACT-SCORE DISTRIBUTION`, `OUTCOME & GOAL SUMMARIES · exact marginals`, `MODEL & VERSIONS`, `PROVENANCE & INPUTS`): give casual-mode friendly titles ("All the scorelines", "Ways this could go", "Model & version", "Where the data came from") — expert keeps current.
- Seal stamp in casual shows Seed / git sha / params hash / payload sha rows: collapse to `Sealed 17 Jan 2030, 18:00 UTC · Dixon–Coles · full detail ›` with the hashes inside a drawer (expert keeps all rows visible). The identity stays one click away — honesty intact, first-read calmer.
- Add plain anchors to Track-record stats (`PredictionLedger.tsx:251-253`): a footnote line "log loss ≈ 1.10 is the guess-nothing baseline; lower is better" (exact wording from Methodologies).

### C4 — Metric glosses, once, reused
- Add a small `METRIC_GLOSS` map (log loss / Brier / ECE / RPS / calibration) in `lib/format.ts` or a new `lib/glossary.ts`; render as `<abbr>`/`InfoPopover` in Backtests, Track record, Scored panel, Model Lab hub card ("log loss, Brier, RPS, ECE" spelled there too — `ModelLab.tsx:21`).

### C5 — Web-preview Settings shows no app version
- `Settings.tsx:39-59` About block says only "Golavo source build (contract v0.2.0)". Inject the app version at build time (`define: { __APP_VERSION__: JSON.stringify(pkg.version) }` in `vite.config.ts`) and render "Golavo v0.3.x · contract v0.2.0". (Desktop already shows its own version via the updater block.)

---

## Phase D — Theme, texture, icons, motion (the "calm workbench", finished)

Hard rules: **zero new runtime deps**; all motion `prefers-reduced-motion`-gated (the global kill-switch at `index.css:546-551` already exists — extend, don't bypass); nothing animates a number's *meaning* (no bar-width tweening that implies recompute); no blur/vibrancy (explicitly cut in the Phase-10 plan for Tauri perf).

### D1 — Token hygiene
- Add `--radius-xs: 7px`, `--radius-pill: 999px` and sweep the literal `10px/8px/7px/5px/4px` radii (`index.css:248,263,380,411,426,530,776…`) onto the scale.
- Tokenize the repeated AA-fix ink hexes (`#785808` ×5 at `:360,660,667,802,817,844`, plus `#0a5f45`, `#35507f`, `#565247`, `#9a4116`, `#6b5a1e`, `#e6bd45`) into per-theme `--chip-*-ink` tokens.
- Unify input focus rings: `.ms-search:892` and `.mv-filter-input:868` use `2px var(--gold-line)` vs the global `3px var(--focus)` (`:220`) — pick the global ring.
- (A4 fixes the two undefined tokens.)

### D2 — Texture: paper tooth, one hairline of light
- `body::before`: a tiled 64×64 data-URI grain (or single `feTurbulence` SVG) at 2-4 % opacity, `pointer-events:none` — the sumi-e tactility the brand copy promises, ~0 runtime cost. **Not** `background-attachment: fixed`.
- Cards/panels: `box-shadow: inset 0 1px 0 rgba(255,255,255,.03)` top-lit hairline (light theme: a dark equivalent) — physical depth without new elevation tiers.
- Extend the `.seal` radial treatment (`:443`) to the forecast hero/verdict block — one focal lift per page, no more.

### D3 — Icons: finish the system
- Status chips (`primitives.tsx:9-16`) gain glyphs: sealed→`SealIcon`, scored→`CheckIcon`, voided→`VoidIcon`, abstained→`ClockIcon` (colour-blind-safe, removes dot-colour-only encoding).
- Fact-type labels (`CommentatorsNotebook.tsx:166`): predictive→`SparkIcon`, context→`BookIcon` (currently dead code — revive), coincidence→`AlertIcon` (already used in group head).
- Model voices (`ModelCouncil.tsx:263`): ratings→`ScaleIcon`, goals→a new small goal/net glyph, baseline→`GlobeIcon`.
- Nav (`Layout.tsx:65-67`): optional small glyphs (Games ⚽-style `TrophyIcon`? keep restrained — text-first is fine; decide in-flight).
- Replace stray text glyphs where trivially consistent: `✕` toast close (`updates.tsx:431`) → an X icon; keep `★` in the heatmap (it carries an aria-label and works).
- Delete dead icons `SunIcon`, `MoonIcon`, `ArrowLeft` (`icons.tsx`) — or use them (Sun/Moon could badge the theme control). `BookIcon` gets revived above.
- Normalize per-call sizes (SealIcon 17/18/20 drift; `SealStamp.tsx:15`, `ScoredPanel.tsx:69`).

### D4 — Motion: four one-shot, calm effects
1. **Seal stamp-in** (`SealStamp.tsx`): one-shot scale(1.06→1)/opacity on mount of a *sealed* page — the "committed to the record" moment.
2. **Drawer reveal** (`disclosure.tsx` / `.drawer__body`): ease open with the `grid-template-rows: 0fr→1fr` technique (native `<details>` can't transition height; keep semantics, animate the inner wrapper).
3. **What-moved deltas** (`ForecastDetail.tsx:189` re-seal panel): brief fade/slide-in of the ▲/▼ rows, staggered 40 ms.
4. **Casual⇄Expert switch**: 120 ms opacity crossfade on the mode body — kills the hard jump without implying recompute.
- Also: swap the **header brand lockup to the static SVG** — `Layout.tsx:36,61` currently ship `public/brand/golavo-lockup-{dark,light}.svg` = the *animated* variants (7850 B, 23 infinite 6.5 s keyframes compositing on every page); static 3846 B variants exist in `assets/brand/static/` but aren't in `public/`. Keep animation for `StartupSplash` only. (Also E-value.)

### D5 — Backtests page: from wall-of-tables to readable
`EvaluationSummary.tsx` renders ~18 fold tables × 5 models × 4 metrics with no visual anchor (verified hands-on). Add, in order of value:
1. Per-fold **best log-loss highlight** (bold + `--gold-soft` row tint) — instant "who led here".
2. **Per-competition `<details>` groups** (first open by default) with fold count in the summary row.
3. A compact **summary strip** up top: per-competition leader counts ("Elo leads 5 folds · Goals 4 · never averaged").
4. Sticky `<thead>` within groups; C1#1's glossed headers.
Keep every number — this is layering, not hiding.

### D6 — Empty-state glyph identity (A13's design half)
Differentiate not-found / error / empty as chosen in A13; give the ensō a visible brush-stroke character (dash taper) so it reads as ink, not as a loading ring.

---

## Phase E — Performance (faster, lighter; zero new deps)

### E1 — Route-level code splitting
`App.tsx:5-14` statically imports all ten views; no `React.lazy` anywhere; main bundle ≈ 297 KB (mock data is already split via dynamic `import()` — good). Lazy-load the heavy non-landing views (`ForecastDetail`+heatmap, `EvaluationSummary`+reliability, `PredictionLedger`, `MatchdayList`, `Settings`, `Leagues`, `ModelLab`, `MatchSearch`) behind `Suspense` with the existing `Loading` fallback. Target: Games-home-first bundle materially smaller; verify with `vite build` output table before/after (record numbers in the PR).

### E2 — Tiny request cache + in-flight dedupe in `lib/api.ts`
Map<url, {promise, value, ts}> with (a) in-flight coalescing, (b) short TTL (~30 s) or LRU ~50 entries, (c) explicit bypass for `POST` (seal/narrative) and for `fixtures/check`, and (d) **invalidate the cache after any successful mutation** — a seal (`sealMatch`) or a data refresh (B1) must clear match/forecast entries so the ledger and rails can't serve pre-mutation data. Separately, give the `fixtures/check` **result** its own session-scoped memo: today every `MatchSearch` mount with the toggle on re-hits the network (`MatchSearch.tsx:305-311`), and B5 adds a second consumer — one check per app session is plenty. ⚠️ `api.ts` under concurrent edit (§0.1).

### E3 — Lift the duplicated notebook fetch (independent of E2, do both)
- `ForecastDetail.tsx:122` (`InsightCards`) + `:128` (`CommentatorsNotebook`) each call `fetchNotebook(artifact_id)` — fetch once in the parent, pass data down (also stops `topInsights()` running twice).
- Same on the cockpit: `MatchDetail.tsx:103` + `:337` both call `fetchMatchNotebook(id)`.

### E4 — Stop fetching the whole ledger for two neighbours
`ForecastDetail.tsx:24-27` runs `Promise.all([fetchForecast(id), fetchForecasts()])` — the full list (every artifact, validated) just to derive `supersededBy`/`previous` (`:36-39`). Fix: `previous` via `fetchForecast(artifact.supersedes)` when present; `supersededBy` via a server-provided `superseded_by` field on the detail response (server derives it cheaply; add to contract + mock) — or, interim, a `?fields=` slim list call. Scales with real ledger growth.

### E5 — Memoize the pure-render heavies
No `React.memo`/`useMemo` in `src/components` at all. Wrap `ScoreMatrixHeatmap` (rebuilds `grid.flat()`/`maxCell` per render — `ScoreMatrixHeatmap.tsx:19`), `ReliabilityDiagram`, and `deriveMarkets()` results (`useMemo` keyed on artifact id) so the Casual⇄Expert toggle and D4's crossfade don't recompute the world.

### E6 — Server micro-fixes with UX effect
A8 (fixtures vectorization) and A1 (threadpool) are the perf-relevant server items; nothing else measured hot (analysis/search already cached + paginated — `analysis.py:22-56`, `matches.py:310,429`).

### E7 — Perf guardrails (keep it fast)
- Keep the **zero-runtime-deps** rule (react + react-dom only) — reject any plan step that adds a chart/animation/router lib.
- Record `vite build` size table in PRs that touch `App.tsx`/views; optional: a CI size note (no hard gate needed yet).
- Fonts: system stack already (`--font-sans`), no webfont cost — don't add one.

---

## Phase F — Flow guards, onboarding, small missing pieces

### F1 — First-run welcome card (one-time, dismissible, calm)
On Games home, above the rails, first visit only (`localStorage golavo-welcome-dismissed`): three quiet lines — "Open any match for the model council's read · Upcoming internationals can be **sealed** before kickoff and scored after · Your record lives in **Model Lab › Track record**" + dismiss. No modal, no tour, no arrows. (Pairs with B4's empty-state CTAs; in web preview the existing banner already explains sample mode — don't double up: show one or the other.)

### F2 — Retry where users currently dead-end
- Council 503 "warming up" (`ModelCouncil.tsx:92-99`) and match-notebook 503 (`MatchDetail.tsx:360-367`) render advice with **no retry control** (search already has one — `MatchSearch.tsx:234`). Add a "Try again" button re-triggering the fetch (nonce state into `useAsync` deps). `ErrorState` already accepts `onRetry` (`states.tsx:17`).

### F3 — Appearance discoverability
Settings has no Appearance section (theme/text live only in the header popover — verified hands-on). Add a small "Appearance" block in Settings that either embeds the same controls (shared component with `ReadingComfort`) or a one-liner + "Open Reading comfort" affordance. Cheap, ends the "where's dark mode" hunt.

### F4 — Route alias `#/games`
Nav label says **Games** with `href="#/"`; a typed/bookmarked `#/games` 404s (verified). Add `/games` → `Redirect to="/"` next to the existing legacy redirects (`App.tsx:87-88`).

### F5 — A11y follow-ups from the audit
- Match/forecast card links have **no accessible name** (`GameCard` `GamesHome.tsx:105`, `MatchdayList.tsx:145` cards; observed as blank links in the a11y tree): add `aria-label={"${home} v ${away} — ${status}, ${date}"}`.
- `FactLegend` is `aria-hidden` (`MatchDetail.tsx:396`) — the predictive/context/coincidence glosses never reach screen readers; unhide (visually unchanged) or provide an SR-only equivalent.
- `ReadingComfort.tsx:50` sets `role="dialog"` without focus trapping: either trap (the update sheet already has the pattern — `updates.tsx:59-95`) or drop to a plain popover role.
- Small probbar segments (<12 %) hide their % label (`primitives.tsx:65`) — ensure the legend always carries the numbers (it does; just don't regress it).

### F6 — AI provider select on surfaces where it can't run
Web/mock + synthetic pages keep the provider dropdown enabled while the panel says it's unavailable (`AiDeepRead.tsx:78-104`): disable the control with the explanatory note in those contexts so the first interactive element isn't a no-op.

---

## Phase G — Docs, website, README overhaul

Deployment fact: `pages.yml` auto-deploys `docs-site/**` changes on push to main — stale content is **live** at udhawan97.github.io/Golavo. Version strings are otherwise healthy: `bump_version.py` syncs 14 spots, all at 0.3.1.

### G1 · P0 — Rewrite `docs-site/src/content/docs/matchday.md`
Worst page in the tree: titled "Your matchday", names screens that don't exist ("Fixture Room", "Forecast Theatre"), and **falsely states sealing is CLI-only / a future release** (contradicted by `POST /api/v1/matches/{id}/seal`, shipped v0.2.4, reframed v0.3.0). Rewrite around: Games-first home → Match Cockpit (**Replay** for played / **Preview** for scheduled, kickoff−1 s cutoff, two voices + baseline, honest disagreement, score grid) → seal from the cockpit → Leagues hub → Model Lab. Include the Commentator's Notebook + v0.3.1 signature stats (both-teams-scored rate, scoring momentum, clean-sheet rate, H2H goal character) and the no-repeat rule.

### G2 · P0 — Recapture every screenshot on v0.3.1+
All shipped screenshots predate the pivot (`docs-site/public/screenshots/*` from commit 84baf1a; `ui/screenshots/*` from 20b7a45). After Phases C/D land: shoot Games home, Match Cockpit (Replay + Preview), a scored forecast (casual + expert), Model Lab hub, Track record, Backtests, dark + one light/warm sample, desktop + one mobile. Update `index.mdx:128-145` bento captions and README's `:72-85` details block (currently "See the actual Matchday workbench" + old PNG). Delete or re-shoot orphaned `forecast-scored/sealed.png`.

### G3 · P0 — `docs-site/.../roadmap.md` resync
Still lists "Matchday, Fixture Room, Forecast Theatre", repeats the "in-app sealing deferred" falsehood, lacks Phase 9 Match Cockpit, and numbers phases differently from README. Make README the single source; regenerate this page from it.

### G4 · P0 — `docs-site/.../privacy-security.md` truth reconciliation
Contradicts SECURITY.md: claims "Crash reports are local" (none exist — SECURITY.md:29; claim removed from app in v0.2.5) and "Signed packs, DB migrations | Wired but gated" (minisign not implemented; **no DB/migration layer exists**). Rewrite from SECURITY.md as source of truth.

### G5 · P1 — `docs-site/.../architecture.md`
"the implemented v0.2.0 architecture" (stale); API table omits every `matches/*` route and `fixtures/check`; "POST /narrative is the sole non-GET app route" is false (POST seal; POST match-narrative since v0.3.2; POST refresh after B1). Regenerate the table from `main.py`'s actual routes (18 at v0.3.2, +1 after B1); "Ledger" → Model Lab naming.

### G6 · P1 — `ui/README.md` full rewrite
Still the v0.1.0 "Forecast Audit Workbench" doc: 3 endpoints, 4 views, contract v0.1.0, port 8787 (root README says 8000). Rewrite: current views/routes, contract 0.2.0 (+ analysis 0.3.0), data-source matrix (mock vs `VITE_GOLAVO_API`), port aligned, e2e/axe commands.

### G7 · P1 — `docs-site/.../methodology/facts.md` regenerate
Catalogue predates v0.3.1: registry date says 2026.07.11 (code: `REGISTRY_VERSION="2026.07.12"`, `core/golavo_core/facts/registry.py:25`), family_size stale, missing the four signature templates (`both_teams_scored_rate`, `clean_sheet_rate`, `scoring_trend`, `head_to_head_goals` — `registry.py:71-84`). Consider generating this table from the registry at docs-build time so it can't drift again.

### G8 · P1 — docs-site sidebar nav (`astro.config.mjs:65-118`)
No entries for Match Cockpit / Games / Leagues / Model Lab; "Start here" leads with the stale matchday page; "The Prediction Ledger" label is pre-pivot. Restructure to match the app's own nav vocabulary.

### G9 · P2 — CHANGELOG link refs
Footer compare-links end at `[0.2.3]`; `[0.2.4]…[0.3.1]` missing and `[Unreleased]` still compares from v0.2.3 (`CHANGELOG.md:579-584`). Add the five, repoint Unreleased.

### G10 · P2 — Consistency sweep
Node "22+" (README:212) vs "20+" (`installation.md:67`, `build-from-source.md:10`) — CI uses 22; standardize on 22. `CONTRIBUTING.md:38` "make targets are placeholders" (they're real). `updates-rollback.md:87-88` stale v0.2.0 example. `ui/HANDOFF.md`: add a one-line "Historical (Phase 0) — see docs-site" banner (it still claims CLI-only sealing at `:180`); don't rewrite.
- Commit `docs/contracts/match_analysis.schema.json` — code emits `ANALYSIS_SCHEMA_VERSION 0.3.0` but no schema file exists beside the other four.

### G11 · P2 — Stop the manual-README-version footgun
Add README badge+warning version strings to `scripts/bump_version.py` SPOTS (they're the only version spots outside the automated 14).

### G12 — New docs for what ships in this plan
"Refreshing data" page (B), "Reading comfort & themes" snippet (F3), updated Settings screenshots, CHANGELOG entries per phase.

---

## Phase H — CI & test hardening

- **H1:** Add a `cargo check` (or `cargo clippy -- -D warnings`) job for `desktop/src-tauri` to `ci.yml` — today Rust (888-line `updater.rs` included) compiles only at release-tag time. Cache cargo; macOS runner is enough.
- **H2:** ui job: `npm install` → `npm ci` (lockfile drift currently papered over).
- **H3:** Expand `ui/tests/a11y.spec.ts` beyond 4 routes: add `/matches`, `/lab/track-record`, `/lab/backtests`, `/lab/forecasts`, `/settings`, `/leagues` (the table/form-dense pages where `--text-dim` contrast is unverified). Keep 3-theme matrix.
- **H4:** overflow spec: add the opened Reading-comfort popover at 375 px (A3's regression test), and assert the mobile panel-head fix from 104945e stays fixed.
- **H5:** Unit tests where behaviour is now specified: safe-decode (A2), `relative()` status-awareness (A5), api cache (E2), markets relabel (C2). Address the starlette/httpx testclient deprecation warning when bumping deps.

---

## Ordering & dependencies

```
A (bugs)  ──────────────►  ship v0.3.2
C (copy)  ─────┤                │
E (perf)  ─────┤                │
H (CI)    ─────┘                │
                                ▼
B (refresh flow) ──► F (onboarding/guards) ──► D (visual) ──► G2 screenshots ──► G1..G12 docs ──► ship v0.4.0
```
- A1/A4/E2 and anything in `main.py`/`api.ts`/`index.css`/`Layout.tsx` **must first reconcile with the concurrent AI/evidence work** (§0.1).
- G2 (screenshots) strictly after C+D land — shoot once.
- B before F (F's CTAs point at B's control) and before G1/G12 (docs describe it).
- Inside phases, items are independent and can be parallelized.

## Global acceptance gate (before each release)
1. §0.3 recipe green (typecheck, vitest, build, Playwright+axe incl. new routes, ruff, pytest).
2. Hands-on 375 px pass: popover open, no horizontal scroll anywhere, panel heads intact.
3. Bundle table recorded; initial JS not larger than baseline (297 KB) — smaller after E1.
4. Copy sweep: no `ECE`/`RPS`/`P(H/D/A)`/`1X2`/`T−60m`/`dixon_coles` visible on casual surfaces; `<title>` updated; h1s match nav.
5. Refresh flow (v0.4.0): fresh-install path works end-to-end — refresh → upcoming international appears → seal → track record shows it; failure leaves old index intact; web preview stays honest.
6. Docs: matchday/roadmap/privacy/architecture/ui-README verified against the running app; screenshots current; CHANGELOG entries + link-refs updated.

## Out of scope (explicitly)
Club forward fixtures & club sealing (data-source scope, not UX); signing/notarization; new model families; any betting-adjacent framing; background/auto network activity of any kind (refresh stays user-initiated); new runtime dependencies.
