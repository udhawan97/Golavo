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
import {
  FACT_DISPLAY,
  FAMILY_LABELS,
  type CommentatorsNotebook,
  type FactLabel,
  type FactScope,
  type MatchAnalysis,
  type NotebookFact,
  type Outcome,
} from "./contract";
import { pct } from "./format";
import { formStreakSentence } from "./matchProgramme";

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

export type ProgrammePullChapter = "form" | "style" | "history" | "models" | "verdict";

export interface ProgrammePullNumber {
  label: string;
  value: string;
  takeaway: string;
  ariaLabel: string;
}

export interface ProgrammePullContext {
  analysis: MatchAnalysis | null;
  notebook: CommentatorsNotebook | null;
}

const OUTCOME_ORDER: Outcome[] = ["home", "draw", "away"];

function formPull(analysis: MatchAnalysis): ProgrammePullNumber | null {
  const candidates = Object.entries(analysis.team_form ?? {}).flatMap(([team, entries]) => {
    const sentence = formStreakSentence(entries);
    if (!sentence) return [];
    const newest = entries.at(-1)!;
    let count = 1;
    for (let i = entries.length - 2; i >= 0 && entries[i].result === newest.result; i -= 1) count += 1;
    return [{ team, count, result: newest.result, sentence }];
  });
  const resultRank = { W: 0, D: 1, L: 2 } as const;
  const best = candidates.sort(
    (a, b) => b.count - a.count || resultRank[a.result] - resultRank[b.result] || a.team.localeCompare(b.team),
  )[0];
  if (!best) return null;
  const takeaway = `${best.team}: ${best.sentence}`;
  return {
    label: "Current run",
    value: String(best.count),
    takeaway,
    ariaLabel: `Form highlight: ${best.count}. ${takeaway}`,
  };
}

function stylePull(analysis: MatchAnalysis): ProgrammePullNumber | null {
  const style = analysis.team_style;
  if (!style) return null;
  const candidates = Object.entries(style.teams).flatMap(([team, entry]) => [
    { team, metric: "attack" as const, value: entry.attack },
    { team, metric: "defence" as const, value: entry.defence },
  ]);
  const best = candidates.sort(
    (a, b) =>
      Math.abs(b.value - style.baseline) - Math.abs(a.value - style.baseline) ||
      a.team.localeCompare(b.team) ||
      a.metric.localeCompare(b.metric),
  )[0];
  if (!best) return null;
  const value = `${best.value.toFixed(2)}×`;
  const takeaway = `${best.team}'s ${best.metric} is the largest departure from the ${style.baseline.toFixed(1)} dataset baseline.`;
  return {
    label: "Fitted multiplier",
    value,
    takeaway,
    ariaLabel: `Style highlight: ${value}. ${takeaway}`,
  };
}

function historyPull(notebook: CommentatorsNotebook): ProgrammePullNumber | null {
  const fact = topInsights(notebook, 1)[0];
  if (!fact) return null;
  const value = fact.base_rate !== null ? `${Math.round(fact.base_rate * 100)}%` : fact.numbers[0]?.display;
  if (!value) return null;
  const label = FACT_DISPLAY[fact.id]?.title ?? "Match record";
  return {
    label,
    value,
    takeaway: fact.text,
    ariaLabel: `History highlight: ${label}, ${value}. ${fact.text}`,
  };
}

function modelsPull(analysis: MatchAnalysis): ProgrammePullNumber | null {
  const candidates = analysis.models.flatMap((model) =>
    model.role === "voice" && !model.abstained && model.probs
      ? OUTCOME_ORDER.map((outcome, order) => ({ model, outcome, order, probability: model.probs![outcome] }))
      : [],
  );
  const best = candidates.sort(
    (a, b) =>
      b.probability - a.probability ||
      FAMILY_LABELS[a.model.family].localeCompare(FAMILY_LABELS[b.model.family]) ||
      a.order - b.order,
  )[0];
  if (!best) return null;
  const outcome =
    best.outcome === "home"
      ? analysis.match.home_team
      : best.outcome === "away"
        ? analysis.match.away_team
        : "the draw";
  const value = pct(best.probability);
  const takeaway = `${FAMILY_LABELS[best.model.family]} gives ${outcome} the strongest single council reading.`;
  return {
    label: "Strongest model reading",
    value,
    takeaway,
    ariaLabel: `Models highlight: ${value}. ${takeaway}`,
  };
}

function verdictPull(analysis: MatchAnalysis): ProgrammePullNumber | null {
  const score = analysis.score_matrix?.most_likely;
  if (!score || analysis.abstained) return null;
  const value = `${score.home}–${score.away}`;
  const takeaway = `${pct(score.probability)} for this exact scoreline in the goal model.`;
  return {
    label: "Most likely score",
    value,
    takeaway,
    ariaLabel: `Verdict highlight: ${value}. ${takeaway}`,
  };
}

/** One deterministic editorial highlight per chapter, selected only from
 * values that chapter already renders. Null means the programme leaves the
 * page quiet rather than manufacturing a headline. */
export function chapterPullNumber(
  chapter: ProgrammePullChapter,
  { analysis, notebook }: ProgrammePullContext,
): ProgrammePullNumber | null {
  if (chapter === "history") return notebook ? historyPull(notebook) : null;
  if (!analysis) return null;
  if (chapter === "form") return formPull(analysis);
  if (chapter === "style") return stylePull(analysis);
  if (chapter === "models") return modelsPull(analysis);
  return verdictPull(analysis);
}
