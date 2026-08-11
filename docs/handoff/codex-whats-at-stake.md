# Codex prompt — "What's at Stake": match importance + run-in difficulty

**Status: SHIPPED in `97d4db4`** — implemented in-repo rather than handed to Codex.
`fixture_importance` and per-voice `expected_points` live in
`core/golavo_core/season_outlook.py`; the run-in table is in
`ui/src/components/SeasonOutlook.tsx`; the payload contract gained
`remainingFixture.importance` and `teamProbability.expected_points`. The prompt
below is kept as the design record. Phases 3–7 of
`docs/superpowers/specs/2026-08-11-whats-at-stake-design.md` are still open.

Two things landed differently from the plan below, both deliberate:

- **No "At stake" line on match cards / MatchDetail.** A season outlook fits two
  models and runs 30,000 simulations; firing that from every match view to
  annotate one fixture is the wrong trade. The swings are surfaced in the league
  view, where that simulation is already being run.
- **The run-in bands opponents by the outlook's own projected points**, not by a
  second fetch of the Elo ratings endpoint. One table, one voice, no cross-source
  join and no second provenance chain.

Copy everything below the line into Codex, run from the repo root.

---

You are implementing one display-analytics feature in **Golavo**, a local-first,
provenance-bearing football forecaster (Python core + FastAPI sidecar + React
UI in a Tauri shell). Read `CLAUDE.md` and `CONTEXT.md` first — they define the
domain words and the hard rules. The design you are implementing is
`docs/superpowers/specs/2026-08-11-whats-at-stake-design.md`. Do not widen its
scope.

## Feature summary

The season outlook at
`GET /api/v1/analytics/competitions/{id}/season-outlook` already runs a seeded
10,000-iteration simulation of every remaining fixture per voice
(`core/golavo_core/season_outlook.py`) and reports per-team title / top-4 /
relegation probabilities (`docs/contracts/season_outlook.schema.json`). You will
derive two things from those **same** runs — no extra simulation passes:

1. **Match importance.** While simulating, record per remaining fixture per
   iteration its 1X2 outcome, and per club its final-table flags (title,
   top_four, relegation) plus final points. Then, for each remaining fixture,
   for each of its two clubs, for each stake `s`:
   `swing(s) = |P(s | club wins this fixture) − P(s | club loses this fixture)|`,
   club importance = max swing over stakes, fixture importance = max of the two
   clubs. Probabilities conditioned on a branch with **fewer than 200
   iterations must abstain** — emit an insufficient-coverage state, never a
   number ("unknown is a rendered state" is a house rule).
2. **Expected points.** Per club, the mean simulated final points — computed in
   the same pass.

Surface both:
- **LeagueView** (`ui/src/views/Leagues.tsx` area): a "Run-in" section — each
  club's remaining fixtures as chips colored by opponent strength band using
  the existing Golavo Elo (`/api/v1/ratings/club/{competition_id}`), an
  expected-points column, and an importance badge per fixture.
- **Matchday cards + MatchDetail**: an "At stake" line for fixtures covered by
  an outlook (e.g. "Title swing: 23 points of probability for Arsenal"),
  carrying the outlook's provenance ids like every other displayed fact.

## Hard rules (CI enforces most; violations are rejected, not negotiated)

1. The statistical engine owns every probability — the UI must display, never
   compute or adjust, importance numbers. All math lives in
   `core/golavo_core/season_outlook.py` (or a sibling pure module).
2. Every displayed fact carries a source id. Reuse the outlook payload's
   `provenance` for the new fields.
3. This feature is **display-only**: never a model input, never enters seals,
   settlement, or calibration. Do not touch `core/golavo_core/facts/` (adding
   fact families widens the multiple-comparison budget — out of scope).
4. No betting vocabulary anywhere — code, copy, tests, docs. Allowed:
   "importance", "at stake", "swing", "probability". Forbidden: "odds",
   "value", "edge", "units", "locks".
5. Determinism: same seed → byte-identical importance output. No wall clock,
   no randomness outside the existing seeded RNG. Do not add dependencies, do
   not touch `packs/`, `data/index/`, or `core/pyproject.toml` pins.

## Contract changes (additive only)

- `docs/contracts/season_outlook.schema.json`:
  - `$defs.remainingFixture` gains optional `importance`: per-club object with
    per-stake swings, the club importance, fixture importance, and branch
    coverage counts (wins/draws/losses iteration counts) so abstention is
    auditable; plus an explicit `status: "ok" | "insufficient_coverage"`.
  - `$defs.teamProbability` gains optional `expected_points`.
- Follow the Phase-8 precedent (`docs/handoff/codex-phase8.md`): additive
  optional fields keep the schema version unless
  `scripts/tests/test_contract_versions.py` or
  `server/tests/test_contract_drift.py` forces a bump. Do **not** create a new
  schema file (that would trigger OWNERS registration — unnecessary here).
- Mirror the new types **by hand** in `ui/src/lib/contract.ts` — there is no
  codegen; drift is caught by `server/tests/test_contract_drift.py`.

## Repo gotchas that will bite you

- **Server caches leak across tests.** If a server test repoints `analytics` /
  `outlook` / `ratings` state at a tmp fixture, it needs an
  `@pytest.fixture(autouse=True)` calling the module's `reset_cache()` — copy
  the pattern at the top of `server/tests/test_matches_api.py`, or your test
  will pass alone and fail in suite order.
- **UI test split is load-bearing.** Vitest only collects
  `ui/src/**/*.test.{ts,tsx}`; anything in `ui/tests/` runs under Playwright
  only. A test in the wrong directory silently never runs.
- **Component tests render to a string**: `createElement` +
  `renderToStaticMarkup` from `react-dom/server`, assert on HTML, node
  environment — no jsdom unless the component truly needs state/effects (then
  opt in per file with `// @vitest-environment jsdom`).
- **Lint is oxlint with `--deny-warnings`** (`cd ui && npx oxlint` via
  `make lint`); any warning fails CI. `exhaustive-deps` cannot be inline-
  suppressed — restructure (hoist `const { x } = obj` locals) instead.
- The FastAPI routes all live in `server/golavo_server/main.py` (~100 routes,
  one file — deliberate). Compute in a service module, wire thinly there.
- `calibration` lazy-imports numpy for a reason; don't add heavy imports to
  module scope in server files.

## Tasks, in order (TDD: red test first per task)

1. **Core recording pass** — extend the season simulation to collect per-
   fixture outcomes and per-club final flags/points per iteration. Test:
   synthetic 3-team round-robin, seeded, hand-checkable partition counts.
2. **Importance math** — pure function from the recorded partitions to the
   importance structure, including the <200-iteration abstention branch and
   the deterministic-under-seed property. Tests: swing math against hand
   computation; abstention; determinism (two runs, same seed, equal output).
3. **Expected points** — mean simulated points per club, same pass; test vs
   hand computation on the synthetic league.
4. **Payload + contract** — attach both to the outlook payload; update the
   JSON Schema (additive) and `ui/src/lib/contract.ts`; run
   `pytest scripts/tests/test_contract_versions.py` and
   `server/tests/test_contract_drift.py`.
5. **Server test** — outlook endpoint returns the new fields against the tmp
   fixture, with the autouse cache-reset pattern.
6. **UI: Run-in section** in the league view — chips by opponent Elo band,
   expected points, importance badges; string-render component test.
7. **UI: At-stake line** on match cards / MatchDetail for outlook-covered
   fixtures, with provenance ids; string-render test. Abstained fixtures show
   the insufficient-coverage state, never a dash-for-a-number.
8. **Docs** — one docs-site page section (remember: the Astro sidebar is
   hand-authored — a new page needs a sidebar entry; prefer extending the
   existing competition-analytics page), CHANGELOG entry.

## Definition of done

- `make test` green (~840 Python tests), `cd ui && npm test` green,
  `npm run typecheck` green, `make lint` green, `make validate` green.
- No changes under `packs/`, `data/index/`, `data/sources/`,
  `core/golavo_core/facts/`, or to dependency pins.
- Same seed twice → identical importance JSON (add this as a test, not a
  claim).
- Conventional Commits, signed off (`git commit -s`), e.g.
  `feat(analytics): derive match importance from season outlook runs`.
