# golavo-ui — the Golavo workbench

The Golavo interface: React + TypeScript + Vite. **Apache-2.0.**

A calm, honest, **local-first** window onto football intelligence. Open any match — past or
upcoming — for a leak-safe multi-model read (the **Match Cockpit**), seal a genuine pre-kickoff
prediction on the record, and audit the forward calibration in the **Model Lab**. The workbench
never mutates a sealed artifact, never invents data, and labels its data source plainly. This is
**not** a betting product — there is no odds framing anywhere.

```bash
npm ci
npm run dev        # http://127.0.0.1:5173  (bundled sample data by default)
npm run build      # tsc --noEmit && vite build
npm run typecheck  # tsc --noEmit
npm test           # vitest (unit)
npx playwright test  # e2e: no horizontal overflow + axe a11y, 3 themes
```

## Data source: mock by default, live when pointed at a server

The UI runs entirely on **bundled sample artifacts** unless `VITE_GOLAVO_API` is set at
build/run time. When it is set, every view reads the live `golavo-server`; otherwise each view
falls back to its mock under `src/mocks/`.

```bash
# Point at a running server instead of mocks (match the root README's port):
VITE_GOLAVO_API=http://127.0.0.1:8000 npm run dev
```

| Surface | Endpoint (when `VITE_GOLAVO_API` set) | Mock fallback |
| --- | --- | --- |
| Games home — recent + upcoming rails | `GET {base}/api/v1/matches/recent` | `src/mocks/matches.json` |
| Match Search | `GET {base}/api/v1/matches/search`, `/matches/competitions` | `src/mocks/matches.json` |
| Match Cockpit — match + eligibility | `GET {base}/api/v1/matches/{id}` | `src/mocks/matches.json` |
| Match Cockpit — model council | `GET {base}/api/v1/matches/{id}/analysis` | derived from mock rows |
| Commentator's Notebook (any match) | `GET {base}/api/v1/matches/{id}/notebook` | `src/mocks/notebooks/*` |
| Seal a forecast | `POST {base}/api/v1/matches/{id}/seal` | disabled in mock mode (honest note) |
| Sealed forecast list | `GET {base}/api/v1/forecasts` | `src/mocks/forecasts/*.json` |
| Forecast detail + facts | `GET {base}/api/v1/forecasts/{id}`, `/facts` | same, by id |
| Track record (calibration) | `GET {base}/api/v1/calibration` | `src/mocks/calibration.json` |
| Settle finished forecasts *(user-authorized network check)* | `POST {base}/api/v1/forecasts/settle` | disabled in mock mode |
| Backtests | `GET {base}/api/v1/eval/summary` | `src/mocks/eval-summary.json` |
| App/contract meta | `GET {base}/api/v1/meta` | synthesized (`forecast_source: sample`) |
| Fixtures awareness check *(opt-in)* | `GET {base}/api/v1/fixtures/check` | disabled in mock mode |
| AI Analyst Read *(optional)* | `POST {base}/api/v1/forecasts/{id}/narrative`, `/matches/{id}/narrative` | unavailable note in mock mode |

Responses are validated against the frozen contract shape at runtime (`src/lib/api.ts` /
`src/lib/contract.ts`): forecast/eval/calibration on **contract v0.2.0** (accepts 0.1.0), the
Match Cockpit analysis on **analysis 0.3.0**. Contract drift surfaces as a visible error rather
than silently rendering malformed data.

## Routes & views

Hash routing (`src/lib/hooks.ts`), no router library. Header nav is **Games · Leagues · Model
Lab**, plus Search, an **Aa** reading-comfort popover, and a Settings gear.

| Route | View | What it is |
| --- | --- | --- |
| `#/` (or `#/games`) | `GamesHome` | recent + upcoming rails, search entry, league chips — the landing surface |
| `#/matches` | `MatchSearch` | debounced search over the ~75k-match index; grouped internationals/club; honest badge states |
| `#/match/{id}` | `MatchDetail` | **Match Cockpit**: on-demand Replay (played) / Preview (scheduled) council, model-implied goals, score grid, Notebook, and the **Seal before kickoff** action for an eligible fixture |
| `#/forecast/{id}` | `ForecastDetail` | a sealed forecast — verdict bar, seal stamp, provenance, score matrix, scored/voided/superseded states, "what moved" re-seal deltas, insight cards |
| `#/leagues` | `LeaguesHub` | browse hub for domestic leagues, UEFA clubs + internationals |
| `#/league/{slug}` | `LeagueView` | one league's matches (historical backtest surface) |
| `#/lab` | `ModelLabHub` | the relocated audit surface hub |
| `#/lab/track-record` | `PredictionLedger` | the real forward calibration record |
| `#/lab/backtests` | `EvaluationSummary` | held-out chronological fold metrics + reliability diagram |
| `#/lab/methods` | `Methodologies` | why three of five families are one voice; abstention |
| `#/lab/forecasts` | `MatchdayList` | the sealed-forecast list |
| `#/settings` | `Settings` | version, appearance, Local intelligence (AI), opt-in fixtures check |
| `#/eval`, `#/ledger` | — | legacy redirects into `#/lab/backtests` / `#/lab/track-record` |

A malformed deep link segment is decoded safely and falls back to a not-found state; every view
implements loading / empty / partial / abstained / voided states.

## Architecture

```
src/
  lib/contract.ts   Types mirroring the frozen contract (v0.2.0; analysis 0.3.0)
  lib/api.ts        VITE_GOLAVO_API fetch, else bundled mocks; runtime contract guards
  lib/format.ts     percentages, UTC timestamps, hash truncation, plain-language glosses
  lib/hooks.ts      hash router, async loader, reading prefs, clipboard
  mocks/            sample forecasts, matches, calibration, eval summary, notebooks (lazy-loaded)
  components/       primitives, ModelCouncil, ScoreMatrixHeatmap, SealStamp, Provenance,
                    ReliabilityDiagram (hand-rolled SVG), Layout, ReadingComfort, states
  views/            GamesHome, MatchSearch, MatchDetail, ForecastDetail, LeaguesHub, LeagueView,
                    ModelLab, PredictionLedger, EvaluationSummary, Methodologies, MatchdayList,
                    Settings
```

Dependencies are **React + React-DOM only** — no chart library, no router library, no CSS
framework. The reliability and score-matrix views are hand-rolled SVG; mock data is
dynamic-`import()` split so it never weighs down the live build.

## Brand & accessibility

Soccer × japan × zen: dark theme default, light and a **warm low-blue** palette supported via the
header **Aa** popover (also reachable from Settings › Appearance). Trophy Gold accent, hinomaru
red used sparingly, tabular lining numerals, monospace hashes. Respects `prefers-reduced-motion`,
targets WCAG 2.2 AA contrast, full keyboard navigation with visible focus states. A Playwright +
axe-core gate checks no horizontal overflow and no serious a11y violations across all three
themes on every push.
