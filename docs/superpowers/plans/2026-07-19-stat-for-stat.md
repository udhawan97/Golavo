# Stat for stat Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the flat, subject-interleaved "Signature stats & records" grid with a stat-for-stat comparison of the two teams, competition facts lifted into their own band, and every blank side stating why it is blank.

**Architecture:** A new pure module `ui/src/lib/factPairs.ts` does all grouping and ordering with no JSX, so the rules are unit-tested without rendering. `MatchNotes.tsx` calls it from the existing `prepareNotes` and renders the result as a three-column `<table>`. `FactCard` and every other section are untouched.

**Tech Stack:** React 18, TypeScript (strict), Vite, vitest, oxlint. No new dependencies.

## Global Constraints

- **The statistical engine owns every probability.** This change reads `base_rate`, `sample_n` and `numbers[0].display` and rescales nothing.
- **Every displayed fact carries a source id** — `<FactSource/>` must remain reachable for every rendered fact.
- **Not a betting product.** No odds, value, units, locks, or bankroll language in any new copy.
- **Tests live in `ui/src/**/*.test.{ts,tsx}`.** `ui/vite.config.ts` restricts vitest to `src/`; a test placed in `ui/tests/` runs under Playwright only and silently never runs.
- **Component tests render to a string** — `createElement` + `renderToStaticMarkup` from `react-dom/server`, node environment, asserting on HTML. No jsdom; this section has no state or effects.
- **`make lint` runs oxlint with `--deny-warnings`.** Any warning fails the build.
- **`npm run typecheck`** (`tsc --noEmit`, strict) is the TypeScript gate. mypy does not run in this repo.
- **Conventional Commits**, signed off with `git commit -s`.
- Existing utility classes to reuse, not redefine: `.upper`, `.num`, `.small`, `.dim`, `.visually-hidden`, `.mn-section`, `.mn-section__head`, `.mn-fact__proof`.
- Existing CSS custom properties to reuse: `--home`, `--away`, `--wave`, `--gold`, `--link`, `--text-muted`, `--text-dim`, `--border`, `--border-strong`, `--surface-2`, `--surface-3`, `--text-xs`, `--text-sm`.

---

### Task 1: The pure grouping module

**Files:**
- Create: `ui/src/lib/factPairs.ts`
- Create: `ui/src/lib/factPairs.test.ts`
- Modify: `ui/src/components/CommentatorsNotebook.tsx:58` (re-export `factKey` instead of defining it)

**Interfaces:**
- Consumes: `NotebookFact`, `FACT_DISPLAY` from `ui/src/lib/contract.ts`.
- Produces: `factKey(f)`, `groupFacts(input): GroupedFacts`, `buildElsewhere(sources): Map<string, Absence>`, and the types `Absence`, `FactSide`, `FactRow`, `GroupedFacts`, `ElsewhereSources`, `GroupInput`. Task 2 renders `GroupedFacts` and calls both functions from `prepareNotes`.

`factKey` moves here because this module's correctness depends on the key format matching exactly — duplicating the one-liner would let the `elsewhere` lookup fail silently. `CommentatorsNotebook.tsx` re-exports it so every existing importer is unaffected. No cycle results: `factPairs.ts` imports only `contract.ts`.

- [ ] **Step 1: Write the failing test**

Create `ui/src/lib/factPairs.test.ts`:

```tsx
import { describe, expect, it } from "vitest";
import type { NotebookFact } from "./contract";
import { buildElsewhere, factKey, groupFacts } from "./factPairs";

let seq = 0;
function mk(over: Partial<NotebookFact> = {}): NotebookFact {
  seq += 1;
  return {
    id: over.id ?? `fact_${seq}`,
    version: "1.0.0",
    label: "context",
    scope: "team",
    subject: "France",
    text: "A fact.",
    values: {},
    numbers: [],
    sample_n: 100,
    denominator: 100,
    base_rate: null,
    date_range: ["2000-01-01", "2026-01-01"],
    source_ids: ["sp_x"],
    min_sample: 3,
    specificity: 0.5,
    freshness: {
      as_of_utc: "2026-01-01T00:00:00Z",
      last_event_utc: "2026-01-01T00:00:00Z",
      age_days: 1,
      stale: false,
      staleness_days: null,
    },
    ...over,
  };
}

const group = (cards: NotebookFact[], elsewhere = new Map()) =>
  groupFacts({ cards, home: "France", away: "Morocco", elsewhere });

describe("groupFacts", () => {
  it("pairs a stat both teams qualify for into one row", () => {
    const result = group([
      mk({ id: "clean_sheet_rate", subject: "France", base_rate: 0.4 }),
      mk({ id: "clean_sheet_rate", subject: "Morocco", base_rate: 0.6 }),
    ]);
    expect(result.paired).toHaveLength(1);
    expect(result.solo).toHaveLength(0);
    expect(result.paired[0].home.fact?.base_rate).toBe(0.4);
    expect(result.paired[0].away.fact?.base_rate).toBe(0.6);
    expect(result.paired[0].title).toBe("Clean sheets");
  });

  it("puts a stat only one team qualifies for in solo, with the other side absent", () => {
    const result = group([mk({ id: "win_streak", subject: "France" })]);
    expect(result.paired).toHaveLength(0);
    expect(result.solo).toHaveLength(1);
    expect(result.solo[0].home.fact).not.toBeNull();
    expect(result.solo[0].away.fact).toBeNull();
  });

  it("says a missing twin was promoted elsewhere rather than implying it does not exist", () => {
    const elsewhere = new Map([
      ["biggest_win::France", { kind: "elsewhere" as const, section: "Quick briefing", anchor: "#mn-briefing-title" }],
    ]);
    const result = group([mk({ id: "biggest_win", subject: "Morocco" })], elsewhere);
    expect(result.solo[0].home.absence).toEqual({
      kind: "elsewhere",
      section: "Quick briefing",
      anchor: "#mn-briefing-title",
    });
  });

  it("says a missing twin was suppressed when it appears nowhere", () => {
    const result = group([mk({ id: "win_streak", subject: "France" })]);
    expect(result.solo[0].away.absence).toEqual({ kind: "unqualified" });
  });

  it("lifts competition facts out of the comparison entirely", () => {
    const result = group([
      mk({ id: "home_advantage_base_rate", scope: "competition", subject: "FIFA World Cup", base_rate: 0.61 }),
      mk({ id: "clean_sheet_rate", subject: "France", base_rate: 0.4 }),
      mk({ id: "clean_sheet_rate", subject: "Morocco", base_rate: 0.6 }),
    ]);
    expect(result.tournament).toHaveLength(1);
    expect(result.paired).toHaveLength(1);
    expect(result.solo).toHaveLength(0);
  });

  it("never drops a fact whose subject matches neither team", () => {
    const result = group([mk({ id: "head_to_head_goals", scope: "head_to_head", subject: "France v Morocco" })]);
    expect(result.other).toHaveLength(1);
    expect(result.paired).toHaveLength(0);
    expect(result.solo).toHaveLength(0);
  });

  it("allows a rail only when both sides are rates", () => {
    const rates = group([
      mk({ id: "clean_sheet_rate", subject: "France", base_rate: 0.4 }),
      mk({ id: "clean_sheet_rate", subject: "Morocco", base_rate: 0.6 }),
    ]);
    const counts = group([
      mk({ id: "wc_pedigree", subject: "France", base_rate: null }),
      mk({ id: "wc_pedigree", subject: "Morocco", base_rate: null }),
    ]);
    expect(rates.paired[0].rail).toBe(true);
    expect(counts.paired[0].rail).toBe(false);
  });

  it("leads with the widest gap and puts rate rows before count rows", () => {
    const result = group([
      mk({ id: "clean_sheet_rate", subject: "France", base_rate: 0.4 }),
      mk({ id: "clean_sheet_rate", subject: "Morocco", base_rate: 0.45 }),
      mk({ id: "tournament_record", subject: "France", base_rate: 0.56 }),
      mk({ id: "tournament_record", subject: "Morocco", base_rate: 0.29 }),
      mk({ id: "wc_pedigree", subject: "France", base_rate: null }),
      mk({ id: "wc_pedigree", subject: "Morocco", base_rate: null }),
    ]);
    expect(result.paired.map((row) => row.id)).toEqual([
      "tournament_record",
      "clean_sheet_rate",
      "wc_pedigree",
    ]);
  });

  it("orders identically on repeated runs", () => {
    const cards = [
      mk({ id: "b_stat", subject: "France", base_rate: 0.5, sample_n: 10 }),
      mk({ id: "b_stat", subject: "Morocco", base_rate: 0.4, sample_n: 10 }),
      mk({ id: "a_stat", subject: "France", base_rate: 0.5, sample_n: 10 }),
      mk({ id: "a_stat", subject: "Morocco", base_rate: 0.4, sample_n: 10 }),
    ];
    const first = group(cards).paired.map((row) => row.id);
    const second = group([...cards].reverse()).paired.map((row) => row.id);
    expect(first).toEqual(second);
    expect(first).toEqual(["a_stat", "b_stat"]);
  });

  it("falls back gracefully for an unregistered template id", () => {
    const result = group([mk({ id: "future_template", subject: "France" })]);
    expect(result.solo[0].title).toBe("Match record");
  });
});

describe("buildElsewhere", () => {
  const empty = { headlines: [], hero: null, scorers: [], h2h: null, timing: [], penalties: [], omitted: new Set<string>() };

  it("labels and anchors each promoting section", () => {
    const map = buildElsewhere({
      ...empty,
      headlines: [mk({ id: "biggest_win", subject: "France" })],
      hero: mk({ id: "home_advantage_base_rate", subject: "FIFA World Cup" }),
      timing: [mk({ id: "goal_timing_profile", subject: "Morocco" })],
    });
    expect(map.get("biggest_win::France")).toEqual({
      kind: "elsewhere", section: "Quick briefing", anchor: "#mn-briefing-title",
    });
    expect(map.get("home_advantage_base_rate::FIFA World Cup")).toEqual({
      kind: "elsewhere", section: "Cover story", anchor: "#mn-cover-title",
    });
    expect(map.get("goal_timing_profile::Morocco")).toEqual({
      kind: "elsewhere", section: "Scoring clock", anchor: "#mn-timing-title",
    });
  });

  it("marks a fact consumed by another panel with no anchor it cannot resolve", () => {
    const map = buildElsewhere({ ...empty, omitted: new Set(["ht_lead_conversion::France"]) });
    expect(map.get("ht_lead_conversion::France")).toEqual({
      kind: "elsewhere", section: "this programme", anchor: null,
    });
  });

  it("prefers the named section over the generic one", () => {
    const map = buildElsewhere({
      ...empty,
      headlines: [mk({ id: "biggest_win", subject: "France" })],
      omitted: new Set(["biggest_win::France"]),
    });
    expect(map.get("biggest_win::France")?.section).toBe("Quick briefing");
  });
});

describe("factKey", () => {
  it("separates the same stat held by two subjects", () => {
    expect(factKey({ id: "biggest_win", subject: "France" })).toBe("biggest_win::France");
    expect(factKey({ id: "biggest_win", subject: "Morocco" })).not.toBe(
      factKey({ id: "biggest_win", subject: "France" }),
    );
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ui && npx vitest run src/lib/factPairs.test.ts`
Expected: FAIL — `Failed to resolve import "./factPairs"`.

- [ ] **Step 3: Write the implementation**

Create `ui/src/lib/factPairs.ts`:

```ts
/**
 * "Stat for stat" — a pure, deterministic regrouping of the notebook facts the
 * programme has left over after its earlier sections have taken theirs.
 *
 * It invents nothing and rescales nothing. It only SORTS facts the engine
 * already computed into readable bands, by a fixed, documented rule:
 *
 *   1. competition-scope facts describe the stage, not a trait of either side,
 *      so they are lifted out of the comparison entirely.
 *   2. team facts are matched to their twin — the same template id held by the
 *      other side — so the reader compares like with like.
 *   3. a side with no twin states WHY. A bare em dash would assert "this team
 *      has no such record", which is false whenever the twin was merely
 *      promoted into an earlier section of the same programme. See `Absence`.
 *   4. anything that fits none of the above still renders. Facts are never
 *      silently dropped to make the layout tidy.
 *
 * Ordering is fixed so the same notebook always yields the same page:
 *   - paired rate rows lead, widest gap first — the stats on which the teams
 *     most diverge are the ones that most distinguish them.
 *   - then paired counts by the larger sample, then the one-sided rows.
 *   - `id` ascending breaks every tie, so the order never wobbles.
 */
import { FACT_DISPLAY, type FactDisplay, type NotebookFact } from "./contract";

/** Identity of a fact within one notebook: the same template held by two
 *  subjects is two facts. Defined here because the `elsewhere` lookup below is
 *  only correct while every caller agrees on this exact format. */
export const factKey = (f: { id: string; subject: string }): string => `${f.id}::${f.subject}`;

/** Why a side of a comparison row carries no number. Never rendered as a bare
 *  dash: "displayed in another section" and "no fact qualified" are different
 *  claims, and only the second one means the record does not exist. */
export type Absence =
  | { kind: "elsewhere"; section: string; anchor: string | null }
  | { kind: "unqualified" };

export interface FactSide {
  fact: NotebookFact | null;
  /** Non-null exactly when `fact` is null. */
  absence: Absence | null;
}

export interface FactRow {
  id: string;
  title: string;
  explainer: string;
  home: FactSide;
  away: FactSide;
  /** Both sides are rates, so a shared 0–100 rail is meaningful. A rail across
   *  a count would be decoration impersonating data. */
  rail: boolean;
}

export interface GroupedFacts {
  tournament: NotebookFact[];
  paired: FactRow[];
  solo: FactRow[];
  other: NotebookFact[];
}

export interface ElsewhereSources {
  headlines: NotebookFact[];
  hero: NotebookFact | null;
  scorers: NotebookFact[];
  h2h: NotebookFact | null;
  timing: NotebookFact[];
  penalties: NotebookFact[];
  /** factKeys the cockpit consumed for another panel entirely. */
  omitted: ReadonlySet<string>;
}

export interface GroupInput {
  cards: NotebookFact[];
  home: string;
  away: string;
  elsewhere: ReadonlyMap<string, Absence>;
}

const FALLBACK_DISPLAY: FactDisplay = {
  title: "Match record",
  explainer: "A source-backed fact from the available history.",
};

/** Where each already-placed fact went, so a blank side can point at it.
 *  First writer wins: a named section beats the generic "this programme". */
export function buildElsewhere(sources: ElsewhereSources): Map<string, Absence> {
  const map = new Map<string, Absence>();
  const add = (facts: NotebookFact[], section: string, anchor: string) => {
    for (const fact of facts) {
      const key = factKey(fact);
      if (!map.has(key)) map.set(key, { kind: "elsewhere", section, anchor });
    }
  };
  add(sources.headlines, "Quick briefing", "#mn-briefing-title");
  add(sources.hero ? [sources.hero] : [], "Cover story", "#mn-cover-title");
  add(sources.scorers, "Scorer spotlight", "#mn-scorers-title");
  add(sources.h2h ? [sources.h2h] : [], "Head to head", "#mn-h2h-title");
  add([...sources.timing, ...sources.penalties], "Scoring clock", "#mn-timing-title");
  for (const key of sources.omitted) {
    if (!map.has(key)) map.set(key, { kind: "elsewhere", section: "this programme", anchor: null });
  }
  return map;
}

function sideOf(
  fact: NotebookFact | null,
  id: string,
  subject: string,
  elsewhere: ReadonlyMap<string, Absence>,
): FactSide {
  if (fact) return { fact, absence: null };
  return { fact: null, absence: elsewhere.get(`${id}::${subject}`) ?? { kind: "unqualified" } };
}

const gap = (row: FactRow): number =>
  Math.abs((row.home.fact?.base_rate ?? 0) - (row.away.fact?.base_rate ?? 0));

const maxSample = (row: FactRow): number =>
  Math.max(row.home.fact?.sample_n ?? 0, row.away.fact?.sample_n ?? 0);

const bySample = (a: NotebookFact, b: NotebookFact): number =>
  b.sample_n - a.sample_n || a.id.localeCompare(b.id);

export function groupFacts({ cards, home, away, elsewhere }: GroupInput): GroupedFacts {
  const tournament: NotebookFact[] = [];
  const other: NotebookFact[] = [];
  const sides = new Map<string, { home: NotebookFact | null; away: NotebookFact | null }>();

  for (const fact of cards) {
    if (fact.scope === "competition") {
      tournament.push(fact);
      continue;
    }
    const side = fact.scope === "team" && fact.subject === home
      ? "home"
      : fact.scope === "team" && fact.subject === away
        ? "away"
        : null;
    if (!side) {
      other.push(fact);
      continue;
    }
    const entry = sides.get(fact.id) ?? { home: null, away: null };
    if (entry[side]) {
      // factKey is unique, so this cannot happen for a well-formed notebook.
      // Keep the first and still render the second rather than losing a fact.
      other.push(fact);
      continue;
    }
    entry[side] = fact;
    sides.set(fact.id, entry);
  }

  const rows: FactRow[] = [];
  for (const [id, entry] of sides) {
    const display = FACT_DISPLAY[id] ?? FALLBACK_DISPLAY;
    rows.push({
      id,
      title: display.title,
      explainer: display.explainer,
      home: sideOf(entry.home, id, home, elsewhere),
      away: sideOf(entry.away, id, away, elsewhere),
      rail: entry.home?.base_rate != null && entry.away?.base_rate != null,
    });
  }

  const paired = rows
    .filter((row) => row.home.fact !== null && row.away.fact !== null)
    .sort((a, b) => {
      if (a.rail !== b.rail) return a.rail ? -1 : 1;
      if (a.rail && b.rail) return gap(b) - gap(a) || a.id.localeCompare(b.id);
      return maxSample(b) - maxSample(a) || a.id.localeCompare(b.id);
    });

  const solo = rows
    .filter((row) => row.home.fact === null || row.away.fact === null)
    .sort((a, b) => maxSample(b) - maxSample(a) || a.id.localeCompare(b.id));

  return { tournament: tournament.sort(bySample), paired, solo, other: other.sort(bySample) };
}
```

- [ ] **Step 4: Point `CommentatorsNotebook` at the single definition**

In `ui/src/components/CommentatorsNotebook.tsx`, replace line 58:

```ts
export const factKey = (f: { id: string; subject: string }): string => `${f.id}::${f.subject}`;
```

with:

```ts
export { factKey } from "../lib/factPairs";
```

Every existing importer of `factKey` from `./CommentatorsNotebook` keeps working unchanged.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd ui && npx vitest run src/lib/factPairs.test.ts`
Expected: PASS, 14 tests.

- [ ] **Step 6: Typecheck**

Run: `cd ui && npm run typecheck`
Expected: exit 0, no output.

- [ ] **Step 7: Commit**

```bash
git add ui/src/lib/factPairs.ts ui/src/lib/factPairs.test.ts ui/src/components/CommentatorsNotebook.tsx
git commit -s -m "feat(ui): group notebook facts into stat-for-stat pairs

A pure module that matches each team fact to its twin, lifts competition
facts out of the comparison, and records why a blank side is blank. A twin
promoted into an earlier section is not the same claim as a twin the
guardrails suppressed, and only the second means the record does not exist."
```

---

### Task 2: Render the comparison

**Files:**
- Modify: `ui/src/components/MatchNotes.tsx` — `prepareNotes` (lines 164–205), the hero block (line 279), and the stats section (line 289)
- Create: `ui/src/components/MatchNotes.test.tsx`

**Interfaces:**
- Consumes: `groupFacts`, `buildElsewhere`, `factKey`, and the types `GroupedFacts`, `FactRow`, `FactSide` from Task 1.
- Produces: exported `StatForStat({ grouped, home, away, expert })` for direct testing; `prepareNotes` gains a `grouped: GroupedFacts` field on its return object.

- [ ] **Step 1: Write the failing test**

Create `ui/src/components/MatchNotes.test.tsx`:

```tsx
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { NotebookFact } from "../lib/contract";
import type { GroupedFacts } from "../lib/factPairs";
import { StatForStat } from "./MatchNotes";

let seq = 0;
function mk(over: Partial<NotebookFact> = {}): NotebookFact {
  seq += 1;
  return {
    id: over.id ?? `fact_${seq}`,
    version: "1.0.0",
    label: "context",
    scope: "team",
    subject: "France",
    text: "France kept a clean sheet in 8 of 20 recent matches (40.0%).",
    values: {},
    numbers: [{ key: "n", value: 8, unit: "count", display: "8" }],
    sample_n: 20,
    denominator: 20,
    base_rate: null,
    date_range: ["2000-01-01", "2026-01-01"],
    source_ids: ["sp_x"],
    min_sample: 3,
    specificity: 0.5,
    freshness: {
      as_of_utc: "2026-01-01T00:00:00Z",
      last_event_utc: "2026-01-01T00:00:00Z",
      age_days: 1,
      stale: false,
      staleness_days: null,
    },
    ...over,
  };
}

const empty: GroupedFacts = { tournament: [], paired: [], solo: [], other: [] };

const render = (grouped: Partial<GroupedFacts>, expert = false) =>
  renderToStaticMarkup(
    <StatForStat grouped={{ ...empty, ...grouped }} home="France" away="Morocco" expert={expert} />,
  );

describe("StatForStat", () => {
  it("renders nothing when no facts survived", () => {
    expect(render({})).toBe("");
  });

  it("shows both teams' values on one row", () => {
    const html = render({
      paired: [{
        id: "clean_sheet_rate",
        title: "Clean sheets",
        explainer: "How often this team stopped the opposition from scoring recently.",
        home: { fact: mk({ subject: "France", base_rate: 0.4 }), absence: null },
        away: { fact: mk({ subject: "Morocco", base_rate: 0.6 }), absence: null },
        rail: true,
      }],
    });
    expect(html).toContain("Clean sheets");
    expect(html).toContain("40%");
    expect(html).toContain("60%");
    expect(html).toContain("France");
    expect(html).toContain("Morocco");
  });

  it("points at the section holding a promoted twin instead of implying absence", () => {
    const html = render({
      solo: [{
        id: "biggest_win",
        title: "Biggest win",
        explainer: "The widest winning scoreline in the available history.",
        home: {
          fact: null,
          absence: { kind: "elsewhere", section: "Quick briefing", anchor: "#mn-briefing-title" },
        },
        away: { fact: mk({ subject: "Morocco" }), absence: null },
        rail: false,
      }],
    });
    expect(html).toContain("Shown in Quick briefing");
    expect(html).toContain('href="#mn-briefing-title"');
    expect(html).not.toContain("—</");
  });

  it("names the guardrail when no fact qualified", () => {
    const html = render({
      solo: [{
        id: "win_streak",
        title: "Winning streak",
        explainer: "Consecutive wins in the team’s current run.",
        home: { fact: mk({ subject: "France" }), absence: null },
        away: { fact: null, absence: { kind: "unqualified" } },
        rail: false,
      }],
    });
    expect(html).toContain("No qualifying sample");
  });

  it("keeps the tournament band out of the comparison table", () => {
    const html = render({
      tournament: [mk({
        id: "competition_debut_base_rate",
        scope: "competition",
        subject: "FIFA World Cup",
        base_rate: 0.26,
      })],
    });
    expect(html).toContain("The tournament");
    expect(html).toContain("First-year teams");
    expect(html).not.toContain("<table");
  });

  it("gives the casual reader the explainer and the expert the source proof", () => {
    const row = {
      id: "clean_sheet_rate",
      title: "Clean sheets",
      explainer: "How often this team stopped the opposition from scoring recently.",
      home: { fact: mk({ subject: "France", base_rate: 0.4 }), absence: null },
      away: { fact: mk({ subject: "Morocco", base_rate: 0.6 }), absence: null },
      rail: true,
    };
    const casual = render({ paired: [row] }, false);
    const expert = render({ paired: [row] }, true);
    expect(casual).toContain("How often this team stopped");
    expect(casual).not.toContain("minimum 3");
    expect(expert).not.toContain("How often this team stopped");
    expect(expert).toContain("minimum 3");
  });

  it("draws a rail only for rates", () => {
    const rate = render({
      paired: [{
        id: "clean_sheet_rate", title: "Clean sheets", explainer: "x",
        home: { fact: mk({ subject: "France", base_rate: 0.4 }), absence: null },
        away: { fact: mk({ subject: "Morocco", base_rate: 0.6 }), absence: null },
        rail: true,
      }],
    });
    const count = render({
      paired: [{
        id: "wc_pedigree", title: "World Cup pedigree", explainer: "x",
        home: { fact: mk({ subject: "France" }), absence: null },
        away: { fact: mk({ subject: "Morocco" }), absence: null },
        rail: false,
      }],
    });
    expect(rate).toContain("mn-compare__rail");
    expect(count).not.toContain("mn-compare__rail");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ui && npx vitest run src/components/MatchNotes.test.tsx`
Expected: FAIL — `StatForStat` is not exported from `./MatchNotes`.

- [ ] **Step 3: Add the imports**

In `ui/src/components/MatchNotes.tsx`, replace the import on line 5:

```ts
import { factKey, RateDial, SourcePopover } from "./CommentatorsNotebook";
```

with:

```ts
import { RateDial, SourcePopover } from "./CommentatorsNotebook";
import { buildElsewhere, factKey, groupFacts, type FactRow, type FactSide, type GroupedFacts } from "../lib/factPairs";
```

- [ ] **Step 4: Add the three rendering components**

In `ui/src/components/MatchNotes.tsx`, insert directly after `FactCard` (after line 56):

```tsx
/** One side of a comparison row. An absent side never renders a bare dash:
 * "displayed in another section" and "no fact qualified" are different claims. */
function CompareCell({ side, tone, rail, expert }: {
  side: FactSide;
  tone: "home" | "away";
  rail: boolean;
  expert?: boolean;
}) {
  const className = `mn-compare__cell mn-compare__cell--${tone}`;
  if (!side.fact) {
    const absence = side.absence ?? { kind: "unqualified" as const };
    return (
      <td className={`${className} mn-compare__cell--absent`}>
        {absence.kind === "unqualified" ? (
          <span className="mn-compare__absent">No qualifying sample</span>
        ) : absence.anchor ? (
          <a className="mn-compare__absent" href={absence.anchor}>Shown in {absence.section}</a>
        ) : (
          <span className="mn-compare__absent">Featured elsewhere in {absence.section}</span>
        )}
      </td>
    );
  }
  const fact = side.fact;
  return (
    <td className={className}>
      <span className="mn-compare__value num">{displayValue(fact)}</span>
      {rail && fact.base_rate !== null && (
        <span className="mn-compare__rail" aria-hidden>
          <span className="mn-compare__fill" style={{ width: `${Math.round(fact.base_rate * 100)}%` }} />
        </span>
      )}
      <details className="mn-compare__detail">
        <summary>Full stat</summary>
        <p>{fact.text}</p>
        {!expert && <FactSource fact={fact} />}
      </details>
      {expert && <FactSource fact={fact} />}
    </td>
  );
}

function CompareTable({ rows, home, away, expert, caption }: {
  rows: FactRow[];
  home: string;
  away: string;
  expert?: boolean;
  caption: string;
}) {
  if (rows.length === 0) return null;
  return (
    <table className="mn-compare__table">
      <caption className="visually-hidden">{caption}</caption>
      <thead>
        <tr>
          <th scope="col">Stat</th>
          <th scope="col" className="mn-compare__team mn-compare__team--home">{home}</th>
          <th scope="col" className="mn-compare__team mn-compare__team--away">{away}</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.id}>
            <th scope="row" className="mn-compare__stat">
              <span>{row.title}</span>
              {!expert && <p className="mn-compare__explainer">{row.explainer}</p>}
            </th>
            <CompareCell side={row.home} tone="home" rail={row.rail} expert={expert} />
            <CompareCell side={row.away} tone="away" rail={row.rail} expert={expert} />
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** The competition band, the paired comparison, and the rows only one side
 * qualifies for. Exported for direct testing. */
export function StatForStat({ grouped, home, away, expert }: {
  grouped: GroupedFacts;
  home: string;
  away: string;
  expert?: boolean;
}) {
  const { tournament, paired, solo, other } = grouped;
  if (!tournament.length && !paired.length && !solo.length && !other.length) return null;
  return (
    <section className="mn-section mn-compare" aria-labelledby="mn-stats-title">
      <div className="mn-section__head"><span className="upper">Deeper cut</span><h3 id="mn-stats-title">Stat for stat</h3></div>

      {tournament.length > 0 && (
        <div className="mn-compare__stage">
          <span className="upper">The tournament</span>
          <ul>
            {tournament.map((fact) => {
              const display = FACT_DISPLAY[fact.id] ?? { title: "Match record", explainer: "A source-backed fact from the available history." };
              return (
                <li key={factKey(fact)}>
                  <strong className="num">{displayValue(fact)}</strong>
                  <b>{display.title}</b>
                  <span>{display.explainer}</span>
                  <details className="mn-compare__detail">
                    <summary>Full stat &amp; source</summary>
                    <p>{fact.text}</p>
                    <FactSource fact={fact} />
                  </details>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      <CompareTable
        rows={paired}
        home={home}
        away={away}
        expert={expert}
        caption={`${home} against ${away}, on the stats both teams qualify for.`}
      />

      {solo.length > 0 && (
        <div className="mn-compare__solo">
          <span className="upper">Only one side qualifies</span>
          <CompareTable
            rows={solo}
            home={home}
            away={away}
            expert={expert}
            caption={`Stats where only one of ${home} or ${away} has a qualifying record.`}
          />
        </div>
      )}

      {other.length > 0 && (
        <div className="mn-feature-grid mn-compare__other">
          {other.map((fact) => <FactCard fact={fact} key={factKey(fact)} />)}
        </div>
      )}
    </section>
  );
}
```

- [ ] **Step 5: Make `FactCard`'s index optional**

The `other` fallback above renders `FactCard` without a number, because that band has no meaningful order. Change the signature on line 45 of `ui/src/components/MatchNotes.tsx` from:

```tsx
function FactCard({ fact, index }: { fact: NotebookFact; index: number }) {
```

to:

```tsx
function FactCard({ fact, index }: { fact: NotebookFact; index?: number }) {
```

and change line 49 from:

```tsx
      <span className="mn-fact__number num" aria-hidden>{String(index).padStart(2, "0")}</span>
```

to:

```tsx
      {index !== undefined && <span className="mn-fact__number num" aria-hidden>{String(index).padStart(2, "0")}</span>}
```

The three existing call sites pass `index` and are unaffected.

- [ ] **Step 6: Wire `prepareNotes` to the grouping**

In `ui/src/components/MatchNotes.tsx`, change line 170 from:

```ts
  const visible = notebook?.facts.filter((fact) => !omitKeys.has(factKey(fact))) ?? [];
```

to:

```ts
  const all = notebook?.facts ?? [];
  const visible = all.filter((fact) => !omitKeys.has(factKey(fact)));
```

Then, immediately after the `away` constant (line 188), insert:

```ts
  const grouped = groupFacts({
    cards,
    home,
    away,
    elsewhere: buildElsewhere({ headlines, hero, scorers, h2h, timing, penalties, omitted: omitKeys }),
  });
```

and add `grouped,` to the returned object, immediately after `cards,`.

`all` is retained so a fact filtered out by `omitKeys` is still reachable for the absence lookup — that is the whole reason the "featured elsewhere in this programme" case can be told apart from a suppressed one.

- [ ] **Step 7: Give the cover story an anchor target**

In `ui/src/components/MatchNotes.tsx` line 279, change:

```tsx
<h3>{FACT_DISPLAY[view.hero.id]?.title ?? "The headline number"}</h3>
```

to:

```tsx
<h3 id="mn-cover-title">{FACT_DISPLAY[view.hero.id]?.title ?? "The headline number"}</h3>
```

- [ ] **Step 8: Replace the flat grid**

In `ui/src/components/MatchNotes.tsx`, replace line 289 entirely:

```tsx
      {view.cards.length > 0 && <section className="mn-section" aria-labelledby="mn-stats-title"><div className="mn-section__head"><span className="upper">Deeper cut</span><h3 id="mn-stats-title">Signature stats &amp; records</h3></div><div className="mn-stats-grid">{view.cards.map((fact, index) => <FactCard fact={fact} index={index + 1} key={factKey(fact)} />)}</div></section>}
```

with:

```tsx
      <StatForStat grouped={view.grouped} home={view.home} away={view.away} expert={props.expert} />
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `cd ui && npx vitest run src/components/MatchNotes.test.tsx src/lib/factPairs.test.ts`
Expected: PASS, 21 tests.

- [ ] **Step 10: Typecheck and lint**

Run: `cd ui && npm run typecheck && npm run lint`
Expected: both exit 0.

- [ ] **Step 11: Commit**

```bash
git add ui/src/components/MatchNotes.tsx ui/src/components/MatchNotes.test.tsx
git commit -s -m "feat(ui): render the deeper cut as a stat-for-stat comparison

The section put competition, home-team and away-team facts in one flat grid
in array order, so the reader re-oriented at every card. It now reads as a
three-column table: the tournament band, the stats both sides qualify for,
then the stats only one side does — each blank side saying why it is blank.

Numbering is dropped here because the order was array residue; Quick
briefing keeps its numbers, where topInsights genuinely ranks."
```

---

### Task 3: Style the comparison

**Files:**
- Modify: `ui/src/index.css:2884` (drop the dead `.mn-stats-grid` selector) and insert the new block after line 2893

**Interfaces:**
- Consumes: the class names emitted in Task 2 — `mn-compare`, `mn-compare__stage`, `mn-compare__table`, `mn-compare__team--home`, `mn-compare__team--away`, `mn-compare__stat`, `mn-compare__explainer`, `mn-compare__cell`, `mn-compare__cell--home`, `mn-compare__cell--away`, `mn-compare__cell--absent`, `mn-compare__value`, `mn-compare__rail`, `mn-compare__fill`, `mn-compare__absent`, `mn-compare__detail`, `mn-compare__solo`, `mn-compare__other`.
- Produces: no code interface.

- [ ] **Step 1: Retire the dead selector**

`.mn-stats-grid` had exactly one usage — the block Task 2 replaced. In `ui/src/index.css` line 2884, change:

```css
.mn-feature-grid, .mn-stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 17rem), 1fr)); gap: .75rem; }
```

to:

```css
.mn-feature-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 17rem), 1fr)); gap: .75rem; }
```

- [ ] **Step 2: Add the comparison block**

In `ui/src/index.css`, insert immediately after line 2893 (the `.mn-fact__proof > span` rule, before `.mn-h2h__bar`):

```css
.mn-compare__stage { display: flex; flex-wrap: wrap; align-items: baseline; gap: .5rem 1rem; margin-top: .9rem; padding: .7rem .9rem; border-left: 2px solid var(--wave); background: color-mix(in srgb, var(--surface-2) 58%, transparent); }
.mn-compare__stage > .upper { color: var(--wave); }
.mn-compare__stage ul { display: flex; flex-wrap: wrap; gap: .35rem 1.4rem; margin: 0; padding: 0; list-style: none; }
.mn-compare__stage li { display: flex; flex-wrap: wrap; align-items: baseline; gap: .4rem; min-width: 0; }
.mn-compare__stage strong { color: var(--gold); font-size: 1.15rem; font-weight: 400; }
.mn-compare__stage span { color: var(--text-muted); font-size: var(--text-sm); }
.mn-compare__table { width: 100%; margin-top: 1rem; border-collapse: collapse; }
.mn-compare__table thead th { padding: 0 0 .5rem; border-bottom: 1px solid var(--border-strong); color: var(--text-dim); font: 650 .7rem/1 var(--font-sans); letter-spacing: .09em; text-transform: uppercase; text-align: left; }
.mn-compare__team--home { color: var(--home); text-align: right; }
.mn-compare__team--away { color: var(--away); }
.mn-compare__table tbody tr { border-bottom: 1px solid var(--border); }
.mn-compare__stat { width: 40%; padding: .7rem .9rem .7rem 0; font-size: 1rem; font-weight: 400; text-align: left; vertical-align: top; }
.mn-compare__explainer { margin: .25rem 0 0; max-width: 42ch; color: var(--text-muted); font-size: var(--text-sm); line-height: 1.45; }
.mn-compare__cell { width: 30%; padding: .7rem 0; vertical-align: top; }
.mn-compare__cell--home { padding-right: .7rem; text-align: right; }
.mn-compare__cell--away { padding-left: .7rem; text-align: left; }
.mn-compare__value { display: block; font-size: 1.4rem; }
.mn-compare__cell--home .mn-compare__value { color: var(--home); }
.mn-compare__cell--away .mn-compare__value { color: var(--away); }
.mn-compare__rail { display: flex; height: .5rem; margin-top: .35rem; background: var(--surface-3); }
.mn-compare__cell--home .mn-compare__rail { justify-content: flex-end; }
.mn-compare__fill { height: 100%; }
.mn-compare__cell--home .mn-compare__fill { background: var(--home); }
.mn-compare__cell--away .mn-compare__fill { background: var(--away); }
.mn-compare__absent { color: var(--text-dim); font-size: var(--text-sm); font-style: italic; }
a.mn-compare__absent { color: var(--link); font-style: normal; }
.mn-compare__detail { margin-top: .45rem; }
.mn-compare__detail summary { width: fit-content; cursor: pointer; color: var(--link); font-size: var(--text-xs); }
.mn-compare__cell--home .mn-compare__detail summary { margin-left: auto; }
.mn-compare__detail > p { margin: .35rem 0 0; color: var(--text-muted); font-size: var(--text-sm); line-height: 1.5; text-align: left; }
.mn-compare__cell--home .mn-fact__proof { justify-content: flex-end; }
.mn-compare__solo, .mn-compare__other { margin-top: 1.3rem; }
.mn-compare__solo > .upper { color: var(--text-dim); }
@media (max-width: 46rem) {
  .mn-compare__rail { display: none; }
  .mn-compare__stat { width: 46%; }
  .mn-compare__value { font-size: 1.15rem; }
}
```

Every selector sits in the single `.mn-compare__*` namespace, so nothing collides with the `.mn-fact` or `.mn-section` rules above it. The one deliberate reach outside that namespace is `.mn-compare__cell--home .mn-fact__proof`, which right-aligns the shared proof strip inside the home column only.

- [ ] **Step 3: Verify the build compiles the stylesheet**

Run: `cd ui && npm run build`
Expected: exit 0, `dist/` written.

- [ ] **Step 4: Commit**

```bash
git add ui/src/index.css
git commit -s -m "style(ui): dress the stat-for-stat comparison

Home and away keep the --home/--away coding the head-to-head band above
already teaches. Rails are hidden below 46rem: they are aria-hidden
decoration duplicating the numeric cell, so narrow screens lose nothing."
```

---

### Task 4: Verify the whole gate

**Files:** none modified — this task only runs checks and looks at the result.

**Interfaces:** none.

- [ ] **Step 1: Run the full UI test suite**

Run: `cd ui && npm test -- --run`
Expected: PASS. The suite grew by two files; no previously passing test may fail.

- [ ] **Step 2: Typecheck and lint**

Run: `cd ui && npm run typecheck && npm run lint`
Expected: both exit 0. Lint runs `--deny-warnings`, so any warning is a failure.

- [ ] **Step 3: Confirm the fixture actually produces the new shape**

Run:

```bash
cd ui && npx vitest run src/lib/factPairs.test.ts --reporter=verbose
```

Expected: the ordering and absence tests pass, including "points at the section holding a promoted twin".

- [ ] **Step 4: Look at the rendered section**

Start the dev server and open a fixture match, then toggle Casual/Expert:

```bash
make dev
```

Confirm by eye:
- the tournament band sits above the table and reads as background, not as a third team
- home values are gold and right-aligned, away values orange and left-aligned
- rails appear on percentage rows and not on count rows
- a blank side reads "No qualifying sample" or "Shown in …", never a bare dash
- Casual shows the explainer under each stat name; Expert shows the source proof instead
- narrowing the window below ~736px drops the rails and keeps every number

- [ ] **Step 5: Commit any fixes, then stop**

If steps 1–4 required changes, commit them with a `fix(ui):` message. If not, nothing to commit — the plan is complete.

---

## Self-review

**Spec coverage.** Every spec section maps to a task: the honesty contract and the `elsewhere` label table → Task 1 Step 3 (`buildElsewhere`) and Task 2 Step 4 (`CompareCell`); the rail rule → Task 1 (`rail` field) and Task 2 (`CompareCell` guard); data grouping and ordering → Task 1 Step 3; rendering and markup → Task 2 Steps 4–8; density via the expert toggle → Task 2 Step 4; the visual spec → Task 3; testing → Task 1 Step 1 and Task 2 Step 1; the `.mn-stats-grid` retirement → Task 3 Step 1; the `#mn-cover-title` addition → Task 2 Step 7. The spec's "What could break" list is exercised by Task 4.

**Type consistency.** `GroupedFacts` carries `tournament` / `paired` / `solo` / `other` in Task 1 and is destructured under those exact names in Task 2. `FactSide` is `{ fact, absence }` in both. `Absence` uses `kind` / `section` / `anchor` throughout. `StatForStat` takes `{ grouped, home, away, expert }` where it is defined, tested, and called.

**Known deviation from the spec.** The spec's file table did not mention making `FactCard`'s `index` optional. Task 2 Step 5 does, because the `other` fallback band has no meaningful order and numbering it would repeat the false-sequence problem this change exists to remove. The three existing call sites still pass `index` and are unaffected.
