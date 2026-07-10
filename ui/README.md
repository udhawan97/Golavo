# golavo-ui — Forecast Audit Workbench

The Golavo interface: React + TypeScript + Vite. **Apache-2.0.**

A beautiful, honest, **read-only** window onto sealed forecast artifacts. A
forecast is sealed *before* kickoff — with its model version and input-data
hashes — and scored *after* full time. The workbench never edits an artifact,
never invents data, and labels its data source plainly. This is **not** a
betting product.

```bash
npm install
npm run dev        # http://127.0.0.1:5173  (mocks by default)
npm run build      # tsc --noEmit && vite build
npm run typecheck  # tsc --noEmit
```

## Data source

The UI reads from a local `golavo-server` **only if** `VITE_GOLAVO_API` is set
at build/run time; otherwise it runs entirely on bundled sample artifacts.

| View | Endpoint (when `VITE_GOLAVO_API` set) | Mock fallback |
| --- | --- | --- |
| Matchday list | `GET {base}/api/v1/forecasts` | `src/mocks/forecasts/*.json` |
| Forecast detail | `GET {base}/api/v1/forecasts/{id}` | same, by id |
| Evaluation | `GET {base}/api/v1/eval/summary` | `src/mocks/eval-summary.json` |

```bash
# Point at a running server instead of mocks:
VITE_GOLAVO_API=http://127.0.0.1:8787 npm run dev
```

No other endpoints are assumed to exist. Responses are validated against the
frozen contract shape at runtime (`src/lib/api.ts`); contract drift surfaces as
a visible error rather than silently rendering malformed data.

## Views

1. **Matchday** — forecasts newest-first; status chips (sealed / scored /
   abstained / voided), competition, kickoff (UTC), neutral-venue mark,
   superseded mark, W/D/L bar.
2. **Forecast detail** — probability bar with uncertainty tier; **seal stamp**
   (sealed-at, horizon, model id/family/version, code git sha, seed, params
   hash, payload sha256); **provenance** (every input snapshot, copyable
   hashes); abstained state renders its reason with no probabilities.
3. **After the whistle** (scored) — sealed probabilities beside the full-time
   result, prob assigned to outcome, log loss + Brier, and a *"the seal never
   changed"* framing with the supersession link when present.
4. **Evaluation** — per-fold table (model × log loss / Brier / ECE / RPS, log
   loss as the headline) and a hand-rolled SVG reliability diagram.

Every view implements empty / loading / partial / abstained / voided states.

## Architecture

```
src/
  lib/contract.ts   Types mirroring the frozen contract v0.1.0 (exactly)
  lib/api.ts        VITE_GOLAVO_API fetch, else bundled mocks; runtime guards
  lib/format.ts     percentages (1 dp), UTC timestamps, hash truncation
  lib/hooks.ts      hash router, async loader, theme, clipboard
  mocks/            9 ForecastArtifact JSONs + 1 EvalSummary (lazy-loaded)
  components/       primitives, SealStamp, Provenance, ScoredPanel,
                    ReliabilityDiagram (hand-rolled SVG), Layout, states
  views/            MatchdayList, ForecastDetail, EvaluationSummary
```

Dependencies are React + React-DOM only. No chart library, no router library,
no CSS framework — the reliability diagram is hand-rolled SVG and the initial
JS is ~56 KB gzip.

## Brand & accessibility

Soccer × japan × zen: dark theme default (light supported via the header
toggle), Trophy Gold accent, hinomaru red used sparingly, tabular lining
numerals, monospace hashes. Respects `prefers-reduced-motion`, targets WCAG 2.2
AA contrast, full keyboard navigation with visible focus states.
