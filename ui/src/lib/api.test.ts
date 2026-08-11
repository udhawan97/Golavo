import { describe, expect, it } from "vitest";
import type { SeasonFixtureImportance, SeasonRemainingFixture } from "./contract";
import {
  importanceViolation,
  narrativeJobWasLost,
  refreshMatchWeather,
  WeatherRefreshError,
} from "./api";

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

describe("weather refresh consent", () => {
  it("never fetches without a connected backend (the click is the consent)", async () => {
    // In the mock-data build there is no engine, so no network call is attempted.
    await expect(refreshMatchWeather("m_x")).rejects.toBeInstanceOf(WeatherRefreshError);
    await expect(refreshMatchWeather("m_x")).rejects.toMatchObject({ reasonCode: "preview_only" });
  });
});
