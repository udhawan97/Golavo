# Phase 8 handoff — Exact-score distribution + Casual/Expert presentation

**Base SHA:** `68baed3` (v0.1.0 tagged; tree clean at start).
**Lane:** `friendly-helper-claude/golavo-phase-8-ea9cbb`, landed on `main` in verified merges.
**Reviewer:** Codex.

The goal was to surface the exact-score distribution the sealed model **already implies** — as an
honest distribution with a tail bucket and explicit abstention/missing states — and add Casual vs
Expert presentation over the **same** sealed numbers. The non-negotiable was coherence: never
display a matrix the sealed 1X2 and expected goals do not imply, enforced by a machine check.

## What shipped

- `core/golavo_core/score_matrix.py` — pure matrix module: `build_score_matrix`, marginal/mean
  helpers, and the coherence checkers (`stored_coherence_violations`, `assert_stored_coherent`,
  `assert_model_coherent`).
- `core/golavo_core/models/candidates.py` — `Prediction` gains an optional `matrix`; `PoissonModel`
  integrates to `SCORE_MATRIX_RESOLUTION = 20` and derives its sealed 1X2 from that same matrix.
- `core/golavo_core/artifacts.py` — `seal_forecast` attaches `forecast.score_matrix` for goal
  families (proving model-level coherence first); `validate_artifact` enforces stored coherence on
  **every load**.
- `docs/contracts/forecast_artifact.schema.json` — additive `ScoreMatrix` (optional on `Forecast`);
  schema stays `0.2.0`.
- `scripts/generate_sample_artifacts.py` — Poisson fixtures now carry a coherent matrix; elo/
  abstained carry none. Regenerated 8 fixtures + UI mocks + calibration mock.
- `core/golavo_core/evidence.py` — top-3 scorelines + grid cap + tail enter `allowed_numbers`
  (with engine/snapshot source ids) plus deterministic scoreline facts; guarded so non-matrix
  bundles are byte-identical.
- UI: `lib/summary.ts` (band-generated verdict), `components/ScoreMatrixHeatmap.tsx`,
  `lib/hooks.ts` `useForecastMode`, and a rewritten `views/ForecastDetail.tsx` with the
  Casual/Expert toggle; additive `ScoreMatrix` contract type; `index.css` additions.
- Tests: `core/tests/test_phase8_score_matrix.py` (27).
- Docs: `methodology/prediction.md` (exact-score + coherence), `casual-vs-expert.md` (rewritten to
  the shipped design), README + CHANGELOG, this handoff.

## Matrix representation & the N / tail choice

`score_matrix` (all values are probabilities in `[0,1]`):

```jsonc
{
  "max_goals": 7,          // display cap N — concrete scorelines 0..7 per side
  "resolution": 20,        // internal integration resolution the tail was computed from
  "grid": [[...], ...],    // (N+1)×(N+1); grid[i][j] = P(home=i, away=j)
  "tail": { "probability": .., "home": .., "draw": .., "away": .. },  // cells with a side > N
  "most_likely": { "home": h, "away": a, "probability": p },
  "total_probability": ~1.0
}
```

- **N = 7.** Internationals and the top-5 leagues almost never see a side score more than seven; the
  tail beyond 7 is `< 1%` for realistic rates (`0.03%` on the sample fixtures). Everything beyond
  folds into **one** `8+` bucket, **decomposed by outcome** so W/D/L reconstruct exactly (no
  aggregated corner is left un-attributable).
- **Grid + tail is an exact partition of the model matrix** — no mass created or dropped.
- Cells stored to 9 dp; drift over the grid is `< 1e-7`.

## The coherence proof (the crux)

Everything — sealed probs, expected goals, and the grid — is derived from **one** matrix
integrated to 20 goals/side (truncation `< 1e-7` even at the rate clip of λ=5). Coherence is then
two machine-checked guarantees:

1. **Artifact-level** (`validate_artifact`, runs on every load): `grid + tail` win/draw/loss
   marginals reproduce `forecast.probs` within `1e-5`; `grid + tail` sums to 1; the tail
   decomposition reconciles; `most_likely` is the grid argmax. A hand-edited/incoherent grid is
   rejected — see the tamper test.
2. **Model-level** (`assert_model_coherent`, at seal time + in tests): the matrix mean reproduces
   `forecast.expected_goals` within `1e-4`, and re-deriving the model yields a byte-identical grid.
   An incoherent matrix **aborts the seal**.

`core/tests/test_phase8_score_matrix.py` covers, per Poisson family: matrix present + shaped;
`grid + tail` reproduces the sealed 1X2 (artifact-only); the re-fitted model reproduces probs +
expected goals and the identical grid; byte-identical re-seals; a small, decomposed tail. Plus:
elo/climatological seals carry no matrix; an abstained goal-family seal carries no matrix; every
sample matrix is coherent; a legacy `0.1.0` no-matrix artifact still validates; a one-cell tamper
is rejected; and `build_score_matrix` is an exact partition on a seeded random matrix. **Tolerances**
(`PROB 1e-5`, `GOALS 1e-4`) are documented in `score_matrix.py` and `methodology/prediction.md`;
before the seal is written the reproduction is exact to `~1e-12` — the tolerances only cover the
six-decimal quantisation of the stored probs.

## Calibration approach

Golavo applies **no post-hoc probability transform** to a seal; its "calibration" is the empirical
reliability ledger (`golavo_core.calibration`), not a re-scaler. So the grid and the 1X2 are both
raw outputs of the same fitted model — there is nothing that could be applied to one and not the
other, and no place they can desync. This is stated in the methodology; if a transform is ever
added it must act on the joint distribution and re-derive the marginals, and the coherence checks
would catch asymmetric application. The internal resolution was raised from 10→20 to make the model
self-consistent (matrix mean == raw rate to `~1e-6`); no real seals existed yet (ledger empty), so
this changed no committed artifact.

## Casual / Expert behaviour

A persisted toggle (top-right, hidden when abstained). **The verdict bar + its plain-language
headline are identical in both modes — depth never changes displayed certainty.**

- **Casual**: verdict bar + one band-generated sentence (`lib/summary.ts`, a pure function of the
  sealed numbers — NOT AI; bands documented in `casual-vs-expert.md`) + a few cited sealed-number
  facts labelled *"straight from the sealed model — no AI wrote these."*
- **Expert**: an accessible exact-score **heatmap** (real `<table>` with row/col `scope` headers, a
  screen-reader `<caption>`, tabular numerals, the most-likely scoreline outlined + starred, heat
  tint mixed over the surface so text stays legible in both themes, CSS-only motion) with the
  decomposed tail, the model's spread (most-likely, expected goals, tail), model/feature versions,
  and calibration context linking to the ledger.
- **Honest states**: goal-less families show "this model forecasts outcomes, not goals — no grid";
  abstained seals show no toggle and no grid. Never a fabricated grid.
- **AI stays subordinate** in both modes (recessed, off by default, below the sealed numbers).

## Live verification

`npm run build` (tsc + vite) is green. Verified in the browser preview across: Poisson sealed
(Casual + Expert, **dark and light** theme — heatmap contrast holds in both), elo sealed (honest
"no distribution" note), and abstained (no toggle, no grid); no console errors. Coherence is visible
in the render — e.g. the draw diagonal (`8.2 + 12.8 + 5.0 + 0.9 ≈ 26.9%`) reproduces the `27.0%`
draw bar. The Expert grid as rendered (Poisson `1–1` most likely, starred):

```
Home↓ · Away→   0      1      2      3      4      5     6   7
0             8.2%  10.3%   6.4%   2.7%   0.8%   0.2%   —   —
1            10.3%  12.8%★  8.0%   3.3%   1.0%   0.3%   —   —
2             6.4%   8.0%   5.0%   2.1%   0.7%   0.2%   —   —
...           (rows 6–7 all —; 0.0% beyond 7 goals a side)
```

## AI fold

The evidence bundle enumerates the top-3 scorelines (home goals, away goals, probability each), the
grid cap, and the tail as `allowed_numbers`, plus deterministic scoreline facts bound to them. The
AI may now cite "most likely 1-1 at 12.6%", but the numeric whitelist still governs: every digit
must equal a referenced number's exact `display`, so a fabricated `3-0 at 40%` is rejected
(verified: unsupported tokens `['3','0','40%']`). Non-matrix bundles are unchanged.

## Honest gaps (still no open source)

- **Club goalscorers, corners, xG** — no open feed at all; not attempted. martj42 ships goalscorers
  for **internationals only** (already used by the Phase 7 notebook, not by the score grid).
- **Likely goalscorers (internationals-only, the Phase 8 stretch)** — deferred. The team-goal
  coherent allocation (player share × the matrix, Σ shares = 1) is designed but not built; shipping
  the coherent matrix first was the right call, and there is a clean interface (`score_matrix` +
  per-team share) to add it behind later without touching the sealed grid.
- **No score matrix for elo/climatological** — by design (they model no goal process); shown as an
  honest absence, not a gap to paper over.
