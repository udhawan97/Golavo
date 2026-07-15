import { describe, expect, it } from "vitest";
import type { CommentatorsNotebook, FactLabel, MatchAnalysis, NotebookFact } from "./contract";
import { chapterPullNumber, topInsights } from "./insights";

let seq = 0;
function mk(over: Partial<NotebookFact> & { label: FactLabel }): NotebookFact {
  seq += 1;
  return {
    id: over.id ?? `fact_${seq}`,
    version: "1.0.0",
    scope: "team",
    subject: "Test",
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

function notebook(facts: NotebookFact[]): CommentatorsNotebook {
  return {
    schema_version: "0.1.0",
    notebook_id: "nb_test",
    registry_version: "2026.01",
    as_of_utc: "2026-01-01T00:00:00Z",
    match: { home_team: "A", away_team: "B", competition: "C", neutral_venue: false },
    source_ids: ["sp_x"],
    family_size: 10,
    coincidence_cap: 3,
    facts,
    suppressed: [],
    generator: "test",
  };
}

function analysis(overrides: Partial<MatchAnalysis> = {}): MatchAnalysis {
  return {
    schema_version: "0.4.1",
    analysis_kind: "preview",
    match: {
      match_id: "m1",
      competition: "C",
      kickoff_utc: "2026-01-02T00:00:00Z",
      home_team: "A",
      away_team: "B",
      neutral_venue: false,
      is_complete: false,
    },
    information_cutoff_utc: "2026-01-01T00:00:00Z",
    abstained: false,
    abstain_reason: null,
    uncertainty: "medium",
    team_history: { A: 20, B: 20 },
    min_team_matches: 8,
    council: {
      voices: 2,
      voices_agree: true,
      leading_outcome: "home",
      max_delta_p: 0.1,
      outcome_range: null,
    },
    models: [],
    score_matrix: null,
    score_matrix_family: null,
    ...overrides,
  };
}

describe("topInsights", () => {
  it("returns nothing for a null or empty notebook", () => {
    expect(topInsights(null)).toEqual([]);
    expect(topInsights(notebook([]))).toEqual([]);
  });

  it("leads with the fact closest to this fixture (scope), not the most specific one", () => {
    // A broad head-to-head still beats a razor-specific team fact.
    const h2h = mk({ id: "h2h", scope: "head_to_head", label: "context", specificity: 0.1 });
    const team = mk({ id: "team", scope: "team", label: "predictive", specificity: 0.9 });
    const comp = mk({ id: "comp", scope: "competition", label: "predictive", specificity: 1.0 });
    const out = topInsights(notebook([comp, team, h2h]));
    expect(out.map((f) => f.id)).toEqual(["h2h", "team", "comp"]);
  });

  it("within a scope, prefers higher specificity, then predictive over context", () => {
    const a = mk({ id: "spec_hi", scope: "team", label: "context", specificity: 0.9 });
    const b = mk({ id: "spec_lo_pred", scope: "team", label: "predictive", specificity: 0.4 });
    const c = mk({ id: "spec_lo_ctx", scope: "team", label: "context", specificity: 0.4 });
    const out = topInsights(notebook([c, b, a]));
    expect(out.map((f) => f.id)).toEqual(["spec_hi", "spec_lo_pred", "spec_lo_ctx"]);
  });

  it("never includes coincidences", () => {
    const coincidence = mk({ id: "coin", scope: "head_to_head", label: "coincidence", specificity: 1.0 });
    const context = mk({ id: "ctx", scope: "team", label: "context", specificity: 0.2 });
    const out = topInsights(notebook([coincidence, context]));
    expect(out.map((f) => f.id)).toEqual(["ctx"]);
  });

  it("drops stale facts", () => {
    const fresh = mk({ id: "fresh", scope: "team", label: "context", specificity: 0.3 });
    const stale = mk({
      id: "stale",
      scope: "head_to_head",
      label: "context",
      specificity: 0.9,
      freshness: { as_of_utc: "x", last_event_utc: "x", age_days: 9999, stale: true, staleness_days: 9999 },
    });
    const out = topInsights(notebook([stale, fresh]));
    expect(out.map((f) => f.id)).toEqual(["fresh"]);
  });

  it("breaks full ties by sample size then id", () => {
    const a = mk({ id: "b_more", scope: "team", label: "context", specificity: 0.5, sample_n: 500 });
    const b = mk({ id: "a_less", scope: "team", label: "context", specificity: 0.5, sample_n: 50 });
    const out = topInsights(notebook([b, a]));
    expect(out.map((f) => f.id)).toEqual(["b_more", "a_less"]);
  });

  it("caps at the requested limit and is stable", () => {
    const facts = Array.from({ length: 6 }, (_, i) =>
      mk({ id: `p${i}`, scope: "team", label: "predictive", specificity: i / 10 }),
    );
    const a = topInsights(notebook(facts), 3);
    const b = topInsights(notebook(facts.slice().reverse()), 3);
    expect(a).toHaveLength(3);
    expect(a.map((f) => f.id)).toEqual(b.map((f) => f.id));
  });
});

describe("chapterPullNumber", () => {
  const context = { analysis: null, notebook: null };

  it("leaves chapters quiet when no already-rendered number qualifies", () => {
    expect(chapterPullNumber("form", context)).toBeNull();
    expect(chapterPullNumber("history", context)).toBeNull();
  });

  it("selects the longest current form run with stable result and team tie-breaks", () => {
    const entry = (result: "W" | "D" | "L", date: string) => ({
      result, opponent: "X", gf: result === "W" ? 2 : 1, ga: result === "L" ? 2 : 1,
      date, is_home: false, neutral: false,
    });
    const value = chapterPullNumber("form", {
      analysis: analysis({
        team_form: {
          B: [entry("W", "1"), entry("W", "2"), entry("W", "3")],
          A: [entry("W", "1"), entry("W", "2"), entry("W", "3")],
        },
      }),
      notebook: null,
    });
    expect(value).toMatchObject({ value: "3", takeaway: "A: Three away wins in a row." });
  });

  it("selects the style multiplier furthest from the engine baseline", () => {
    const value = chapterPullNumber("style", {
      analysis: analysis({
        team_style: {
          family: "dixon_coles",
          derivation: "fitted_from_results",
          baseline: 1,
          clip: { min: 0.2, max: 3 },
          teams: {
            A: { attack: 1.08, defence: 0.92, expected_goals_for: null, expected_goals_against: null },
            B: { attack: 1.24, defence: 1.04, expected_goals_for: null, expected_goals_against: null },
          },
        },
      }),
      notebook: null,
    });
    expect(value).toMatchObject({ value: "1.24×", label: "Fitted multiplier" });
    expect(value?.takeaway).toContain("B's attack");
  });

  it("uses the same ranked notebook fact and display value as the history chapter", () => {
    const fact = mk({
      id: "unbeaten_run",
      scope: "head_to_head",
      label: "context",
      text: "A are unbeaten in four meetings.",
      base_rate: 0.625,
    });
    expect(chapterPullNumber("history", { analysis: null, notebook: notebook([fact]) })).toMatchObject({
      label: "Unbeaten run",
      value: "63%",
      takeaway: "A are unbeaten in four meetings.",
    });
  });

  it("selects the strongest voice probability and exact-score verdict deterministically", () => {
    const current = analysis({
      models: [
        {
          family: "elo_ordlogit", role: "voice", method: "ratings", abstained: false,
          probs: { home: 0.61, draw: 0.22, away: 0.17 }, expected_goals: null, score_matrix: null, params: {},
        },
        {
          family: "dixon_coles", role: "voice", method: "goals", abstained: false,
          probs: { home: 0.58, draw: 0.24, away: 0.18 }, expected_goals: null, score_matrix: null, params: {},
        },
      ],
      score_matrix: {
        max_goals: 6, resolution: 12, grid: [[0.1]],
        tail: { probability: 0, home: 0, draw: 0, away: 0 },
        most_likely: { home: 2, away: 1, probability: 0.1234 }, total_probability: 1,
      },
    });
    expect(chapterPullNumber("models", { analysis: current, notebook: null })).toMatchObject({ value: "61.0%" });
    expect(chapterPullNumber("verdict", { analysis: current, notebook: null })).toMatchObject({
      value: "2–1",
      takeaway: "12.3% for this exact scoreline in the goal model.",
    });
  });
});
