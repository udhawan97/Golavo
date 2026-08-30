import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { MatchAnalysis } from "../lib/contract";
import { MatchStudyDesk } from "./MatchStudyDesk";

const analysis = {
  schema_version: "0.4.1",
  analysis_kind: "preview",
  match: {
    match_id: "m-study",
    competition: "English Premier League",
    kickoff_utc: "2026-08-31T17:00:00Z",
    home_team: "Alpha",
    away_team: "Beta",
    neutral_venue: false,
    is_complete: false,
    source_id: "test",
  },
  information_cutoff_utc: "2026-08-30T16:59:59Z",
  abstained: false,
  abstain_reason: null,
  uncertainty: "medium",
  team_history: { Alpha: 80, Beta: 75 },
  min_team_matches: 75,
  council: { voices: 2, voices_agree: false, leading_outcome: null, max_delta_p: 0.08, outcome_range: null },
  models: [
    { family: "elo_ordlogit", role: "voice", method: "ratings", abstained: false, probs: { home: .51, draw: .27, away: .22 }, expected_goals: null, score_matrix: null, params: null },
    { family: "dixon_coles", role: "voice", method: "goals", abstained: false, probs: { home: .45, draw: .30, away: .25 }, expected_goals: { home: 1.5, away: 1 }, score_matrix: null, params: null },
  ],
  score_matrix_family: "dixon_coles",
  score_matrix: {
    max_goals: 1,
    resolution: 1,
    grid: [[.15, .12], [.25, .18]],
    tail: { probability: .30, home: .15, draw: .02, away: .13 },
    most_likely: { home: 1, away: 0, probability: .25 },
    total_probability: 1,
  },
  derived_markets: { family: "dixon_coles", source: "full_resolution_matrix", btts: { yes: .56, no: .44 }, clean_sheets: { home: .34, away: .27 } },
  explanation: {
    schema_version: "0.1.0",
    descriptive_only: true,
    hypothetical_only: true,
    averaged_consensus: false,
    calibrated_confidence: false,
    causal_claims: false,
    sealed_forecast_immutable: true,
    analysis_kind: "preview",
    history_support: { level: "strong", minimum_qualifying_matches: 75, model_floor: 30, meaning: "history" },
    disagreement: { status: "modal_split", voices: [], outcome_gap_percentage_points: null, largest_gap: { outcome: "home", percentage_points: 6 }, meaning: "split" },
    change_triggers: [],
    capability_coverage: { available_count: 0, assessed_count: 0, meaning: "", items: [] },
    missing_evidence: ["verified_lineups"],
    provenance: { source_ids: ["engine"], engine_source_id: "engine:match_analysis", formula_version: "analysis-explanation-1", input_fields: [] },
  },
} as MatchAnalysis;

describe("MatchStudyDesk", () => {
  it("keeps model voices separate and labels mathematical equivalents narrowly", () => {
    const html = renderToStaticMarkup(createElement(MatchStudyDesk, {
      analysis, loading: false, error: null, unavailableReason: null, onRetry: () => {}, home: "Alpha", away: "Beta",
    }));
    expect(html).toContain("Elo ratings");
    expect(html).toContain("Dixon–Coles");
    expect(html).toContain("Voices split");
    expect(html).toContain("1/p");
    expect(html).toContain("no margin, market movement or recommendation");
    expect(html).not.toContain("best bet");
    expect(html).not.toContain("Clean-sheet edge");
    expect(html).toContain("History support means: history");
    expect(html).toContain("Model families:");
    expect(html).toContain("elo_ordlogit");
    expect(html).toContain("dixon_coles");
    expect(html).toContain("Sources:");
    expect(html).toContain("engine:match_analysis");
    expect(html).toContain("test");
  });

  it("renders unsupported target forecasts as explicit unavailable states", () => {
    const html = renderToStaticMarkup(createElement(MatchStudyDesk, {
      analysis, loading: false, error: null, unavailableReason: null, onRetry: () => {}, home: "Alpha", away: "Beta",
    }));
    expect(html).toContain("Scorer forecast");
    expect(html).toContain("Corner forecast");
    expect(html).toContain("Card forecast");
    expect(html.match(/Unavailable/g)).toHaveLength(3);
  });

  it("preserves the exact unavailable reason instead of inventing a history failure", () => {
    const html = renderToStaticMarkup(createElement(MatchStudyDesk, {
      analysis: null,
      loading: false,
      error: null,
      unavailableReason: "This sample-data preview has no engine to fit the models.",
      onRetry: () => {},
      home: "Alpha",
      away: "Beta",
    }));
    expect(html).toContain("This sample-data preview has no engine to fit the models.");
    expect(html).not.toContain("did not clear the history");
  });

  it("renders request errors distinctly with a retry action", () => {
    const html = renderToStaticMarkup(createElement(MatchStudyDesk, {
      analysis: null,
      loading: false,
      error: new Error("engine offline"),
      unavailableReason: null,
      onRetry: () => {},
      home: "Alpha",
      away: "Beta",
    }));
    expect(html).toContain("Analysis error");
    expect(html).toContain("engine offline");
    expect(html).toContain("Retry analysis");
  });

  it("uses the engine abstention reason without relabeling it", () => {
    const html = renderToStaticMarkup(createElement(MatchStudyDesk, {
      analysis: { ...analysis, abstained: true, abstain_reason: "kickoff precision is unavailable" },
      loading: false,
      error: null,
      unavailableReason: null,
      onRetry: () => {},
      home: "Alpha",
      away: "Beta",
    }));
    expect(html).toContain("Models abstained");
    expect(html).toContain("kickoff precision is unavailable");
  });
});
