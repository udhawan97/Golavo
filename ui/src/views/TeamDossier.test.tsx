// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fetchClubRatings, fetchCompetitionAnalytics, fetchSeasonOutlook } from "../lib/api";
import type { CompetitionAnalytics, RatingsTable, SeasonOutlook } from "../lib/contract";
import { TeamDossier } from "./TeamDossier";

vi.mock("../lib/api", () => ({
  fetchClubRatings: vi.fn(),
  fetchCompetitionAnalytics: vi.fn(),
  fetchSeasonOutlook: vi.fn(),
}));
vi.mock("../components/FollowButton", () => ({
  FollowButton: ({ matchId }: { matchId: string }) => <button type="button">Follow {matchId}</button>,
}));

const OUTLOOK = {
  schema_version: "0.3.0",
  status: "available",
  competition_id: "england-premier-league",
  competition_name: "Premier League",
  season: "2026-27",
  as_of_utc: "2026-08-29T00:00:00Z",
  simulation_rule: "season-mc-2026.07.1",
  ledger_status: "never_persisted_or_scored_as_a_seal",
  reason_code: null,
  reason: null,
  standings_rule_id: "epl-2026-27",
  fixture_certificate: {
    expected_teams: 20, observed_teams: 20, teams: ["Exact Club", "Rival"],
    expected_matches: 380, observed_matches: 380, unique_ordered_pairs: 380,
    duplicate_ordered_pairs: 0, self_fixtures: 0, incomplete_fixtures: 0,
    past_result_gaps: 0, future_completed_results: 0, complete_fixture_list: true,
  },
  current_table: [{
    position: 2, team: "Exact Club", played: 30, won: 18, drawn: 6, lost: 6,
    goals_for: 55, goals_against: 30, goal_difference: 25, points_adjustment: 0, points: 60,
  }],
  voices: [{
    voice_id: "elo_ordlogit", label: "Ratings voice", role: "voice", scoreline_method: "outcome",
    teams: [{
      team: "Exact Club", title: 0.2, top_four: 0.8, relegation: 0,
      expected_points: 74.2, display_percent: { title: 20, top_four: 80, relegation: 0 },
      history_coverage: { matches: 100, model_floor: 30, status: "ok" },
    }], totals: { title: 1, top_four: 4, relegation: 3 },
  }, {
    voice_id: "dixon_coles", label: "Goal voice", role: "voice", scoreline_method: "scoreline",
    teams: [{
      team: "Exact Club", title: 0.16, top_four: 0.74, relegation: 0.01,
      expected_points: 72.8, display_percent: { title: 16, top_four: 74, relegation: 1 },
      history_coverage: { matches: 100, model_floor: 30, status: "ok" },
    }], totals: { title: 1, top_four: 4, relegation: 3 },
  }, {
    voice_id: "equal_chance", label: "Equal chance baseline", role: "baseline", scoreline_method: "outcome",
    teams: [{
      team: "Exact Club", title: 0.05, top_four: 0.2, relegation: 0.15,
      expected_points: 55, display_percent: { title: 5, top_four: 20, relegation: 15 },
      history_coverage: { matches: 100, model_floor: 0, status: "ok" },
    }], totals: { title: 1, top_four: 4, relegation: 3 },
  }],
  remaining_fixtures: [{
    match_id: "m_run_in", kickoff_utc: "2026-09-01T18:30:00Z",
    home_team: "Exact Club", away_team: "Rival",
    importance: {
      voice_id: "elo_ordlogit", status: "ok", score: 0.05,
      coverage: { home_wins: 100, draws: 100, away_wins: 100 },
      clubs: [{
        team: "Exact Club", side: "home", score: 0.05,
        swings: { title: 0.05, top_four: 0.02, relegation: 0 },
      }, {
        team: "Rival", side: "away", score: 0.03,
        swings: { title: 0.01, top_four: 0.03, relegation: 0 },
      }],
    },
  }],
  scenario: null,
  iterations: 10_000,
  seed: 42,
  provenance: { source_ids: ["openfootball-england"], index_sha256: "a".repeat(64) },
} as SeasonOutlook;

const ANALYTICS = {
  schema_version: "0.2.0",
  competition_id: "england-premier-league",
  competition_name: "Premier League",
  as_of_utc: "2026-08-29T00:00:00Z",
  scope: { team_category: "club", strength_comparison: "this_competition_only", model_input: false },
  provenance: { source_ids: ["openfootball-england"], index_sha256: "a".repeat(64) },
  current_season: {
    status: "available", reason: null, season: "2026-27", data_through_utc: "2026-08-28T20:00:00Z",
    fixture_list_complete: true, teams: [{
      team: "Exact Club", played: 3, won: 2, drawn: 1, lost: 0, goals_for: 7,
      goals_against: 2, clean_sheets: 2, both_teams_scored: 1,
      recent_form: ["W", "W", "D"], points_per_game: 2.33,
      goals_for_per_match: 2.33, goals_against_per_match: 0.67,
    }],
  },
  strength_trends: {
    status: "available", reason: null, method: "time-decayed-poisson-rates-v1",
    minimum_matches: 8, data_through_utc: "2026-08-28T20:00:00Z", comparison_scope: "this_competition_only",
    teams: [{
      team: "Exact Club",
      current: { cutoff_utc: "2026-08-28T20:00:00Z", sample_matches: 30, overall_index: 118.4, attack_index: 121.2, defence_index: 115.6 },
      trend: [],
    }],
  },
  rest_congestion: {
    status: "available", reason: null, method: "indexed-match-counts-v1",
    coverage_note: "Indexed matches only.", teams: [{
      team: "Exact Club", last_indexed_match_utc: "2026-08-28T20:00:00Z",
      rest_days: 4, matches_last_7_days: 1, matches_last_14_days: 3,
      matches_last_28_days: 5, congestion: "elevated",
    }],
  },
  schedule_difficulty: {
    status: "available", reason: null, required_capability: null,
    method: "mean-remaining-opponent-elo-v1", season: "2026-27", rating_scope: "england-premier-league",
    teams: [{
      rank: 4, team: "Exact Club", own_rating: 1612, matches_remaining: 8,
      home_remaining: 4, away_remaining: 4, mean_opponent_rating: 1518.6,
    }],
  },
} as CompetitionAnalytics;

const RATINGS = {
  schema_version: "0.1.0",
  method: "elo-goal-weighted-v1",
  label: "Golavo Ratings",
  as_of_utc: "2026-08-29T00:00:00Z",
  scope: "england-premier-league",
  matches_counted: 1_000,
  data_through_utc: "2026-08-28T20:00:00Z",
  provenance: { index_sha256: "a".repeat(64) },
  teams: [{
    rank: 3, team: "Exact Club", rating: 1612, matches: 120,
    last_match_date: "2026-08-28", history: [],
  }],
} as RatingsTable;

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  vi.mocked(fetchSeasonOutlook).mockResolvedValue(structuredClone(OUTLOOK));
  vi.mocked(fetchCompetitionAnalytics).mockResolvedValue(structuredClone(ANALYTICS));
  vi.mocked(fetchClubRatings).mockResolvedValue(structuredClone(RATINGS));
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
  vi.clearAllMocks();
});

describe("TeamDossier", () => {
  it("keeps observed record, model voices, and evidence context in separate layers", async () => {
    await act(async () => root.render(
      <TeamDossier competitionId="england-premier-league" team="Exact Club" />,
    ));

    expect(container.querySelector("h1")?.textContent).toBe("Exact Club");
    expect(container.textContent).toContain("2nd · 60 points");
    expect(container.textContent).toContain("W,W,D");
    expect(container.textContent).toContain("Ratings voice");
    expect(container.textContent).toContain("Projected points74.2");
    expect(container.textContent).toContain("Goal voice");
    expect(container.textContent).toContain("Projected points72.8");
    expect(container.textContent).not.toContain("Equal chance baseline");
    expect(container.textContent).toContain("Competition rank3rd");
    expect(container.textContent).toContain("Overall strength118.4");
    expect(container.textContent).toContain("4 days rest");
    expect(container.textContent).toContain("5pp title swing · Ratings voice");
    expect(container.textContent).toContain("Pick in Match Cockpit");
    expect(container.textContent).toContain("Follow m_run_in");
    expect(container.textContent).toContain("Analytics sources: openfootball-england");
    expect(container.textContent).toContain("Table and projection sources: openfootball-england");
    expect(container.querySelectorAll(".team-dossier__layer")).toHaveLength(3);
    expect(fetchSeasonOutlook).toHaveBeenCalledWith("england-premier-league");
    expect(fetchCompetitionAnalytics).toHaveBeenCalledWith(
      "england-premier-league",
      OUTLOOK.as_of_utc,
    );
    expect(fetchClubRatings).toHaveBeenCalledWith("england-premier-league", {
      asOfUtc: OUTLOOK.as_of_utc,
      indexSha256: OUTLOOK.provenance.index_sha256,
    });
  });

  it("fails closed when the exact team is absent from the active current-season table", async () => {
    vi.mocked(fetchSeasonOutlook).mockResolvedValue({
      ...structuredClone(OUTLOOK),
      current_table: [{ ...OUTLOOK.current_table[0], team: "Different Club" }],
    });

    await act(async () => root.render(
      <TeamDossier competitionId="england-premier-league" team="Exact Club" />,
    ));

    expect(container.textContent).toContain("Exact team identity not present");
    expect(container.textContent).toContain("will not guess through a rename, promotion, or relegation");
    expect(container.textContent).not.toContain("Projected points");
  });

  it("rejects a hypothetical scenario from the canonical dossier route", async () => {
    vi.mocked(fetchSeasonOutlook).mockResolvedValue({
      ...structuredClone(OUTLOOK),
      scenario: {
        hypothetical_only: true,
        persisted: false,
        model_input: false,
        forced_results: [{
          match_id: "m_run_in",
          home_team: "Exact Club",
          away_team: "Rival",
          home_score: 2,
          away_score: 0,
        }],
      },
    });

    await act(async () => root.render(
      <TeamDossier competitionId="england-premier-league" team="Exact Club" />,
    ));

    expect(container.textContent).toContain("Canonical season outlook required");
    expect(container.textContent).not.toContain("Projected points");
  });

  it("keeps the certified record and model voices when analytics context fails", async () => {
    vi.mocked(fetchCompetitionAnalytics).mockRejectedValue(new Error("analytics offline"));

    await act(async () => root.render(
      <TeamDossier competitionId="england-premier-league" team="Exact Club" />,
    ));

    expect(container.querySelector("h1")?.textContent).toBe("Exact Club");
    expect(container.textContent).toContain("2nd · 60 points");
    expect(container.textContent).toContain("Ratings voice");
    expect(container.textContent).toContain("Competition analytics are unavailable");
    expect(container.textContent).toContain("Competition rank3rd");
    expect(container.querySelectorAll(".team-dossier__layer")).toHaveLength(3);
  });

  it("keeps the certified record and analytics when ratings context fails", async () => {
    vi.mocked(fetchClubRatings).mockRejectedValue(new Error("ratings offline"));

    await act(async () => root.render(
      <TeamDossier competitionId="england-premier-league" team="Exact Club" />,
    ));

    expect(container.textContent).toContain("2nd · 60 points");
    expect(container.textContent).toContain("Overall strength118.4");
    expect(container.textContent).toContain("Golavo Ratings are unavailable");
  });

  it("withholds optional envelopes whose snapshot identity does not match the outlook", async () => {
    vi.mocked(fetchCompetitionAnalytics).mockResolvedValue({
      ...structuredClone(ANALYTICS),
      provenance: { ...ANALYTICS.provenance, index_sha256: "b".repeat(64) },
    });
    vi.mocked(fetchClubRatings).mockResolvedValue({
      ...structuredClone(RATINGS),
      scope: "different-competition",
    });

    await act(async () => root.render(
      <TeamDossier competitionId="england-premier-league" team="Exact Club" />,
    ));

    expect(container.textContent).toContain("2nd · 60 points");
    expect(container.textContent).toContain("Ratings voice");
    expect(container.textContent).toContain("Ratings were withheld");
    expect(container.textContent).toContain("Competition analytics were withheld");
    expect(container.textContent).not.toContain("Competition rank3rd");
    expect(container.textContent).not.toContain("Overall strength118.4");
  });

  it("withholds all projections when one model voice lacks the exact team", async () => {
    const incomplete = structuredClone(OUTLOOK);
    const goalVoice = incomplete.voices.find((voice) => voice.voice_id === "dixon_coles");
    if (goalVoice) goalVoice.teams = [];
    vi.mocked(fetchSeasonOutlook).mockResolvedValue(incomplete);

    await act(async () => root.render(
      <TeamDossier competitionId="england-premier-league" team="Exact Club" />,
    ));

    expect(container.textContent).toContain("Model projections are withheld");
    expect(container.textContent).not.toContain("Projected points74.2");
    expect(container.textContent).not.toContain("Projected points72.8");
  });

});
