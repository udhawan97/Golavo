# Phase 10 — UI/UX Redesign Plan ("Calm Workbench")

*Status: PLAN ONLY — nothing implemented. Written 2026-07-12 against HEAD `1ac0553`.*
*Inputs: screenshot review (Match Detail, Argentina v Egypt, dark theme), full `ui/src` audit, design research (Apple HIG, FotMob/Sofascore/Apple Sports, Stripe/Linear/Mercury, FiveThirtyEight/Metaculus/Polymarket).*

**Product contract (unchanged, non-negotiable):** deterministic/statistical forecasts are authoritative. AI explains evidence only; it never changes a probability or becomes a second forecast engine. Depth toggles change *how much* is shown, never displayed certainty.

---

## 0. Rebuttal first — attacking this plan before proposing it

Per the brief, the self-challenge comes first; the plan that follows already incorporates these cuts.

**What would be overdesigned (cut):**
- **Team-color theming / crests** (Apple Sports' signature move). Teams are plain strings in the contract — no crest assets, no color data, licensing risk. Cut until a data phase adds team metadata.
- **Vibrancy/translucency materials.** Blur-heavy chrome in a Tauri WebView is a perf/compat gamble for marginal calm. Solid surfaces on the existing 3-step ladder achieve the same hierarchy.
- **Replacing the score-matrix `<table>` with canvas/SVG.** The accessible table with CSS heat tint is already good; a canvas rewrite loses a11y for polish nobody asked for.
- **A component library or Tailwind.** The zero-dependency posture (`react` + `react-dom` only) is a supply-chain feature of a local-first app. The 802-line CSS file is not the problem; its missing spacing/type scale is.
- **CSS-file splitting / CSS modules.** Churn with no user-visible value at this scale. Reorganize sections inside the one file instead.

**What would slow implementation too much (descope):**
- Full Playwright matrix across every page × theme × viewport × mode. Scope to ~6 routes × 3 viewports × dark (light spot-checked on 2 pages), or CI time balloons.
- Redesigning navigation/app shell. The header/nav is fine; the pain is page composition.

**What could accidentally reduce trust (guardrails):**
- **Cutting hedge copy too far.** The repeated disclaimers are the #1 density problem, but deleting them outright hides the truth. Rule: *each guarantee is stated exactly once per page, visibly; secondary restatements collapse into ⓘ popovers.* "No retro-forecasting" and "sealed before kickoff" always remain visible in the default view — as compact labeled strips, not paragraphs.
- **"3 things to know" becoming editorial.** If selection looks curated, it reads as AI or opinion. It must be a pure, documented, unit-tested ranking function over existing notebook facts (label priority → specificity → sample size → stable id tie-break), labeled "chosen by fixed rules, not by AI."
- **A "confidence badge" reading as an accuracy claim.** It must surface the model's own `uncertainty` flag and the ledger's *measured* calibration — never an invented composite score.
- **Whole-number percentages changing "displayed certainty" between modes.** Resolution: the probability bar goes to whole numbers in *both* modes (kills false precision, preserves the byte-identical rule); one-decimal stays only in expert tables (heatmap, ledger, eval).

**What should be deferred (not in phases A–F):**
| Deferred item | Why |
|---|---|
| Form-guide W/D/L squares | Needs a new deterministic recent-form series from core; no structured data today |
| Match story timeline (in-match) | No minute/event data exists; anything shown would be fabricated |
| "What changed?" re-seal delta panel | Data exists (`supersedes` chain) but re-seals are rare today; build after the first real ones |
| Team crests/colors | No data, licensing risk |
| BTTS/team-total markets | Intentionally excluded — tail not exactly decomposable (`lib/markets.ts`) |

---

## 1. Visual diagnosis (severity-ranked)

From the screenshot and code audit:

1. **CRITICAL — Trust copy does the work layout should do.** The notebook panel opens with two hedging paragraphs + a three-chip legend with three inline notes before the first fact. Every panel re-states its guarantees in full sentences (`MatchDetail.tsx:336-339`, `CommentatorsNotebook.tsx:46-49`, `ForecastDetail.tsx:234-239,273-281`). The page reads as disclaimers-with-data-attached.
2. **CRITICAL — Notebook facts are raw evidence rows, not insights.** Each fact states its numbers twice: once inside the sentence ("has won 61.2% of 134 non-neutral matches") and again in the meta row ("sample **134** · base rate **61.2%**"). No visual encoding of the rate, raw ISO date ranges ("1930-07-18 → 2026-07-06"), raw mono pack ids (`martj42-international-results`) as chips. (`CommentatorsNotebook.tsx:162-188`)
3. **HIGH — Header metadata bleed.** Raw `match_id` mono hash floats in the h1 meta line; icon/text pairs wrap out of alignment (clock icon orphaned above its date in the screenshot); competition/date/venue/id compete in one flex-wrap row. (`MatchDetail.tsx:84-94`, same pattern `ForecastDetail.tsx:55-60`)
4. **HIGH — Flat hierarchy of same-weight panels.** "Final score" and "Commentator's Notebook" have identical visual weight; the score `3–2` renders at ~1.15rem while an info callout below it is nearly as tall as the score block. Nothing on the page is the hero.
5. **MEDIUM — Card-in-card-in-card.** `panel > nb-group > nb-fact` = three nested bordered rounded boxes; four counting the page. Each nesting level adds a border, radius, and background shift — reads heavy and busy.
6. **MEDIUM — Pill overload.** Chips are used for status, taxonomy, legend, source, meta, and mode — six meanings, one shape. Users can't tell interactive from static.
7. **MEDIUM — Compressed type scale.** h1 caps at 2rem; panel titles are .82rem uppercase; body is .9–1rem. Hierarchy is carried by uppercase + letterspacing everywhere → "dense terminal," not "calm Apple." No spacing scale: ad-hoc rem values throughout.
8. **MEDIUM — Long lines.** Fact sentences run ~120ch across the 1080px content column. Comfortable reading is 45–75ch.
9. **LOW — One-decimal percentages everywhere** ("61.2%") imply false precision (the 538 lesson).
10. **LOW (already decent) —** empty/error/loading states exist (ensō empty state, skeletons, honest error copy); light theme is complete with AA fixes; reduced-motion is handled; tables scroll under `.table-wrap`. Mobile is fluid with one 860px breakpoint — adequate, unverified by any test.

---

## 2. Product framing

**Casual user opening a match (the 10-second read):**
They should learn, in order, without scrolling past ~4 modules: (1) who's playing, when, where, and the status; (2) the outcome — final score as the hero if played, the probability bar + plain-language verdict if forecast; (3) three things worth knowing (deterministic insight cards); (4) one compact trust strip ("Sealed before kickoff ✓ · deterministic ✓ · no AI in the numbers ✓"). Zero hashes, zero ISO timestamps, zero registry jargon, whole-number percentages, natural-frequency phrasing ("about 3 in 5").

**Expert user (provenance, math, matrix, calibration):**
Everything the app knows, one disclosure away, none of it visually dominant by default: exact-score heatmap + tail decomposition, derived markets, model family/version/seed/hashes, training cutoff, provenance receipt per snapshot (sha256, license, retrieved-at), notebook fact metadata (sample/denominator, date ranges, suppressed candidates, registry version), reliability diagrams with Wilson intervals. The existing rule holds: expert mode shows *more of the same sealed numbers*, never different ones.

**The wall between them:** expert depth lives in collapsed disclosure panels and the Expert mode; the casual default never renders a hash, a mono id, or a third decimal. The only expert artifacts visible by default are the trust strip and the seal stamp identity (which are the product).

---

## 3. Information architecture

Target hierarchy for the match/forecast surface (top → bottom):

```
1. MATCH HEADER        breadcrumb · status chip · TEAMS (hero type) · one meta line
                       (comp · date-with-relative · venue) — match_id demoted to
                       the provenance drawer
2. VERDICT ZONE        played: hero score (large, light-weight numerals) + ScoredPanel
                       forecast: plain-language verdict + probability bar (whole %)
                       + "about 3 in 5" natural-frequency subline
3. TRUST STRIP         one compact row: "Sealed 6 Jul, 18:42 — 5h before kickoff ✓ ·
                       deterministic ✓ · AI never touches these numbers ⓘ"
                       (each ⓘ opens the full explanation; copy stated ONCE here,
                       nowhere else on the page)
4. THREE THINGS TO KNOW  3 insight cards derived by fixed rules from the notebook
5. COMMENTATOR'S NOTEBOOK  grouped inset list (HIG pattern), tabs/segments for
                       Predictive · Context · Coincidence; facts as insight rows
                       with a rate bar; per-fact ⌄ disclosure for meta
6. EXPERT DRAWERS      collapsed <details> accordions (Expert mode expands them):
                       Exact-score matrix · Outcome & goal summaries ·
                       Model & versions · Provenance receipt · Calibration context
7. AI DEEP READ        unchanged position and subordination (dashed, recessed, off
                       by default)
```

**Disclosure mechanics — decisions:**
- **Keep the Casual ⇄ Expert toggle** (it exists, is persisted, and is the right primitive). Extend it: honored on MatchDetail too (notebook meta density), not just ForecastDetail.
- **Accordions (`<details>`-based, animated, a11y-native) for expert drawers** — not tabs. Tabs hide the page's shape; collapsed accordions keep the whole audit trail scannable and printable. Expert mode = accordions default-open + meta rows visible; Casual = collapsed + hidden.
- **ⓘ popovers for guarantee restatements** (hover + click + focusable, `aria-describedby`). Never for primary truth — "no retro-forecasting" keeps a visible strip.
- **Segmented control for notebook groups** (Predictive/Context/Coincidence) on narrow viewports, all-groups-stacked on desktop. Coincidence keeps its quarantine styling in both.

Matchday list, Ledger, Eval keep their IA; they get the same primitives (density, type scale, sparklines, empty states) in Phases A/D.

---

## 4. Analytics & artifacts

| Artifact | User value | Data required | Supported today? | Effort | Overclaim/confusion risk |
|---|---|---|---|---|---|
| **Probability bar polish** (whole %, 44px, direct labels, natural-frequency subline) | The one-glance answer | `forecast.probs` | ✅ exists (`primitives.tsx:40`) | **S** | Low — whole numbers *reduce* false precision |
| **"3 things to know" insight cards** | The casual payoff; turns evidence into a story honestly | notebook facts (label, specificity, sample_n, freshness) | ✅ all fields exist | **M** | Medium — selection must be a pure documented ranking fn, labeled "fixed rules, not AI" |
| **Notebook insight rows** (rate bar, humanized dates "96 years of data", source popover) | Makes facts readable | fact fields | ✅ | **M** | Low — same numbers, better clothes |
| **Scoreline heatmap promotion** (casual: one "most likely 2–1, about 1 in 8" line; expert: existing table, modal cell labeled) | Distribution as the object | `score_matrix` | ✅ exists (`ScoreMatrixHeatmap.tsx`) | **S** | Low |
| **xG stat tiles** (Stripe card anatomy: label/value/hint) | "How many goals to expect" | `expected_goals` | ✅ | **S** | Low — must say "expected", never "predicted score" |
| **Confidence/calibration badge** | "Should I trust this one?" | `uncertainty` + ledger `running` | ✅ both exist | **S–M** | **High** — copy must be "model flags low certainty" + "measured: when we said 70%, it happened 68%" — never a made-up composite |
| **Plain-words calibration line + reliability sparkline** (ledger & eval) | Calibration for humans | `reliability_bins` | ✅ | **M** | Low — it's the honest sentence 538/Calibration City proved works |
| **Provenance receipt restyle** (source → sha → retrieved, receipt idiom) | Auditability that looks like a feature | `inputs.snapshots` | ✅ (`Provenance.tsx`) | **S** | Low |
| **Artifact lifecycle strip** (sealed → kickoff → scored, with timestamps) | Shows the no-retro guarantee as a picture | artifact timestamps | ✅ | **S** | Low |
| **Delta chips on ledger counts** | Trend at a glance | needs history of counts | ⚠️ partially (no time series) | M | Medium — skip deltas, keep counts |
| **"What changed?" re-seal diff** | Explains superseded seals | both artifacts' probs via `supersedes` | ⚠️ chain exists, `superseded_by` scan breaks under pagination | **M** | Medium | → **deferred** (see §0) |
| **xG race timeline / match story** | — | minute-level events | ❌ none | L | **Fatal — would be fabricated. Rejected.** |
| **Form-guide W/D/L squares** | Universal shorthand | recent-form series per team | ❌ not in contract | L (core work) | Low once data exists → **deferred** |

---

## 5. Visual design direction

Refine "soccer × japan × zen" — don't replace it. The tokens are good; the composition is what's failing.

**Type & spacing (Phase A tokens):**
- Type ramp tokens: `--text-xs 12px / --text-sm 13px / --text-base 15px / --text-md 17px / --text-lg 20px / --text-xl 28px / --text-hero 34-40px (clamp)`. Hero numerals (score, big stats) go *lighter-weight at larger size* (Stripe pattern), slightly negative tracking above 20px only.
- Spacing scale: `--space-1..--space-8` on a 4px base; sweep ad-hoc rem values.
- Reading measure: body/fact text capped at `65ch`; the 1080px column stays for grids/tables only.
- `tabular-nums` already applied — keep; right-align all numeric table columns (already done).

**Surfaces & density:**
- Max one border level inside a panel. Notebook: `panel > list-row` (HIG grouped inset list: hairline separators between rows, one rounded container), killing `nb-group > nb-fact` double boxes.
- Cap the casual view at ~4 modules; everything else is a collapsed drawer.
- Dark elevation via the existing 3-step surface ladder, not heavier shadows.

**Color & signals:**
- Gold = actions + seal identity only. Team hues (`--home/--draw/--away`) only in probability segments and heatmap. Red/green only for *resolved* outcomes and deltas — never to moralize a probability (anti-pattern #4).
- Chips demoted to two meanings: *status* (sealed/scored/abstained/voided) and *fact taxonomy*. Sources become quiet text-links/popovers; legends become section headers; meta becomes plain text.

**Icons & labels:**
- Expand `icons.tsx` (calendar, pin, trophy, book, scale/balance, seal-check, sparkline, chevron-down) — inline currentColor SVGs, same 24×24/1.75 factory.
- Compact labeled values ("134 matches · since 1930") replace key-value word pairs ("sample 134 · base rate 61.2%") in casual; full pairs remain in expert meta.

**Numbers & language:**
- Whole-number % in bars/verdicts (both modes, identically); one decimal only in expert tables. Natural-frequency phrasing beside headline probabilities ("about 3 in 5").
- Humanized dates in casual ("since 1930", "5 days ago" — `relative()` exists); ISO in expert drawers only.

**Explicit avoid-list (from the brief, all honored):** no hero/marketing fluff, no decorative gradients beyond the existing faint background wash, no cards-in-cards, no pill inflation, "no retro-forecasting" stays visible, nothing implying AI generates or modifies probabilities — the AI panel's dashed/recessed subordination is untouched.

**Accessibility floor (existing, preserved + verified in Phase F):** WCAG 2.2 AA contrast (4.5:1), visible focus rings, `:focus-visible` styling, skip link, reduced-motion blocks, per-cell heatmap labels, `aria-pressed` toggles, 44px hit targets on new controls, keyboard-operable accordions/popovers (native `<details>`/`<summary>` + focus management).

---

## 6. Implementation plan (phased, file-level)

Order: **A → B → C** are the spine (sequential). **D and E** can proceed in parallel after C. **F** gates the merge of every phase (checklist per phase) and lands its infra early, right after A.

### Phase A — Design-system cleanup & layout primitives (S/M)
- `ui/src/index.css` — add type-ramp + spacing tokens; reorganize sections; add `.measure` (65ch), `.stat-tile`, `.trust-strip`, `.insight-row`, `.drawer` styles; sweep pill/chip usage.
- `ui/src/components/primitives.tsx` — extract `Stat` from ForecastDetail into a shared `StatTile`; add `TrustStrip`, `InfoPopover`, `MetaLine`.
- New `ui/src/components/disclosure.tsx` — accessible `<details>`-based `Drawer` (animated, reduced-motion-aware, expert-mode-aware default-open).
- `ui/src/components/icons.tsx` — new icons listed above.
- `ui/package.json` — add **vitest** (pure-function tests only: `lib/insights.ts`, `lib/format.ts` humanizers) and **Playwright** scaffolding (used from Phase B on).
- Probability formatting decision lands here: `lib/format.ts` gains `pctWhole()`; `ProbabilityBar` switches (both modes).

### Phase B — Match header & Match Detail redesign (M)
- New `ui/src/components/MatchHeader.tsx` — shared by both detail views: status → teams hero → single meta line; `match_id` removed from header (moves to provenance drawer).
- `ui/src/views/MatchDetail.tsx` — hero final score for played matches; retro-forecast truth becomes a trust-strip row + ⓘ; seal-action panel keeps its honest eligibility copy.
- `ui/src/views/ForecastDetail.tsx` — adopt MatchHeader + trust strip; per-panel disclaimer sentences collapse into the strip's popovers.

### Phase C — Notebook redesign & insight cards (M/L)
- New `ui/src/lib/insights.ts` — pure deterministic "top 3" selector (predictive > context, never coincidence; then specificity desc, sample_n desc, freshness non-stale, id tie-break). Vitest-covered. Documented in code + docs-site.
- `ui/src/components/CommentatorsNotebook.tsx` — grouped inset list rows; rate bar per fact (when `base_rate` non-null); humanized date ranges; sources → popover; per-fact meta behind row disclosure; coincidence quarantine preserved (dashed group + "for the pub" note, stated once).
- New `ui/src/components/InsightCards.tsx` — the "3 things to know" module, labeled "chosen by fixed rules — not by AI".
- `ui/src/views/MatchDetail.tsx` / `ForecastDetail.tsx` — mount InsightCards above the notebook.

### Phase D — Analytics artifacts (M)
- `ui/src/views/ForecastDetail.tsx` — xG `StatTile`s; casual most-likely-score line with natural frequency; confidence badge (uncertainty + measured calibration copy).
- `ui/src/components/ScoredPanel.tsx` — lifecycle strip (sealed → kickoff → scored); Stripe-anatomy metric tiles.
- `ui/src/components/ReliabilityDiagram.tsx` — add a `Sparkline` variant export.
- `ui/src/views/PredictionLedger.tsx` — plain-words calibration sentence + sparkline above the chains table; empty state per Stripe pattern ("Forecasts you seal before kickoff appear here…" + Generate action link).
- `ui/src/views/EvaluationSummary.tsx` — same calibration sentence idiom; table polish only.

### Phase E — Expert drilldowns & provenance (M)
- `ui/src/views/ForecastDetail.tsx` — Model & versions, Derived markets, Calibration context move into `Drawer`s (expert default-open).
- `ui/src/components/Provenance.tsx` — receipt idiom (source → sha256 → retrieved → license), inside a Drawer; gains the demoted `match_id`/`artifact_id`.
- `ui/src/components/SealStamp.tsx` — stays visible (it's the product); hash rows tightened.
- `ui/src/lib/hooks.ts` — `useForecastMode` consumed by MatchDetail + notebook density.

### Phase F — Visual QA, tests, docs (M, starts after A, gates each phase)
- New `ui/playwright.config.ts` + `ui/tests/` — screenshot tests: 6 routes (matchday, search, match played/forecast, forecast casual/expert, ledger, eval) × 375/768/1280 × dark (light on forecast + matchday); overflow assertion (`document.documentElement.scrollWidth <= innerWidth`); axe-core pass on the two detail pages; mock-data mode (exists) makes runs hermetic.
- `.github/workflows/ci.yml` — ui job grows `npm run test` (vitest) + `npm run test:e2e` (Playwright, chromium only).
- `docs-site/src/content/docs/casual-vs-expert.md` — update for drawers, whole-number bars, insight cards, MatchDetail mode support.
- `docs-site/src/content/docs/matchday.md`, `prediction-ledger.md` — refresh screenshots; `ui/screenshots/` regenerated.

---

## 7. Acceptance criteria (objective)

1. **No horizontal overflow** at 375, 768, 1280 px on all 6 tested routes (Playwright assertion, CI-enforced).
2. **10-second casual read:** at 1280×800, the casual match view shows ≤4 modules and ≤40 words of body copy above the fold; no mono hash, ISO timestamp, or registry jargon rendered in casual default (Playwright text assertions).
3. **Expert reachable, not dominant:** every expert artifact reachable in ≤2 interactions from the match page; all drawers collapsed in casual mode.
4. **Provenance adjacency:** every displayed statistic retains source/sample/seal-time within its own module (fact rows keep source popovers; forecast keeps trust strip + seal stamp).
5. **Contract intact:** probability bar byte-identical between modes (existing rule, now at whole-number precision); heatmap W/D/L totals still reproduce the 1X2 (existing on-load coherence check untouched); AI panel remains recessed/dashed/off-by-default; no UI path routes AI output into a number.
6. **Truth not hidden:** "no retro-forecasting" and "sealed before kickoff" visibly rendered (trust strip) on every match/forecast view — Playwright text assertion.
7. **A11y:** axe-core no serious/critical violations on both detail pages; keyboard-only walkthrough of drawers/popovers/toggle documented in the phase handoff.
8. **No regression in existing gates:** `ui` typecheck + build, core pytest, license-isolation, sidecar smoke all green; vitest + Playwright added to CI and green.

---

## Implementation status (landed)

Phases A, B, C, and the E-slice **shipped** in this cycle; F shipped its unit-test gate. Verified in the running app (mock data) across dark/light themes, Casual/Expert, goal and outcome model families, and desktop/tablet/mobile — no horizontal overflow at 375/768/1280, no console errors.

- **A** — `index.css` type-ramp + 4px spacing tokens, `.measure`, `.trust-strip`, `.stat-tile`, `.rate-bar`, `.drawer`, `.insight-*`, aligned `.meta-line`; `format.ts` gained `pctWhole`, `largestRemainder`, `inWords`, `sinceYear`, `yearSpan`; new primitives `MetaLine`, `TrustStrip`, `InfoPopover`, `StatTile`, `RateBar`; new `disclosure.tsx` `Drawer`; `ProbabilityBar` → whole-number labels that sum to 100.
- **B** — new `MatchHeader.tsx` (teams hero, one meta line, `match_id` demoted); `MatchDetail` hero final score + "No retro-forecast" trust strip; `ForecastDetail` adopts the header + a `ForecastTrustStrip`, per-panel disclaimers collapsed into ⓘ popovers. A pre-existing header overflow at ≤640px was fixed (nav wraps below brand/tools).
- **C** — new pure `lib/insights.ts` top-3 selector (vitest-covered); `InsightCards.tsx` ("chosen by fixed rules · not AI"); Commentator's Notebook restyled to a grouped-inset list with rate bars, humanized `1930–2026` spans, and a source ⓘ popover instead of mono pack-id chips.
- **E-slice** — Model & versions, Outcome/goal summaries, Provenance & inputs, and Calibration moved into `Drawer`s (open in Expert, collapsed in Casual); `Provenance` restyled as a receipt and now holds the demoted match/artifact ids.
- **F (partial)** — vitest added; `format.test.ts` + `insights.test.ts` (14 tests) wired into the `ui` CI job before build.

### Second cycle (also landed)

- **Insight ordering → closest-to-fixture first.** `lib/insights.ts` now ranks by scope (head_to_head → match → team → competition), then specificity, then predictive-before-context, then sample/id — so a head-to-head record leads the "Three things to know" cards. Tests + docs updated.
- **Tidy.** Matchday mini-bars round by largest-remainder (sum to 100); `ScoredPanel` migrated to the shared `StatTile`; dead CSS removed (`.md-final`, `.casual-detail`, `.metric*`).
- **"What moved" box.** On a re-sealed forecast, the Re-sealed callout shows per-outcome line movement (was → now, ▲/▼ points) from the earlier seal — deterministic, deltas sum to zero, green-up/red-down (a delta, not a hit/miss verdict). Reuses the already-fetched forecast list, no extra request.
- **Reading comfort.** A header "Aa" popover with Theme (Light/Dark/**Warm** low-blue palette), Text size (4 steps scaling root font-size), Line spacing, and Contrast — root CSS vars + `data-*` on `<html>`, applied before paint by an inline script in `index.html`, persisted, and defaulting Contrast on under `prefers-contrast: more`. Warm is a **dedicated hand-tuned palette**, not an overlay (overlays silently break contrast and axe can't see them). Copy is honest: "warm tones for comfortable evening reading", never "reduces eye strain".
- **Playwright + axe in CI.** `ui/tests/` — overflow assertion (`scrollWidth ≤ clientWidth`) over 7 routes × 375/768/1280, and `@axe-core/playwright` on the detail pages across all three themes, failing on serious/critical. Wired into the `ui` CI job (`npx playwright install --with-deps chromium && npm run test:e2e`). Authoring these caught a real WCAG miss: the probability-bar segment labels failed 4.5:1 in the light/warm themes (dark label on theme-darkened accents) — fixed with theme-independent bright segment fill tokens (`--seg-home/draw/away`).

**Still deferred:** form-guide W/D/L squares (needs a core recent-form series) and team crests/colours (no data, licensing).

## 8. Final recommendation

Do **A → B → C** as one arc (the visible transformation), with F's test scaffolding landing immediately after A so B and C merge behind screenshot coverage. D and E follow in either order or in parallel. Defer the deferred-table items until their data exists. Total scope is deliberately composition-and-primitives, not a rebrand: same tokens, same zero-dependency stack, same contract — the app just stops explaining itself in paragraphs and starts showing itself in structure.
