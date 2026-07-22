import type { MatchAnalysis, MatchDetailResponse } from "./contract";
import { analysisHistorySupport } from "./analysisPresentation";

export type ReadinessState = "ready" | "limited" | "boundary";
export interface ReadinessItem { label: string; state: ReadinessState; detail: string }

export function forecastReadinessItems(
  detail: MatchDetailResponse,
  analysis: MatchAnalysis | null,
  indexSha256: string | null,
): ReadinessItem[] {
  const { match, seal_eligibility: seal } = detail;
  const history = analysis ? analysisHistorySupport(analysis) : null;
  return [
    {
      label: "Verified generation",
      state: indexSha256 ? "ready" : "limited",
      detail: indexSha256 ? `Index ${indexSha256.slice(0, 12)}…` : "Generation proof unavailable",
    },
    {
      label: "Fixture timing",
      state: match.kickoff_precision === "exact" ? "ready" : "limited",
      detail: match.kickoff_precision === "exact" ? "Exact UTC kickoff" : "Day precision only",
    },
    {
      label: "History support",
      state: history === "strong" ? "ready" : history ? "limited" : "boundary",
      detail: history ? `${history[0].toUpperCase()}${history.slice(1)} qualifying history` : "Analysis unavailable",
    },
    {
      label: "Seal path",
      state: seal?.eligible ? "ready" : "boundary",
      detail: seal?.eligible ? "Eligible for an immutable pre-kickoff seal" : seal?.detail ?? "Read-only analysis",
    },
    {
      label: "Known evidence boundary",
      state: "boundary",
      detail: "No verified lineups, injuries, or observed xG are claimed",
    },
  ];
}
