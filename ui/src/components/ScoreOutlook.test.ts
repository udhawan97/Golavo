import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { MatchAnalysis } from "../lib/contract";
import { ScoreOutlook } from "./ScoreOutlook";

const analysis: MatchAnalysis = {
  schema_version: "0.4.1",
  analysis_kind: "preview",
  match: {
    match_id: "m_design_test",
    competition: "Design test",
    kickoff_utc: "2030-01-01T12:00:00Z",
    home_team: "France",
    away_team: "Spain",
    neutral_venue: true,
    is_complete: false,
  },
  information_cutoff_utc: "2029-12-31T12:00:00Z",
  abstained: false,
  abstain_reason: null,
  uncertainty: "medium",
  team_history: { France: 20, Spain: 20 },
  min_team_matches: 20,
  council: {
    voices: 1,
    voices_agree: true,
    leading_outcome: "draw",
    max_delta_p: 0,
    outcome_range: null,
  },
  models: [{
    family: "poisson_independent",
    role: "voice",
    method: "goals",
    abstained: false,
    probs: { home: 0.34, draw: 0.36, away: 0.3 },
    expected_goals: { home: 1.35, away: 1.2 },
    score_matrix: {
      grid: [
        [0.08, 0.1, 0.06],
        [0.11, 0.14, 0.09],
        [0.08, 0.09, 0.05],
      ],
      max_goals: 2,
      most_likely: { home: 1, away: 1, probability: 0.14 },
      resolution: 20,
      tail: { home: 0.04, draw: 0.01, away: 0.05, probability: 0.1 },
      total_probability: 1,
    },
    params: null,
  }],
  score_matrix: null,
  score_matrix_family: "poisson_independent",
  derived_markets: {
    family: "poisson_independent",
    source: "full_resolution_matrix",
    btts: { yes: 0.53, no: 0.47 },
    clean_sheets: { home: 0.24, away: 0.3 },
  },
};

describe("ScoreOutlook market dashboard", () => {
  it("keeps a compact exact-data preview ahead of the expert analytical details", () => {
    const html = renderToStaticMarkup(createElement(ScoreOutlook, {
      analysis,
      home: "France",
      away: "Spain",
      expert: true,
    }));

    expect(html).toContain("Most balanced line");
    expect(html).toContain("Clean-sheet edge");
    expect(html).toContain("Goal peak");
    expect(html).toContain("Total-goal distribution");
    expect(html).toContain('aria-label="Total-goal probability distribution"');
    expect(html).toContain("Expected total");
    expect(html).toContain("Exact-score matrix");
    expect(html).toContain("Spain");
  });

  it("calls equal clean-sheet probabilities level instead of inventing an edge", () => {
    const tiedAnalysis: MatchAnalysis = {
      ...analysis,
      derived_markets: {
        ...analysis.derived_markets!,
        clean_sheets: { home: 0.25, away: 0.25 },
      },
    };
    const html = renderToStaticMarkup(createElement(ScoreOutlook, {
      analysis: tiedAnalysis,
      home: "France",
      away: "Spain",
      expert: true,
    }));

    expect(html).toContain("Clean sheets level");
    expect(html).toContain("Even");
    expect(html).toContain("25.0% each");
    expect(html).not.toContain("Clean-sheet edge");
  });

  it("reveals exact double-chance and outcome-tail rows only in expert mode", () => {
    const casual = renderToStaticMarkup(createElement(ScoreOutlook, {
      analysis,
      home: "France",
      away: "Spain",
    }));
    const expert = renderToStaticMarkup(createElement(ScoreOutlook, {
      analysis,
      home: "France",
      away: "Spain",
      expert: true,
    }));

    expect(casual).toContain("widest safety net");
    expect(casual).not.toContain("Double chance");
    expect(casual).not.toContain("Beyond the grid");
    expect(casual).not.toContain("Total-goal distribution");
    expect(casual).not.toContain("Exact-score matrix");
    expect(expert).toContain("Double chance");
    expect(expert).toContain("1X");
    expect(expert).toContain("Beyond the grid");
    expect(expert).toContain("10.0%");
    expect(expert).toContain("Per-team totals are not shown");
    expect(expert).toContain("Total-goal distribution");
    expect(expert).toContain("Exact-score matrix");
  });
});
