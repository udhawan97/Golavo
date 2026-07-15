import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { createElement } from "react";
import type { ResearchTeamAnalytics } from "../lib/contract";
import { ResearchTeamAnalyticsBody } from "./ResearchTeamAnalytics";

const data: ResearchTeamAnalytics = {
  schema_version: "0.1.0",
  status: "available",
  label: "Historical team research — never a live model input",
  competition_id: "england-premier-league",
  competition_name: "Premier League",
  era: "2017/18",
  team_scope: "team_aggregate_only",
  coverage: { matches: 380, events: 643150, teams: 2 },
  methods: {
    progressive_pass: "x gain >= 20",
    chain_proxy: "same-team event run",
    research_xt: "12x8 transition grid",
  },
  teams: [
    { team_id: 1, team: "Alpha", matches: 38, passes_attempted: 100, passes_completed: 80,
      pass_completion_pct: 80, progressive_passes_per_match: 10, shots_per_match: 5,
      goals_per_match: 1.2, chain_proxy_events: 100, chain_proxy_count: 50,
      progressive_chains_per_match: 8, research_xt_created_per_match: 1.234 },
    { team_id: 2, team: "Beta", matches: 38, passes_attempted: 90, passes_completed: 70,
      pass_completion_pct: 77.8, progressive_passes_per_match: 9, shots_per_match: 4,
      goals_per_match: 1, chain_proxy_events: 90, chain_proxy_count: 45,
      progressive_chains_per_match: 7, research_xt_created_per_match: 1.1 },
  ],
  provenance: {
    source_id: "pappalardo-wyscout-events",
    license: "CC-BY-4.0",
    attribution: "Pappalardo et al.",
    modifications: "Team aggregates only.",
  },
};

describe("ResearchTeamAnalytics", () => {
  it("is collapsed, era-specific, and explicit about model isolation", () => {
    const html = renderToStaticMarkup(createElement(ResearchTeamAnalyticsBody, { data }));
    expect(html).toContain("2017/18 team event research");
    expect(html).toContain("Historical · not a model input");
    expect(html).toContain("never mixed");
    expect(html).not.toContain("<details open");
  });
});
