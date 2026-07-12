/**
 * "Three things to know" — a pure, deterministic selector over the notebook's
 * own facts. It invents nothing and re-weights nothing: it only PICKS a few of
 * the facts the engine already computed, by a fixed, documented rule.
 *
 * The rule leads with the facts CLOSEST to this fixture, so a head-to-head
 * record surfaces above a competition-wide base rate:
 *   1. scope closeness — head_to_head (both these teams) → match → team →
 *      competition (broad background).
 *   2. specificity, descending — within a scope, a more specific fact wins.
 *   3. label priority — predictive (labelled base rate) before context on a tie.
 *   4. sample size, descending — more evidence beats less.
 *   5. fact id, ascending — a stable tie-break so the pick never wobbles.
 *
 * Coincidences are excluded entirely (they are "for the pub"), and stale facts
 * are dropped (the same freshness guard the notebook already applies). The same
 * notebook always yields the same three facts, in the same order — which is what
 * lets the UI label them "chosen by fixed rules, not AI".
 */
import type { CommentatorsNotebook, FactLabel, FactScope, NotebookFact } from "./contract";

/** Closeness to THIS fixture: both-team facts first, broad background last. */
const SCOPE_RANK: Record<FactScope, number> = {
  head_to_head: 0,
  match: 1,
  team: 2,
  competition: 3,
};

const LABEL_RANK: Record<FactLabel, number> = {
  predictive: 0,
  context: 1,
  coincidence: 99, // excluded before ranking; kept here so the type is total
};

/** Returns up to `limit` facts, closest-to-this-fixture first. Never
 *  coincidences, never stale. Pure: no dates, no randomness, no I/O. */
export function topInsights(
  notebook: CommentatorsNotebook | null,
  limit = 3,
): NotebookFact[] {
  if (!notebook) return [];
  return notebook.facts
    .filter((f) => f.label !== "coincidence" && !f.freshness.stale)
    .slice() // don't mutate the source array's order
    .sort(
      (a, b) =>
        SCOPE_RANK[a.scope] - SCOPE_RANK[b.scope] ||
        b.specificity - a.specificity ||
        LABEL_RANK[a.label] - LABEL_RANK[b.label] ||
        b.sample_n - a.sample_n ||
        a.id.localeCompare(b.id),
    )
    .slice(0, limit);
}
