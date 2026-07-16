import type { HistorySupportLevel, MatchAnalysis, Uncertainty } from "./contract";

/** Compatibility mapping for old cached/sample analyses. The legacy value was
 * derived only from match counts, so the honest presentation is history support. */
export function legacyHistorySupport(level: Uncertainty): HistorySupportLevel {
  return level === "high" ? "limited" : level === "medium" ? "moderate" : "strong";
}

export function analysisHistorySupport(analysis: MatchAnalysis): HistorySupportLevel {
  return analysis.explanation?.history_support.level ?? legacyHistorySupport(analysis.uncertainty);
}
