# What's at Stake — season-race features from the existing simulator

**Date:** 2026-08-11 · **Status:** proposed · **Author:** Claude (research: GitHub OSS survey + repo inventory)

## Why this feature set

A survey of high-star open-source football analytics projects (stars checked live
2026-08-11) looked for features that are (a) proven elsewhere, (b) buildable from
data Golavo already ships or from license-clean free sources, (c) not
betting-shaped. The strongest finding: the features with the best
confidence-to-cost ratio need **no new data at all** — they are derivatives of
the 10k-run season simulation that already powers
`/api/v1/analytics/competitions/{id}/season-outlook`.

### Inspiration survey (condensed)

| Project | Stars | License | What it proves |
|---|---|---|---|
| fivethirtyeight/data `soccer-spi` | 17.4k | CC-BY-4.0 (frozen) | Match **importance** metric; season forecast presentation |
| penaltyblog | 211 | MIT | Multi-rating systems (Pi/Massey/Colley), Dixon-Coles, backtest framing |
| mplsoccer | 533 | MIT | Bumpy (rank-over-time) charts, radar charts from aggregates |
| openfootball / footballcsv | 989 / — | CC0 | The fixture/result data Golavo already vendors |
| socceraction | 805 | MIT | Action-value analytics (needs event data — see exclusions) |
| kloppy | 538 | BSD-3 | Vendor-neutral data modeling (validates Golavo's pack design) |

Excluded honestly: **StatsBomb open-data** (custom license, registry-`rejected`;
P10 remains blocked on an owner ADR), **ClubElo / live SPI / eloratings /
FBref / Understat / soccerdata's scrape targets** (owner watch list in
`docs/handoff/open-data-feature-roadmap-2026-07.md` — "named so they aren't
re-litigated"), anything odds/betting-shaped (non-negotiable #5).

## Ranked plan (high-confidence, all free)

1. **What's at Stake — match importance** (this spec, phase 1). For each
   remaining fixture: how much the season-outcome probabilities (title / top-4 /
   relegation) of the two clubs swing between winning and losing it. Concept
   proven by FiveThirtyEight SPI's `importance` columns. Zero new data. **S/M.**
2. **The Run-In — remaining-schedule difficulty** (this spec, phase 1). Per
   club: remaining fixtures with opponent strength (existing Golavo Elo) and
   simulated expected final points. **S.**
3. **Rank trajectory (bumpy chart)** — league position per matchweek replayed
   from the index, projected continuation from the outlook. mplsoccer-proven.
   Follow-up phase. **S.**
4. **Ratings Council — Pi / Massey / Colley beside Elo** with a disagreement
   indicator. penaltyblog-proven (MIT; reimplement in-house, no new dep).
   Follow-up phase. **M.**
5. **Women's WC history facts** — roadmap #2; sole blocker is the men's-only
   filter at `core/golavo_core/facts/wc_history.py:53-56`; data already bundled
   in the isolated fjelstul pack. **S.**
6. **Frauen-Bundesliga overlay** — roadmap #5; `fbl1` shortcut verified
   populated; ODbL-isolated config change. **S.**
7. **P8 pack lane + per-match Wyscout artifacts** (roadmap #13, CC-BY-4.0
   verified) — the license-clean route to shot maps / pass networks; unlocks P9
   (SkillCorner, MIT). **L.**

## Phase-1 design (items 1–2)

### Core: importance from the runs we already simulate

`core/golavo_core/season_outlook.py` already simulates every remaining fixture
per iteration. Add a recording pass: per remaining fixture, per iteration, the
simulated 1X2 outcome; per club, per iteration, the final-table flags (title /
top-4 / relegation) and final points.

Per fixture, per club in it, per stake `s ∈ {title, top_four, relegation}`:

```
swing(s) = | P(s | club wins fixture) − P(s | club loses fixture) |
club importance = max over s of swing(s)
fixture importance = max of the two clubs' importance
```

This is the SPI definition restated over Golavo's own runs. Deterministic: same
seed, same partition. **Abstention rule:** a conditional branch with fewer than
`MIN_BRANCH_RUNS` (200 of 10k) iterations renders as an insufficient-coverage
state, never a number — "unknown is a rendered state" applies.

Expected points: per club, mean simulated final points. Same pass, no extra
runs.

### Contract (additive only)

`docs/contracts/season_outlook.schema.json`:
- `$defs.remainingFixture` gains optional `importance` (per-club stake swings +
  fixture score + coverage counts).
- `$defs.teamProbability` gains optional `expected_points`.
- Follow the Phase-8 precedent: additive optional fields, version stays `0.2.0`
  unless `test_contract_drift` / `test_contract_versions` forces a bump. No new
  schema file → no OWNERS registration needed.
- Mirror by hand in `ui/src/lib/contract.ts` (no codegen).

### Server

Computed inside the existing season-outlook build (module `analytics` /
`season_outlook` path); cached with the same epoch-guarded cache; no new
endpoint. Scenario endpoint untouched.

### UI

- **LeagueView**: a "Run-in" section — clubs × remaining-fixture chips colored
  by opponent Elo band, expected-points column, importance badge per fixture.
- **Matchday cards / MatchDetail**: an "At stake" line for fixtures whose
  competition has an outlook (e.g. "Title swing: 23 points of probability for
  Arsenal"), with the outlook's provenance/source ids.
- Copy rules: "importance", "at stake", "swing" — never "odds", "value",
  "edge", or any betting vocabulary.

### What this feature is not

Display-only analytics. Never a model input, never sealed, never settled, never
in calibration. No new fact families (no `family_size()` widening). No new
dependencies, no index change, no pack change.

### Testing

- Core: seeded determinism of importance; partition math on a synthetic
  3-team round-robin fixture; abstention below `MIN_BRANCH_RUNS`; leak-safety
  (`as_of` respected — importance only over genuinely remaining fixtures).
- Server: autouse `reset_cache()` fixture (copy `test_matches_api.py` pattern).
- UI: string-render component tests in `ui/src/**/*.test.tsx` (vitest glob);
  contract mirror covered by existing drift test.

## Alternatives considered

- **New `match_importance` contract + endpoint** — rejected: a new schema file
  triggers OWNERS + three-place version registration for what is one optional
  field on an existing payload.
- **Forced-scoreline scenario calls per fixture (3 × N sim runs)** — rejected:
  ~30× the compute for the same numbers the partition gives free.
- **538 SPI benchmark pack (CC-BY)** — deferred: owner watch list says
  excluded (archive-only); revisit only if the owner reopens it.
