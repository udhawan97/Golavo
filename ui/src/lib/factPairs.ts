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
