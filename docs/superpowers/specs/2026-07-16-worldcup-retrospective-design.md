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
   fold logic, recomputed against the active pack. No new scoring code.

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
| Trust | "Could the models have called the tournament from outside?" | once, pre-tournament | existing WC2026 fold, recomputed on the active pack |

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

**The same argument applies to the trust layer, and this is a correction to an earlier
draft of this spec.** The committed `docs/handoff/eval_summary.json` is frozen against the
*canonical* pack and already reports WC2026 at `n_matches: 97`, while the refreshed pack
has 102 completed. Reading the frozen fold would put 97 next to the story layer's 102 on
one page — two numbers disagreeing about the same tournament, which is the staleness this
design exists to avoid. The trust layer therefore calls `evaluate(active_pack_dir)` and
caches it on the same fingerprint. Measured at 30.5s, so on-demand is affordable.

Total first-compute budget: ~2.7 min (story) + ~31s (trust) ≈ 3.2 min, once per pack.

Both layers must resolve the **same** pack — the story reads the index frame, the trust
layer reads the pack directory. The server resolves the active pack via
`seal.resolve_pack_dir(...)` (runtime-refreshed → greatest-anchor → canonical). The
response must stamp which pack both layers used, so a reader can audit that they agree.

## Architecture

```
active pack ─┬─> index frame ──> retrospective.compute(window) ──> per-match rows ─┬─> cache ──> API ──> UI
             └─> evaluate(pack) ──> WC2026 fold report card ──────────────────────┘
```

One pack resolves both layers, so their match counts cannot drift apart.

### `core/golavo_core/retrospective.py` (new, pure)

Given a frame and a tournament window, returns per-match rows. No I/O, no cache, no
network — testable standalone.

Per row: `match_id`, `kickoff_utc`, teams, per-family probabilities, actual result, and
per-match log loss.

- Cutoff is `kickoff − 1s` per match, reusing the existing leak-safe convention in
  `analysis.py:421`. This gives each forecast **seal semantics**: exactly what the app
  would have produced had it been asked at that moment.

- **Use `analysis.py`'s cutoff exactly — do not invent a stricter one.** The story
  layer's claim is "what the app would have told you". A cutoff that differs from the
  app's own, even in a safer direction, produces forecasts the app would never have
  made and silently voids the claim. Fidelity to the real code path *is* the feature.

### The day-proxy caveat (must be disclosed, not silently fixed)

10 of the 102 completed WC2026 matches carry `kickoff_precision: "day"` — a 00:00 UTC
proxy rather than a real kickoff time. This creates an ordering ambiguity the leak guard
cannot see: a day-proxy row is stamped 00:00, so it sits *before* a same-day 19:00
cutoff and survives `training_rows()`, even if it was really played at 21:00 — after the
match being forecast.

This is a pre-existing property of date-proxy rows, inherited from the app's own replay
path, not something this surface introduces. The resolution follows the project's
standing doctrine — *a missing guarantee is a typed state with a reason, never a silent
assumption*:

- Carry `kickoff_precision` on every retrospective row.
- Where it is `"day"`, the UI marks the row and says plainly that the kickoff time is a
  date proxy, so same-day ordering is not provable and the forecast may rest on a result
  from later that day.
- Never exclude these matches silently, and never quietly diverge from `analysis.py` to
  "fix" them. Both would trade a visible caveat for an invisible one.

The training impact is small (at most ~3 same-day rows out of ~49,500), but the honesty
requirement does not scale with effect size.
- **Four families, not five.** `bivariate_poisson` is numerically identical to
  `poisson_independent` across every recorded fold; showing both implies two independent
  opinions where there is one.
- Incomplete matches are skipped with a typed reason, never scored.

### `server/golavo_server/retrospective.py` (new)

- Orchestrates via `jobs.py` (progress + cancellation, the v0.7.0 pattern).
- Cache keyed on `(index fingerprint, index epoch, active pack)`, so it self-invalidates on
  any index change, including a user refresh.
- **v1 is L1 (in-memory) only.** `analysis.py`'s L2 disk tier is ~80 lines of validation,
  atomic write, digest check, and pruning, and it is shaped around a per-`match_id`
  payload; a per-tournament envelope carrying 104 rows is a different shape and a
  different failure surface. L1-only is correct, just slower across a restart, which
  re-runs the ~3.2 min compute. Add L2 when a restart-cost complaint justifies its
  failure surface — not before.
- The cache is an **accelerator, never a dependency**: a miss recomputes, and no read
  ever fails the request.
- Route: `GET /api/v1/tournaments/worldcup-2026/retrospective` → typed job handle;
  poll for progress; result on completion.

### `ui/src/views/WorldCupRetrospective.tsx` (new)

Route `/lab/worldcup-2026`, reached from Model Lab.

- **Story**: matches ranked by log loss — "most surprised" descending, "most confident
  and right" ascending. Named plainly as per-match log loss, not dressed up as a
  proprietary "surprise score".
- **Trust**: the fold report card with its bootstrap intervals, labelled as trained once,
  pre-tournament, and stamped with the pack it was computed from.
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
