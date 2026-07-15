import { describe, expect, it } from "vitest";
import { doubleChanceMarkets, goalThresholds, totalGoalBands } from "./markets";
import type { ScoreMatrix } from "./contract";

/** A tiny 2×2 grid (max_goals=1) with a small tail, used to check the exact
 *  re-bucketing the Score outlook markets rely on. */
const sm: ScoreMatrix = {
  family: "dixon_coles",
  max_goals: 1,
  grid: [
    [0.30, 0.20],
    [0.25, 0.15],
  ],
  most_likely: { home: 0, away: 0, probability: 0.30 },
  tail: { probability: 0.10, home: 0.04, draw: 0.02, away: 0.04 },
} as unknown as ScoreMatrix;

describe("goalThresholds", () => {
  it("over a line counts every scoreline with more total goals, plus the whole tail", () => {
    const t = goalThresholds(sm).find((x) => x.line === 0.5)!;
    // Over 0.5 = everything except 0-0 (0.30): 0.20 + 0.25 + 0.15 + tail 0.10 = 0.70.
    expect(t.over).toBeCloseTo(0.70, 9);
    expect(t.under).toBeCloseTo(0.30, 9);
    // over + under always partitions the mass to 1.
    expect(t.over + t.under).toBeCloseTo(1, 9);
  });
});

describe("doubleChanceMarkets", () => {
  it("returns the exact pair-sums of engine 1X2 probabilities", () => {
    expect(doubleChanceMarkets({ home: 0.48, draw: 0.27, away: 0.25 })).toEqual({
      home_or_draw: 0.75,
      home_or_away: 0.73,
      draw_or_away: 0.52,
    });
  });
});

describe("totalGoalBands", () => {
  it("bands sum to one with a tail-inclusive top bucket", () => {
    const bands = totalGoalBands(sm);
    const sum = bands.reduce((s, b) => s + b.probability, 0);
    expect(sum).toBeCloseTo(1, 9);
    // 0 goals = 0-0 = 0.30.
    expect(bands.find((b) => b.total === "0")!.probability).toBeCloseTo(0.30, 9);
  });
});
