/**
 * Derived markets — exact re-buckets of a sealed forecast's stored distribution.
 *
 * These are pure marginals of the `score_matrix` the artifact already carries (the
 * same grid the heatmap renders), so they can never diverge from the sealed
 * numbers — this is presentation of sealed values, not a new computation. Only the
 * exactly-recoverable set is produced: double chance (from the sealed 1X2), and,
 * when a goal model sealed a grid, total-goal bands and thresholds below the tail.
 * BTTS / clean sheets / team totals are intentionally absent — the tail is
 * decomposed by outcome only, so those are not exactly recoverable here.
 *
 * Mirrors core/golavo_core/score_matrix.py (double_chance / total_goals_bands /
 * total_goals_over_under); both sum the same stored grid, so they agree exactly.
 */
import type { ForecastBlock, ScoreMatrix } from "./contract";

export interface DoubleChance {
  home_or_draw: number;
  home_or_away: number;
  draw_or_away: number;
}

export interface GoalBand {
  /** "0".."N", then "(N+1)+" for the tail-inclusive bucket. */
  total: string;
  probability: number;
}

export interface GoalThreshold {
  line: number;
  over: number;
  under: number;
}

export interface DerivedMarkets {
  doubleChance: DoubleChance | null;
  bands: GoalBand[] | null;
  thresholds: GoalThreshold[] | null;
}

// Common analysis lines; all below the display cap (max_goals is 7) so the entire
// tail sits on the "more than" side and each threshold is an exact partition.
const LINES = [0.5, 1.5, 2.5, 3.5, 4.5];

function round(value: number, dp: number): number {
  const factor = 10 ** dp;
  return Math.round(value * factor) / factor;
}

export function deriveMarkets(forecast: ForecastBlock): DerivedMarkets {
  const probs = forecast.probs;
  const doubleChance = probs
    ? {
        home_or_draw: round(probs.home + probs.draw, 6),
        home_or_away: round(probs.home + probs.away, 6),
        draw_or_away: round(probs.draw + probs.away, 6),
      }
    : null;
  const sm = forecast.score_matrix ?? null;
  return {
    doubleChance,
    bands: sm ? totalGoalBands(sm) : null,
    thresholds: sm ? goalThresholds(sm) : null,
  };
}

/** Exact P(total goals == t) for t in 0..N, plus a tail-inclusive "(N+1)+" bucket
 *  (exact because every tail cell has at least N+1 total goals). */
export function totalGoalBands(sm: ScoreMatrix): GoalBand[] {
  const n = sm.max_goals;
  const band = new Array<number>(n + 1).fill(0);
  let over = sm.tail.probability;
  for (let i = 0; i <= n; i++) {
    for (let j = 0; j <= n; j++) {
      const value = sm.grid[i][j];
      if (i + j <= n) band[i + j] += value;
      else over += value;
    }
  }
  const bands: GoalBand[] = band.map((p, t) => ({ total: String(t), probability: round(p, 9) }));
  bands.push({ total: `${n + 1}+`, probability: round(over, 9) });
  return bands;
}

/** Exact P(total > line) / P(total <= line) for each line below the tail. */
export function goalThresholds(sm: ScoreMatrix): GoalThreshold[] {
  const n = sm.max_goals;
  return LINES.filter((line) => line < n + 1).map((line) => {
    let over = sm.tail.probability; // every tail total exceeds the line
    let under = 0;
    for (let i = 0; i <= n; i++) {
      for (let j = 0; j <= n; j++) {
        const value = sm.grid[i][j];
        if (i + j > line) over += value;
        else under += value;
      }
    }
    return { line, over: round(over, 9), under: round(under, 9) };
  });
}
