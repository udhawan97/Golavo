import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { SeasonOutlook } from "../lib/contract";
import { SeasonOutlookBody } from "./SeasonOutlook";

const BLOCKED: SeasonOutlook = {
  schema_version: "0.1.0",
  status: "blocked",
  label: "Season outlook — not a seal.",
  competition_id: "england-premier-league",
  competition_name: "English Premier League",
  season: "2026-27",
  as_of_utc: "2026-07-15T08:00:00Z",
  simulation_rule: "season-mc-2026.07.1",
  ledger_status: "never_persisted_or_scored_as_a_seal",
  reason_code: "fixtures_not_published",
  reason: "No 2026–27 fixtures are present in Golavo's pinned lawful source.",
  standings_rule_id: "england-2024.1",
  fixture_certificate: {
    expected_teams: 20, observed_teams: 0, teams: [], expected_matches: 380,
    observed_matches: 0, unique_ordered_pairs: 0, duplicate_ordered_pairs: 0,
    self_fixtures: 0, incomplete_fixtures: 0, past_result_gaps: 0,
    future_completed_results: 0, complete_fixture_list: false,
  },
  current_table: [], iterations: 0, seed: null, voices: [],
  provenance: { source_ids: [], index_sha256: "0".repeat(64) },
};

describe("SeasonOutlookBody", () => {
  it("shows the missing-fixture gate without fabricated probabilities", () => {
    const html = renderToStaticMarkup(createElement(SeasonOutlookBody, { outlook: BLOCKED }));
    expect(html).toContain("Waiting for the complete fixture list");
    expect(html).toContain("No 2026–27 fixtures");
    expect(html).not.toContain("0.0%");
  });

  it("keeps available model voices separate", () => {
    const teams = ["A", "B", "C", "D"].map((team) => ({
      team, title: 0.25, top_four: 1, relegation: 0.25,
      display_percent: { title: 25, top_four: 100, relegation: 25 },
    }));
    const available: SeasonOutlook = {
      ...BLOCKED, status: "available", reason_code: null, reason: null,
      iterations: 10_000, seed: 42,
      voices: (["elo_ordlogit", "dixon_coles", "equal-chance-baseline"] as const).map((id) => ({
        voice_id: id, label: id, role: id === "equal-chance-baseline" ? "baseline" : "voice",
        scoreline_method: "declared method", teams,
        totals: { title: 1, top_four: 4, relegation: 1 },
      })),
    };
    const html = renderToStaticMarkup(createElement(SeasonOutlookBody, { outlook: available }));
    expect(html).toContain("Ratings");
    expect(html).toContain("Goals");
    expect(html).toContain("Baseline");
    expect(html).toContain("10,000 seeded runs");
    expect(html).toContain("25.0%");
  });
});
