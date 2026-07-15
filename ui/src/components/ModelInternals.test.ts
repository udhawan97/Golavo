import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { MatchAnalysis } from "../lib/contract";
import { ModelInternals } from "./ModelInternals";

const analysis = {
  team_style: {
    family: "dixon_coles",
    derivation: "fitted_from_results",
    baseline: 1,
    clip: { min: 0.35, max: 2.8 },
    teams: {
      France: { attack: 1.24, defence: 0.9, expected_goals_for: 1.4, expected_goals_against: 1.1 },
      Spain: { attack: 0.95, defence: 1.1, expected_goals_for: 1.1, expected_goals_against: 1.4 },
    },
  },
  models: [
    { family: "elo_ordlogit", role: "voice", method: "ratings", params: { ratings: { France: 1620, Spain: 1580 }, home_advantage: 60, k_factor: 28 } },
    { family: "dixon_coles", role: "voice", method: "goals", params: { rho: -0.08, xi: 0.001, prior_matches: 8 } },
  ],
} as unknown as MatchAnalysis;

describe("ModelInternals", () => {
  it("explains only engine-carried model internals", () => {
    const html = renderToStaticMarkup(createElement(ModelInternals, { analysis, home: "France", away: "Spain" }));
    expect(html).toContain("France rating");
    expect(html).toContain("1620");
    expect(html).toContain("France attack");
    expect(html).toContain("scores 24% more than an average side");
    expect(html).toContain("ρ low-score correction");
    expect(html).toContain("Only fields carried by this analysis payload are shown");
  });
});
