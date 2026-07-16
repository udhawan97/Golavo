# World Cup 2026 Retrospective — design

Date: 2026-07-16
Status: approved for planning

## Why

After the 2026 World Cup final on 19 July, the index contains **zero** forecastable
fixtures. Every club league ended in May, the 2026-27 fixture lists are not published
upstream, and internationals do not resume until September. For roughly six weeks the
forward loop — the product's thesis — has nothing to run on.

The tournament that just finished is the richest thing the app owns: 104 matches, 48
teams, 94 exact kickoffs, all in the committed index. This surface makes those six quiet
weeks worth opening the app for, using data already present.

## What it is

One view at `/lab/worldcup-2026` answering two questions that must never be conflated:

1. **Story** — "What would the app have told you before each match, and where was it
   most wrong?" Per-match forecasts, each trained only up to its own kickoff.
2. **Trust** — "Do these models actually have skill?" The existing WC2026 evaluation
   fold, reused as-is.

## Non-goals (v1)

- **No sealed-pick overlay.** Deferred. The local ledger likely holds at most the final,
  which is too thin to carry a layer. See "Deferred" below.
- **No new committed artifact.** Computed on demand, cached. See "Why not frozen".
- **No AI narration.** The story is ranked evidence, not prose. Narration is a separate
  ladder with its own rules.
- **No other tournaments.** The window is hard-coded to WC2026. Generalising is a later
  decision, driven by a second real use case.

## The honesty contract

This is the requirement the whole design serves. Two claims sit on one page, and they are
**not** the same claim:

| Layer | Claim | Training cutoff | Source |
|---|---|---|---|
| Story | "What the app would have told you before this match" | per-match, `kickoff − 1s` | new |
| Trust | "Could the models have called the tournament from outside?" | once, pre-tournament | existing WC2026 fold |

Rules:

- **Neither layer is a record.** Nothing here was called in advance by anyone. Every
  number on this page is a backtest. The page must say so where a reader cannot miss it,
  in the app's own vocabulary — not a footnote.
- **Dropping the sealed-pick layer raises the labelling burden.** With a real seal beside
  them, "backtest ≠ seal" is self-evident by contrast. Alone on the page, backtests can
  be mistaken for a track record. v1 must carry that weight in explicit copy.
- **Never merge the two layers' numbers.** They have different cutoffs and answer
  different questions. No blended "overall accuracy" across them.
- Reuse `ledger_status: "never_persisted_or_scored_as_a_seal"` semantics — the existing
  vocabulary for exactly this distinction.

## Why on-demand, not frozen

A frozen artifact built from the bundled pack goes stale the moment a user runs an
in-app approved-source refresh: their index moves, the artifact does not, and the page
would quietly describe a different dataset than the one they hold. That is the precise
failure mode this app refuses.

Computing from the active pack is consistent by construction. The cost (~2.7 min for 104
matches × 5 families, measured) is paid once per pack, not once per open, because the
result is cached against the index fingerprint.

## Architecture

```
index ──> retrospective.compute(window) ──> per-match rows ──> cache ──> API ──> UI
                                         ↘ existing WC2026 fold ─────────────> trust panel
```

### `core/golavo_core/retrospective.py` (new, pure)

Given a frame and a tournament window, returns per-match rows. No I/O, no cache, no
network — testable standalone.

Per row: `match_id`, `kickoff_utc`, teams, per-family probabilities, actual result, and
per-match log loss.

- Cutoff is `kickoff − 1s` per match, reusing the existing leak-safe convention in
  `analysis.py`. This gives each forecast **seal semantics**: exactly what the app would
  have produced had it been asked at that moment.
- **Four families, not five.** `bivariate_poisson` is numerically identical to
  `poisson_independent` across every recorded fold; showing both implies two independent
  opinions where there is one.
- Incomplete matches are skipped with a typed reason, never scored.

### `server/golavo_server/retrospective.py` (new)

- Orchestrates via `jobs.py` (progress + cancellation, the v0.7.0 pattern).
- Two-level cache mirroring `analysis.py`: L1 in-memory LRU, L2 disk, content-addressed
  by `(tournament_id, index fingerprint, schema version)`. Self-invalidates on any index
  change, including a user refresh.
- The cache is an **accelerator, never a dependency**: every read/write swallows I/O
  errors and falls back to recompute.
- Route: `GET /api/v1/tournaments/worldcup-2026/retrospective` → typed job handle;
  poll for progress; result on completion.

### `ui/src/views/WorldCupRetrospective.tsx` (new)

Route `/lab/worldcup-2026`, reached from Model Lab.

- **Story**: matches ranked by log loss — "most surprised" descending, "most confident
  and right" ascending. Named plainly as per-match log loss, not dressed up as a
  proprietary "surprise score".
- **Trust**: the existing fold report card with its bootstrap intervals, labelled as
  trained once, pre-tournament.
- Progress UI during first compute, reusing the existing job-polling components.

### `docs/contracts/tournament_retrospective.schema.json` (new)

Validated in tests like the other 27 contracts.

## Ranking semantics

"Biggest upset" = per-match log loss, ranked descending. This is a real, standard
measure. It gets named as what it is in the UI. No invented composite.

**Ranked on `dixon_coles` specifically** — the app's own `DEFAULT_FAMILY` in `seal.py`.
The story layer's claim is "what the app would have told you", so the ranking must follow
the family the app would actually have sealed with. The other three families appear on
each row for comparison but do not drive the order. Ranking on a cross-family average
would describe a forecast the app never makes.

## Error handling

| Case | Behaviour |
|---|---|
| Tournament incomplete (final unplayed) | **Typed partial state, not an error.** Ships today at 102/104 with "final not yet played"; completes itself on Sunday with no code change. |
| Job cancelled or failed | Typed states — `jobs.py` already models these. |
| Cache read/write failure | Recompute. Never a dependency. |
| Index lacks the WC2026 window | Typed `unavailable` with a reason, mirroring `OutlookUnavailable`. Never an empty object the UI could read as zero. |

## Testing

- **Leak safety (the one that matters).** Poison the frame with a post-kickoff row;
  assert per-match output is unchanged. Mirrors the guard added in
  `core/tests/test_outlook.py` on 2026-07-16, which caught a live leak of exactly this
  shape.
- **Cutoff correctness.** A match's forecast must not shift when a *later* match's result
  is added.
- **Determinism.** Same index → byte-identical rows.
- **Cache invalidation.** Changing the index fingerprint produces a fresh compute.
- **Contract.** Schema validation.
- **UI.** Both layers stay labelled and distinct; the backtest disclosure is present.

## Ships incrementally

The partial state is a feature, not a compromise: the view is useful today at 102/104 and
completes on its own when the final is played and the pack refreshed. It does not block
on the release decision.

## Deferred

- **Sealed-pick overlay.** Add once a real ledger exists to overlay — the natural trigger
  is the first tournament the user seals through. It restores the contrast that makes
  "backtest ≠ seal" self-evident, so it is a genuine improvement, not just a feature.
- **Generalising beyond WC2026.** Wait for a second real use case, likely Euro 2028 or a
  club season once fixtures exist.
- **Per-match narration.** Belongs to the AI ladder, under its own quarantine rules.

## Open risk

`_SEMIFINAL_START/_END` in `outlook.py:27` hard-codes a Jul 14–16 window and demands
exactly two matches. It is unrelated to this surface but shares the tournament, and a
post-tournament refresh could trip `OutlookUnavailable`. Worth checking after 19 July.
