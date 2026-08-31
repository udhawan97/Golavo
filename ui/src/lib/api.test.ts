import { describe, expect, it, vi } from "vitest";
import type {
  CompetitionAnalytics,
  SeasonFixtureImportance,
  SeasonForcedResult,
  SeasonOutlook,
  SeasonRemainingFixture,
} from "./contract";
import {
  assertSeasonScenarioResponse,
  assertCompetitionAnalytics,
  clearApiCache,
  fetchCompetitionAnalytics,
  getJson,
  importanceViolation,
  narrativeJobWasLost,
  refreshMatchWeather,
  WeatherRefreshError,
} from "./api";

function scenarioResponse(): SeasonOutlook {
  const voice = (voiceId: "elo_ordlogit" | "dixon_coles" | "equal-chance-baseline") => ({
    voice_id: voiceId,
    label: voiceId,
    role: voiceId === "equal-chance-baseline" ? "baseline" as const : "voice" as const,
    scoreline_method: "declared method",
    teams: [{
      team: "A",
      title: 1,
      top_four: 1,
      relegation: 0,
      display_percent: { title: 100, top_four: 100, relegation: 0 }, history_coverage: { matches: 40, model_floor: 10, status: "ok" as const },
    }],
    totals: { title: 1, top_four: 1, relegation: 0 },
  });
  return {
    schema_version: "0.3.0",
    status: "available",
    label: "Season outlook — not a seal.",
    competition_id: "test-league",
    competition_name: "Test League",
    season: "2026-27",
    as_of_utc: "2026-08-20T08:00:00Z",
    simulation_rule: "season-mc-2026.07.1",
    ledger_status: "never_persisted_or_scored_as_a_seal",
    reason_code: null,
    reason: null,
    standings_rule_id: "test-2026.1",
    fixture_certificate: {
      expected_teams: 2,
      observed_teams: 2,
      teams: ["A", "B"],
      expected_matches: 2,
      observed_matches: 2,
      unique_ordered_pairs: 2,
      duplicate_ordered_pairs: 0,
      self_fixtures: 0,
      incomplete_fixtures: 1,
      past_result_gaps: 0,
      future_completed_results: 0,
      complete_fixture_list: true,
    },
    current_table: [],
    remaining_fixtures: [{
      match_id: "m-1",
      kickoff_utc: "2027-02-01T15:00:00Z",
      home_team: "A",
      away_team: "B",
    }],
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
    iterations: 10_000,
    seed: 42,
    voices: [voice("elo_ordlogit"), voice("dixon_coles"), voice("equal-chance-baseline")],
    provenance: { source_ids: ["test-source"], index_sha256: "0".repeat(64) },
  };
}

const REQUEST: SeasonForcedResult[] = [{ match_id: "m-1", home_score: 2, away_score: 1 }];
const EXPECTED_FIXTURES: SeasonRemainingFixture[] = [{
  match_id: "m-1",
  kickoff_utc: "2027-02-01T15:00:00Z",
  home_team: "A",
  away_team: "B",
}];
const EXPECTATION = {
  competitionId: "test-league",
  forcedResults: REQUEST,
  fixtures: EXPECTED_FIXTURES,
  season: "2026-27",
  asOfUtc: "2026-08-20T08:00:00Z",
  indexSha256: "0".repeat(64),
};

function fixture(importance?: SeasonFixtureImportance): SeasonRemainingFixture {
  return {
    match_id: "m-1",
    kickoff_utc: "2027-02-01T15:00:00Z",
    home_team: "A",
    away_team: "B",
    importance,
  };
}

const SOUND: SeasonFixtureImportance = {
  voice_id: "elo_ordlogit",
  status: "ok",
  score: 0.4,
  coverage: { home_wins: 4000, draws: 2000, away_wins: 4000 },
  clubs: [
    { team: "A", side: "home", score: 0.4, swings: { title: 0.4, top_four: 0.1, relegation: 0 } },
    { team: "B", side: "away", score: 0.2, swings: { title: 0.2, top_four: 0.1, relegation: 0 } },
  ],
};

describe("narrative job polling", () => {
  it("tolerates a brief hand-off race before the first successful poll", () => {
    expect(narrativeJobWasLost(false, 1)).toBe(false);
    expect(narrativeJobWasLost(false, 2)).toBe(false);
    expect(narrativeJobWasLost(false, 3)).toBe(true);
  });

  it("stops immediately when a previously visible job disappears", () => {
    expect(narrativeJobWasLost(true, 1)).toBe(true);
  });
});

describe("GET cache invalidation", () => {
  it("keeps a pre-clear response out of the new epoch and preserves the newer in-flight request", async () => {
    const oldValue = { generation: "old" };
    const newValue = { generation: "new" };
    let resolveOld!: (value: typeof oldValue) => void;
    let resolveNew!: (value: typeof newValue) => void;
    const bodies = [
      new Promise<typeof oldValue>((resolve) => { resolveOld = resolve; }),
      new Promise<typeof newValue>((resolve) => { resolveNew = resolve; }),
    ];
    const fetchMock = vi.fn(() => Promise.resolve({
      ok: true,
      json: () => bodies.shift()!,
    } as Response));

    vi.stubGlobal("fetch", fetchMock);
    try {
      clearApiCache();
      const oldRequest = getJson("/cache-epoch-probe");
      await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

      clearApiCache();
      const newRequest = getJson("/cache-epoch-probe");
      await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));

      resolveOld(oldValue);
      await expect(oldRequest).resolves.toEqual(oldValue);

      const coalescedAfterOldSettles = getJson("/cache-epoch-probe");
      expect(fetchMock).toHaveBeenCalledTimes(2);
      resolveNew(newValue);

      await expect(newRequest).resolves.toEqual(newValue);
      await expect(coalescedAfterOldSettles).resolves.toEqual(newValue);
      await expect(getJson("/cache-epoch-probe")).resolves.toEqual(newValue);
      expect(fetchMock).toHaveBeenCalledTimes(2);
    } finally {
      vi.unstubAllGlobals();
      clearApiCache();
    }
  });
});

describe("current-season analytics contract", () => {
  it("validates and returns the available Premier League pulse in mock mode", async () => {
    const value = await fetchCompetitionAnalytics("england-premier-league");

    expect(value.current_season).toMatchObject({
      status: "available",
      season: "2026-27",
      observed_matches: 380,
      matches_played: 10,
      matches_remaining: 361,
      past_result_gaps: 9,
      source_ids: ["golavo-synthetic-contract-fixtures"],
    });
    expect(value.current_season.teams.map((team) => team.team)).toEqual([
      "Example Athletic",
      "Sample City",
    ]);
  });

  it("rejects invalid statuses, counts, rates, partitions, teams and provenance", async () => {
    const valid = await fetchCompetitionAnalytics("england-premier-league");
    const mutations: Array<(value: CompetitionAnalytics) => void> = [
      (value) => { value.current_season.status = "stale" as never; },
      (value) => { value.current_season.matches_remaining = -1; },
      (value) => { value.current_season.home_win_rate = 1.1; },
      (value) => { value.current_season.observed_matches = 379; },
      (value) => { value.current_season.home_wins = 8; },
      (value) => { value.current_season.teams[0].played = -1; },
      (value) => { value.current_season.teams[0].points_per_game = 2.5; },
      (value) => { value.current_season.source_ids = []; },
      (value) => { value.current_season.source_ids = ["test", "test"]; },
    ];

    for (const mutate of mutations) {
      const invalid = structuredClone(valid);
      mutate(invalid);
      expect(() => assertCompetitionAnalytics(invalid, "invalid pulse")).toThrow();
    }
  });
});

describe("season importance contract", () => {
  it("accepts a sound block and a payload with no importance at all", () => {
    expect(importanceViolation([fixture(SOUND), fixture()])).toBeNull();
  });

  it("rejects a swing the engine said it could not read", () => {
    const faked: SeasonFixtureImportance = {
      ...SOUND,
      status: "insufficient_coverage",
      score: 0.4,
    };
    expect(importanceViolation([fixture(faked)])).toContain("abstained");
  });

  it("rejects an out-of-range swing and a half-named fixture", () => {
    expect(importanceViolation([fixture({ ...SOUND, score: 1.4 })])).toContain("invalid swing");
    expect(importanceViolation([fixture({ ...SOUND, clubs: [SOUND.clubs[0]] })])).toContain(
      "both clubs",
    );
  });
});

describe("season scenario response contract", () => {
  it("accepts an available response that exactly matches the request", () => {
    expect(assertSeasonScenarioResponse(
      scenarioResponse(),
      EXPECTATION,
    ).scenario?.forced_results).toHaveLength(1);
  });

  it("rejects a canonical response and request identity mismatches", () => {
    const canonical = scenarioResponse();
    canonical.scenario = null;
    expect(() => assertSeasonScenarioResponse(canonical, EXPECTATION))
      .toThrow(/available conditional scenario/);

    const competition = scenarioResponse();
    competition.competition_id = "other-league";
    expect(() => assertSeasonScenarioResponse(competition, EXPECTATION))
      .toThrow(/response identity/);

    const season = scenarioResponse();
    season.season = "2027-28";
    expect(() => assertSeasonScenarioResponse(season, EXPECTATION))
      .toThrow(/response identity/);

    const cutoff = scenarioResponse();
    cutoff.as_of_utc = "2026-08-21T08:00:00Z";
    expect(() => assertSeasonScenarioResponse(cutoff, EXPECTATION))
      .toThrow(/response identity/);

    const generation = scenarioResponse();
    generation.provenance.index_sha256 = "1".repeat(64);
    expect(() => assertSeasonScenarioResponse(generation, EXPECTATION))
      .toThrow(/response identity/);
  });

  it("rejects response results that do not exactly match the submitted set", () => {
    const score = scenarioResponse();
    score.scenario!.forced_results[0].home_score = 3;
    expect(() => assertSeasonScenarioResponse(score, EXPECTATION))
      .toThrow(/submitted forced results/);

    const match = scenarioResponse();
    match.scenario!.forced_results[0].match_id = "m-2";
    expect(() => assertSeasonScenarioResponse(match, EXPECTATION))
      .toThrow(/invalid forced result|submitted forced results/);

    const selfConsistentWrongTeams = scenarioResponse();
    selfConsistentWrongTeams.remaining_fixtures[0].home_team = "Stale A";
    selfConsistentWrongTeams.scenario!.forced_results[0].home_team = "Stale A";
    expect(() => assertSeasonScenarioResponse(
      selfConsistentWrongTeams,
      EXPECTATION,
    )).toThrow(/submitted forced results/);
  });

  it.each([
    ["empty results", []],
    ["duplicate ids", [
      scenarioResponse().scenario!.forced_results[0],
      scenarioResponse().scenario!.forced_results[0],
    ]],
    ["too many results", Array.from({ length: 13 }, (_, index) => ({
      ...scenarioResponse().scenario!.forced_results[0],
      match_id: `m-${index + 1}`,
    }))],
    ["fractional score", [{
      ...scenarioResponse().scenario!.forced_results[0],
      home_score: 1.5,
    }]],
    ["score over 20", [{
      ...scenarioResponse().scenario!.forced_results[0],
      away_score: 21,
    }]],
    ["non-string team", [{
      ...scenarioResponse().scenario!.forced_results[0],
      home_team: {} as unknown as string,
    }]],
  ])("rejects %s", (_name, forcedResults) => {
    const response = scenarioResponse();
    response.scenario!.forced_results = forcedResults;
    expect(() => assertSeasonScenarioResponse(response, EXPECTATION))
      .toThrow();
  });
});

describe("weather refresh consent", () => {
  it("never fetches without a connected backend (the click is the consent)", async () => {
    // In the mock-data build there is no engine, so no network call is attempted.
    await expect(refreshMatchWeather("m_x")).rejects.toBeInstanceOf(WeatherRefreshError);
    await expect(refreshMatchWeather("m_x")).rejects.toMatchObject({ reasonCode: "preview_only" });
  });
});
