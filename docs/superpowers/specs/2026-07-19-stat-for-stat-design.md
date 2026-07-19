# Stat for stat — regrouping the Signature stats section

Date: 2026-07-19
Status: approved for planning

## Why

The "Signature stats & records" section of the matchday programme renders every leftover
editorial fact into one flat `auto-fit` grid, in array order. Facts about the competition,
about the home team and about the away team interleave with nothing but a small uppercase
subject label to tell them apart, so the reader has to re-orient at every card.

Simulating the real pipeline against the committed `France v Morocco` fixture shows the
problem is larger than it looks on screen: that grid receives **19 cards**, not the nine a
narrow viewport happens to show.

The data does not have this problem. Every fact already carries `scope`
(`competition` / `team` / `head_to_head` / `match`) and `subject`. The grid discards both.

Two further findings from the same simulation shape the design:

- **The facts are near-symmetric.** Seven team stats exist for *both* sides — venue form,
  neutral-ground record, World Cup pedigree, competition record, clean sheets, both-teams-
  scored, unbeaten run. A stat-for-stat comparison is therefore possible on real data, not
  just in principle.
- **One pair is genuinely split.** Morocco's `biggest_win` sits in the grid while France's
  was promoted into "Quick briefing" by `topInsights`. Any naive comparison layout would
  render France as `—` and assert something false.

## What it is

The section becomes a comparison of the two teams, stat for stat, with competition-level
facts lifted out into their own band above it.

Reading order within the section:

1. **The tournament** — `scope === "competition"` facts. Background about the stage, not a
   trait of either side.
2. **Complete pairs** — one row per stat where both teams have a qualifying fact.
3. **One-sided rows** — one row per stat where only one team qualifies, each stating why
   the other side is blank.

Head-to-head facts already have their own section immediately above and are untouched.

## Non-goals

- **No change to `FactCard`.** The new section does not use it, so "Quick briefing",
  "Scorer spotlight" and the quarantined-coincidence aside render exactly as they do today.
  This change has no ripple into them.
- **No change to fact selection.** `topInsights`, `prepareNotes`' promotion order, and the
  guardrails that suppress facts are all left alone. This is a presentation change; which
  facts exist and which get promoted is unchanged.
- **No change to `CommentatorsNotebook.tsx`.** It renders facts on its own route and is out
  of scope.
- **No new numbers.** Nothing is computed, rescaled, or derived beyond reading
  `base_rate` and `numbers[0].display`, exactly as `displayValue` does today.

## The honesty contract

This is the requirement the rest of the design serves.

A blank side of a comparison row must never render as a bare `—`. That mark asserts "this
team has no such record", which in the observed fixture is false at least once. A side is
blank for one of three reasons, and the reader is told which:

| Cause | Detection | Renders as |
|---|---|---|
| Twin was promoted into an earlier section of this same component | key is in the `elsewhere` map | `Shown in <section>` — an anchor to that section |
| Twin was consumed by another cockpit panel (half-time story, World Cup story) | key is in `omitKeys` | `Featured elsewhere in this programme` — no anchor; the component cannot know which panel took it |
| No fact qualified — sample or freshness guardrail suppressed it | key appears nowhere | `No qualifying sample` |

`prepareNotes` builds the `elsewhere` map from the key sets it already computes. The label
and anchor for each source are fixed:

| Facts | Label | Anchor |
|---|---|---|
| `headlines` | Quick briefing | `#mn-briefing-title` |
| `hero` | Cover story | `#mn-cover-title` — **to be added**; the hero `<h3>` has no id today |
| `scorers` | Scorer spotlight | `#mn-scorers-title` |
| `h2h` | Head to head | `#mn-h2h-title` |
| `timing`, `penalties` | Scoring clock | `#mn-timing-title` |
| `omitKeys` | this programme | none |

`prepareNotes` currently drops `omitKeys` facts on its first line and therefore cannot tell
the second cause from the third. It must retain the unfiltered fact list for twin lookup.
This is the one behavioural change to existing code.

### Bars may only represent rates

A rail is drawn **only when both sides of the row have `base_rate !== null`**. Rates share
a 0–100 scale, so bar length is meaningful and the bar is drawn against that absolute
scale. Counts (`biggest_win` = `14`, `wc_pedigree` = `16`) do not share a scale with
anything; a bar for them would be decoration impersonating data, and a bar comparing `14`
to `100%` would be worse. Count rows show numbers only, and the absence of a rail is
itself the signal that the row is not a rate.

This rule reads a property the code already branches on in `displayValue`.

## Data grouping

New pure module `ui/src/lib/factPairs.ts`, following the precedent of `lib/insights.ts`: a
documented, deterministic selector over facts the engine already produced, with no dates,
no randomness and no I/O.

```ts
export type Absence =
  | { kind: "elsewhere"; section: string; anchor: string | null }
  | { kind: "unqualified" };

export interface FactSide {
  fact: NotebookFact | null;
  absence: Absence | null;   // non-null exactly when fact is null
}

export interface FactRow {
  id: string;                // template id, e.g. "home_away_form"
  title: string;             // FACT_DISPLAY[id].title, with the existing fallback
  explainer: string;
  home: FactSide;
  away: FactSide;
  rail: boolean;             // both sides present AND both base_rate !== null
}

export interface GroupedFacts {
  tournament: NotebookFact[];  // scope === "competition"
  paired: FactRow[];           // both sides present
  solo: FactRow[];             // exactly one side present
  other: NotebookFact[];       // anything unclassified — never silently dropped
}

export function groupFacts(input: {
  cards: NotebookFact[];               // the existing view.cards residue
  home: string;
  away: string;
  elsewhere: ReadonlyMap<string, Absence>;  // factKey -> why it is not here
}): GroupedFacts;
```

### Classification

- `scope === "competition"` → `tournament`.
- `scope === "team"` and `subject === home || subject === away` → grouped by `id` into
  `paired` (two sides) or `solo` (one side).
- Everything else → `other`. A team fact whose subject matches neither side, or a `match`
  scope fact, must still render rather than vanish. Unknown template ids already fall back
  gracefully in `FACT_DISPLAY`; this is the same principle applied to shape.

### Ordering

Deterministic, so the same notebook always yields the same order:

- **`tournament`** — `sample_n` descending, then `id` ascending.
- **`paired`** — rail rows first, ordered by `|homeRate − awayRate|` **descending**; then
  non-rail rows by `max(home.sample_n, away.sample_n)` descending. `id` ascending breaks
  every tie.
- **`solo`** — `sample_n` descending, then `id` ascending.
- **`other`** — `sample_n` descending, then `id` ascending.

Widest-gap-first is an ordering rule, not an adjustment: the stats on which the two teams
most diverge are the ones that most distinguish them, so they lead. It is documented in
the module header the way `insights.ts` documents its own rule.

## Rendering

`ui/src/components/MatchNotes.tsx` gains a `StatForStat` section component that replaces
the `mn-stats-grid` block on line 289. `prepareNotes` gains two outputs: the unfiltered
fact list, and the `elsewhere` map assembled from the keys it already computes.

Markup is a real `<table>`. Stat × team is tabular data, and a table gives screen readers
row and column association for free.

```
<section class="mn-section mn-compare" aria-labelledby="mn-stats-title">
  <div class="mn-section__head">
    <span class="upper">Deeper cut</span>
    <h3 id="mn-stats-title">Stat for stat</h3>
  </div>

  <div class="mn-compare__stage">        <!-- omitted when tournament is empty -->
    <span class="upper">The tournament</span>
    …one line per competition fact: value, title, explainer…
  </div>

  <table class="mn-compare__table">
    <caption class="visually-hidden">…home v away, stats both teams qualify for…</caption>
    <thead>
      <tr><th scope="col">Stat</th><th scope="col">{home}</th><th scope="col">{away}</th></tr>
    </thead>
    <tbody>
      <tr>
        <th scope="row">
          <span class="mn-compare__stat">{title}</span>
          {!expert && <p class="mn-compare__explainer">{explainer}</p>}
        </th>
        <td class="mn-compare__cell mn-compare__cell--home">…</td>
        <td class="mn-compare__cell mn-compare__cell--away">…</td>
      </tr>
    </tbody>
  </table>

  <div class="mn-compare__solo">         <!-- omitted when solo is empty -->
    <span class="upper">Only one side qualifies</span>
    <table class="mn-compare__table">…same three columns…</table>
  </div>
</section>
```

Three columns, no `colspan`. The rail lives **inside** the value cell as a decorative
`<span aria-hidden>`, not as its own column, so hiding rails on narrow screens cannot
desynchronise the header row from the body.

A present cell holds the value, the optional rail, and — when `expert` — `<FactSource/>`
inline. An absent cell holds only its reason, as text or as an anchor.

The hero `<h3>` in the cover-story block gains `id="mn-cover-title"` so absence anchors can
target it. `mn-briefing-title`, `mn-scorers-title`, `mn-timing-title` and `mn-h2h-title`
already exist.

### Density follows the existing toggle

No new control. The mapping matches the toggle's own published copy — Expert is "full model
values, market detail, sources and audit context"; Casual is "the essential story, with
technical depth kept out of the way":

| Mode | Explainer line | The engine's sentence (`fact.text`) | Source proof (`<FactSource/>`) |
|---|---|---|---|
| Casual | visible under the stat name | inside the cell's `<details>` | inside the same `<details>`, after the sentence |
| Expert | hidden — the reader knows what a clean-sheet rate is | inside the cell's `<details>` | inline in the cell, always visible |

`fact.text` — the engine's exact, number-disciplined sentence — stays behind a per-cell
`<details>` in **both** modes, exactly as `FactCard` holds it today. Expert does not repeat
it inline; it only lifts the proof out of the disclosure. So expert trades a wordy
explainer for a compact proof line and stays the denser of the two.

Each present cell owns its own disclosure, because each cell is a separate fact with a
separate sample and separate source ids.

This reuses the `expert` prop already threaded into `MatchNotes`, and mirrors the
`{expert && <FactSource fact={fact} />}` pattern `GoalTimingSpotlight` uses today.

## Visual specification

New flat `.mn-compare__*` block in `ui/src/index.css`, placed with the other `.mn-*` rules.
A single class namespace with no element-selector overlap, per the specificity warning in
CLAUDE.md.

- **Colour** — the existing `--home` (gold) and `--away` (orange) tokens, unchanged. The
  H2H band immediately above already teaches this coding, so the reader learns it once.
- **Rails** — home rail is right-aligned and grows leftward; away rail is left-aligned and
  grows rightward, meeting at the centre gutter. Width is the rate itself against a 0–100
  track. Height `9px`, square ends, no radius on the fill.
- **Numbers** — `--font-mono`, tabular, coloured by side. Text sits outside the bar, so the
  `--seg-*` tokens that exist for on-bar labels are not needed here.
- **Absence text** — `--text-dim`, italic. Anchors use `--link`.
- **The tournament band** — full width, left rule in `--wave` (the informational accent),
  square corners. Visually distinct from the team rows so it never reads as a third team.

### Responsive and accessible

- Below the table's comfortable width, the rail spans are `display: none`. They are
  `aria-hidden` decoration duplicating the numeric cell, so nothing is lost.
- Row 01–09 numbering is dropped. The order was array residue, so the numbers signalled a
  ranking that did not exist. "Quick briefing" keeps its numbering, where `topInsights`
  genuinely ranks by a documented rule.
- Colour is never the only carrier: each column has a text header naming its team, and
  every value is written out.
- Existing `visually-hidden` utility is used for table captions.

## Testing

Both files live under `ui/src/`, never `ui/tests/` — `ui/vite.config.ts` restricts vitest
to `src/**/*.test.{ts,tsx}` and a spec in the wrong directory silently never runs.

**`ui/src/lib/factPairs.test.ts`** — the real logic, tested without rendering:

- a stat present for both teams produces one `paired` row
- a stat present for one team produces one `solo` row with the other side absent
- a stat whose twin is in the `elsewhere` map produces `absence.kind === "elsewhere"` with
  the section label, **not** `"unqualified"` — the regression guard for the split-pair bug
- a stat whose twin appears nowhere produces `absence.kind === "unqualified"`
- `scope === "competition"` facts land in `tournament`, never in a row
- a fact whose subject matches neither team lands in `other` and is not dropped
- `rail` is true only when both sides carry a `base_rate`
- ordering is stable: the same input twice yields the same order; widest-gap rail row leads

**`ui/src/components/MatchNotes.test.tsx`** — render assertions using the house convention
(`createElement` + `renderToStaticMarkup`, node environment, asserting on HTML; no jsdom is
needed because the section is pure render with no state or effects):

- the tournament band renders outside the comparison table
- a paired row's markup contains both teams' values
- a split-pair row renders the cross-reference text, and does **not** contain a bare `—`
- casual mode renders the explainer; expert mode renders source proof instead
- an empty `cards` list renders no table rather than an empty one

## What could break

- **The axe end-to-end contrast test.** Value text sits outside the rails, so `--home` /
  `--away` on `--surface-1` are the relevant pairs rather than the on-bar `--seg-*` tokens.
  To be verified by running the test, not assumed.
- **`make lint` runs oxlint with `--deny-warnings`.** Any warning fails the build. New
  markup must not reintroduce the `exhaustive-deps` or `no-did-update-set-state` patterns
  that are file-scoped off elsewhere; this section adds no hooks, so neither applies.
- **`npm run typecheck`** (`tsc --noEmit`, strict) is the TypeScript gate. `mypy` does not
  run in this repo and is not relevant here.
- **Contract drift.** `factPairs.ts` derives display metadata from `FACT_DISPLAY` and adds
  no schema, so `docs/contracts/` and the three-place version check are untouched. No new
  file is added to `docs/contracts/`, so the `OWNERS` table needs no entry.
- **Determinism.** No Python, no index rebuild, no `make index`. UI-only change.

## Files

| File | Change |
|---|---|
| `ui/src/lib/factPairs.ts` | new — `groupFacts`, the ordering rule, the absence types |
| `ui/src/lib/factPairs.test.ts` | new — unit tests for the rule |
| `ui/src/components/MatchNotes.test.tsx` | new — render assertions |
| `ui/src/components/MatchNotes.tsx` | `prepareNotes` retains unfiltered facts and builds the `elsewhere` map; `StatForStat` replaces the `mn-stats-grid` block; hero `<h3>` gains an id |
| `ui/src/index.css` | new `.mn-compare__*` block; `.mn-stats-grid` dropped from the shared `.mn-feature-grid, .mn-stats-grid` rule — line 289 is its only usage, so it is dead after this change and the rule becomes `.mn-feature-grid` alone |

`FactCard`, `topInsights`, the fact contract and every other section are unchanged.
