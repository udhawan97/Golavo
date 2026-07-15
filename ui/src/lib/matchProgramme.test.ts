import { describe, expect, it } from "vitest";
import type { FormEntry } from "./contract";
import { formStreakSentence, goalDifferenceTrend, signedGoalDifference } from "./matchProgramme";

const entry = (
  result: FormEntry["result"],
  gf: number,
  ga: number,
  isHome: boolean,
  neutral = false,
): FormEntry => ({ result, gf, ga, is_home: isHome, neutral, opponent: "Opponent", date: "2030-01-01" });

describe("match programme form helpers", () => {
  it("describes the current venue-qualified streak from oldest-first form", () => {
    expect(formStreakSentence([
      entry("L", 0, 1, true),
      entry("W", 2, 0, false),
      entry("W", 1, 0, false),
      entry("W", 3, 1, false),
    ])).toBe("Three away wins in a row.");
  });

  it("drops the venue when the current streak spans roles", () => {
    expect(formStreakSentence([
      entry("D", 1, 1, true),
      entry("D", 0, 0, false),
    ])).toBe("Two draws in a row.");
  });

  it("returns no sentence for a single result", () => {
    expect(formStreakSentence([entry("W", 1, 0, true)])).toBeNull();
  });

  it("keeps exact last-five goal differences and formats their signs", () => {
    const trend = goalDifferenceTrend([
      entry("W", 3, 1, true),
      entry("D", 1, 1, false),
      entry("L", 0, 2, false),
    ]);
    expect(trend).toEqual([2, 0, -2]);
    expect(trend.map(signedGoalDifference)).toEqual(["+2", "0", "−2"]);
  });
});
