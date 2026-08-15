import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type {
  SeasonFixtureImportance,
  SeasonOutlook,
  SeasonOutlookTeam,
  SeasonRemainingFixture,
} from "../lib/contract";
import {
  clubImportance,
  opponentBands,
  RunIn,
  scenarioRequest,
  SeasonOutlookBody,
  topStake,
} from "./SeasonOutlook";

const BLOCKED: SeasonOutlook = {
  schema_version: "0.2.0",
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
  current_table: [], remaining_fixtures: [], scenario: null,
  iterations: 0, seed: null, voices: [],
  provenance: { source_ids: [], index_sha256: "0".repeat(64) },
};

const RUN_IN_TEAMS: SeasonOutlookTeam[] = [
  ["A", 70], ["B", 60], ["C", 50], ["D", 40],
].map(([team, points]) => ({
  team: team as string,
  title: 0.25,
  top_four: 1,
  relegation: 0.25,
  expected_points: points as number,
  display_percent: { title: 25, top_four: 100, relegation: 25 },
}));

const OK_IMPORTANCE: SeasonFixtureImportance = {
  voice_id: "elo_ordlogit",
  status: "ok",
  score: 0.23,
  coverage: { home_wins: 4200, draws: 2100, away_wins: 3700 },
  clubs: [
    { team: "A", side: "home", score: 0.23, swings: { title: 0.23, top_four: 0.1, relegation: 0 } },
    { team: "B", side: "away", score: 0.11, swings: { title: 0.02, top_four: 0.11, relegation: 0 } },
  ],
};

const ABSTAINED_IMPORTANCE: SeasonFixtureImportance = {
  voice_id: "elo_ordlogit",
  status: "insufficient_coverage",
  score: null,
  coverage: { home_wins: 9950, draws: 50, away_wins: 0 },
  clubs: [
    { team: "C", side: "home", score: null, swings: null },
    { team: "D", side: "away", score: null, swings: null },
  ],
};

const RUN_IN_FIXTURES: SeasonRemainingFixture[] = [
  {
    match_id: "m-1", kickoff_utc: "2027-02-01T15:00:00Z",
    home_team: "A", away_team: "B", importance: OK_IMPORTANCE,
  },
  {
    match_id: "m-2", kickoff_utc: "2027-02-02T15:00:00Z",
    home_team: "C", away_team: "D", importance: ABSTAINED_IMPORTANCE,
  },
];

const WITH_IMPORTANCE: SeasonOutlook = {
  ...BLOCKED,
  status: "available",
  reason_code: null,
  reason: null,
  iterations: 10_000,
  seed: 42,
  current_table: RUN_IN_TEAMS.map((team, index) => ({
    position: index + 1, team: team.team, played: 4, won: 2, drawn: 1, lost: 1,
    goals_for: 6, goals_against: 4, goal_difference: 2, points_adjustment: 0, points: 7,
  })),
  remaining_fixtures: RUN_IN_FIXTURES,
  voices: [
    {
      voice_id: "elo_ordlogit", label: "Ratings voice", role: "voice",
      scoreline_method: "declared method", teams: RUN_IN_TEAMS,
      totals: { title: 1, top_four: 4, relegation: 1 },
    },
  ],
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

  it("shows the run-in with swings, and no badge where the engine abstained", () => {
    const html = renderToStaticMarkup(createElement(RunIn, { outlook: WITH_IMPORTANCE }));
    // Projected points come from the same voice that produced the swings.
    expect(html).toContain("70.0");
    expect(html).toContain("Ratings");
    // A's title chance moves 23 points between winning and losing.
    expect(html).toContain("23pp");
    expect(html).toContain("11pp");
    // The abstained fixture renders its opponents but never a fabricated number.
    expect(html).toContain(">D<");
    expect(html).not.toContain("0pp");
  });

  it("renders no run-in when the payload carries no importance", () => {
    const without: SeasonOutlook = {
      ...WITH_IMPORTANCE,
      remaining_fixtures: WITH_IMPORTANCE.remaining_fixtures.map(({ importance, ...rest }) => {
        void importance;
        return rest;
      }),
    };
    expect(renderToStaticMarkup(createElement(RunIn, { outlook: without }))).toBe("");
  });

  it("bands opponents by projected finish from one voice", () => {
    const bands = opponentBands(RUN_IN_TEAMS);
    expect(bands.get("A")).toBe("tough");
    expect(bands.get("D")).toBe("kind");
    // A team with no projected points cannot be banded rather than guessed at.
    expect(opponentBands([{ ...RUN_IN_TEAMS[0], expected_points: undefined }]).size).toBe(0);
  });

  it("reads the leading stake and abstains with the engine", () => {
    const fixture = WITH_IMPORTANCE.remaining_fixtures[0];
    const club = clubImportance(fixture, "A");
    expect(club && topStake(club)).toBe("title");
    // The abstained fixture reports nothing for either club.
    expect(clubImportance(WITH_IMPORTANCE.remaining_fixtures[1], "C")).toBeNull();
  });

  it("builds a bounded multi-fixture hypothetical request", () => {
    const request = scenarioRequest(
      RUN_IN_FIXTURES,
      [
        { id: 1, fixtureId: "m-1", homeScore: 2, awayScore: 1 },
        { id: 2, fixtureId: "m-2", homeScore: 0, awayScore: 0 },
      ],
    );
    expect(request).toEqual([
      { match_id: "m-1", home_score: 2, away_score: 1 },
      { match_id: "m-2", home_score: 0, away_score: 0 },
    ]);
    for (const invalidScore of [-1, 1.5, 21]) {
      expect(() => scenarioRequest(
        RUN_IN_FIXTURES,
        [{ id: 1, fixtureId: "m-1", homeScore: invalidScore, awayScore: 0 }],
      )).toThrow("whole numbers from 0 to 20");
    }
    expect(() => scenarioRequest(
      RUN_IN_FIXTURES,
      [
        { id: 1, fixtureId: "m-1", homeScore: 1, awayScore: 0 },
        { id: 2, fixtureId: "m-1", homeScore: 0, awayScore: 1 },
      ],
    )).toThrow("only once");
    expect(() => scenarioRequest(RUN_IN_FIXTURES, [])).toThrow("1 to 12");
    const thirteenFixtures = Array.from({ length: 13 }, (_, index) => ({
      match_id: `m-${index}`,
      kickoff_utc: "2026-08-22T14:00:00Z",
      home_team: `Home ${index}`,
      away_team: `Away ${index}`,
    }));
    expect(scenarioRequest(
      thirteenFixtures.slice(0, 12),
      thirteenFixtures.slice(0, 12).map((fixture, index) => ({
        id: index,
        fixtureId: fixture.match_id,
        homeScore: 1,
        awayScore: 0,
      })),
    )).toHaveLength(12);
    expect(() => scenarioRequest(
      thirteenFixtures,
      thirteenFixtures.map((fixture, index) => ({
        id: index,
        fixtureId: fixture.match_id,
        homeScore: 1,
        awayScore: 0,
      })),
    )).toThrow("1 to 12");
  });

  it("pairs verified and conditional probabilities by team name", () => {
    const conditional: SeasonOutlook = {
      ...WITH_IMPORTANCE,
      scenario: {
        hypothetical_only: true,
        persisted: false,
        model_input: false,
        forced_results: [{
          match_id: "m-1",
          home_team: "A",
          away_team: "B",
          home_score: 2,
          away_score: 1,
        }],
      },
      voices: [{
        ...WITH_IMPORTANCE.voices[0],
        teams: [...RUN_IN_TEAMS].reverse().map((team) => (
          team.team === "A"
            ? { ...team, display_percent: { ...team.display_percent, title: 33 } }
            : team
        )),
      }],
    };
    const html = renderToStaticMarkup(createElement(SeasonOutlookBody, {
      outlook: conditional,
      canonical: WITH_IMPORTANCE,
    }));
    expect(html).toContain("Verified");
    expect(html).toContain("Conditional");
    expect(html).toMatch(
      /<th scope="row">A<\/th><td class="num">25\.0%<\/td><td class="num season-comparison__conditional">33\.0%/,
    );
  });
});
