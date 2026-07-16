import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { MatchAnalysis } from "../lib/contract";
import { AnalysisExplainer } from "./AnalysisExplainer";

const analysis = {
  explanation: {
    schema_version: "0.1.0",
    descriptive_only: true,
    hypothetical_only: true,
    averaged_consensus: false,
    calibrated_confidence: false,
    causal_claims: false,
    sealed_forecast_immutable: true,
    analysis_kind: "preview",
    history_support: {
      level: "moderate",
      minimum_qualifying_matches: 27,
      model_floor: 10,
      meaning: "training coverage only; not forecast confidence or accuracy",
    },
    disagreement: {
      status: "modal_split",
      voices: [
        { family: "elo_ordlogit", method: "ratings", modal_outcome: "home" },
        { family: "dixon_coles", method: "goals", modal_outcome: "draw" },
      ],
      outcome_gap_percentage_points: { home: 8.4, draw: 4.2, away: 4.2 },
      largest_gap: { outcome: "home", percentage_points: 8.4 },
      meaning: "descriptive probability gaps between the ratings and goals voices",
    },
    change_triggers: [{
      id: "verified_source_refresh",
      label: "Verified source data changes",
      description: "The live analysis is recomputed.",
    }],
    capability_coverage: {
      available_count: 3,
      assessed_count: 6,
      meaning: "known data and product capabilities only; not model quality or accuracy",
      items: [],
    },
    missing_evidence: ["verified_lineups", "verified_injuries", "observed_xg"],
    provenance: {
      source_ids: ["martj42-international-results"],
      engine_source_id: "engine:match_analysis",
      formula_version: "analysis-explanation-1",
      input_fields: ["models[].probs"],
    },
  },
} as unknown as MatchAnalysis;

describe("AnalysisExplainer", () => {
  it("labels support, hypothetical triggers, missing evidence and provenance honestly", () => {
    const html = renderToStaticMarkup(createElement(AnalysisExplainer, {
      analysis,
      home: "France",
      away: "Spain",
    }));

    expect(html).toContain("Depth without false certainty");
    expect(html).toContain("Moderate history");
    expect(html).toContain("27");
    expect(html).toContain("8.4 percentage points on France");
    expect(html).toContain("No probabilities are averaged");
    expect(html).toContain("What would change this analysis?");
    expect(html).toContain("never rewrite a sealed forecast");
    expect(html).toContain("no verified lineup, injury, or observed-xG feed");
    expect(html).toContain("analysis-explanation-1");
    expect(html).not.toContain("confidence score");
  });
});
