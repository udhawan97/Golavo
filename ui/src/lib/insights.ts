/**
 * "Three things to know" — a pure, deterministic selector over the notebook's
 * own facts. It invents nothing and re-weights nothing: it only PICKS a few of
 * the facts the engine already computed, by a fixed, documented rule.
 *
 * The ordering is intentionally boring so it can never look editorial or
 * AI-curated:
 *   1. label priority — predictive (labelled base rates) before context;
 *      coincidences are excluded entirely (they are "for the pub").
 *   2. specificity, descending — a fact about this exact fixture beats a
 *      competition-wide one.
 *   3. sample size, descending — more evidence beats less.
 *   4. fact id, ascending — a stable tie-break so the pick never wobbles.
 *
 * Stale facts are dropped (the same freshness guard the notebook already
 * applies). The same notebook always yields the same three facts, in the same
 * order — which is what lets the UI label them "chosen by fixed rules, not AI".
 */
import type { CommentatorsNotebook, FactLabel, NotebookFact } from "./contract";

const LABEL_RANK: Record<FactLabel, number> = {
  predictive: 0,
  context: 1,
  coincidence: 99, // excluded before ranking; kept here so the type is total
};

/** Returns up to `limit` facts, most worth-knowing first. Never coincidences,
 *  never stale. Pure: no dates, no randomness, no I/O. */
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
        LABEL_RANK[a.label] - LABEL_RANK[b.label] ||
        b.specificity - a.specificity ||
        b.sample_n - a.sample_n ||
        a.id.localeCompare(b.id),
    )
    .slice(0, limit);
}
