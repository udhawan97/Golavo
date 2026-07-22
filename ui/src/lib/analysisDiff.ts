import type { MatchAnalysis, Outcome, Probs } from "./contract";

export interface AnalysisGenerationSnapshot {
  indexSha256: string;
  voices: Record<string, Probs>;
}

export interface AnalysisChange {
  family: string;
  outcome: Outcome;
  percentagePoints: number;
}

export function analysisGenerationSnapshot(
  analysis: MatchAnalysis,
  indexSha256: string,
): AnalysisGenerationSnapshot {
  const voices: Record<string, Probs> = {};
  for (const model of analysis.models) {
    if ((model.role === "voice" || model.role === "baseline") && model.probs) {
      voices[model.family] = { ...model.probs };
    }
  }
  return { indexSha256, voices };
}

export function diffAnalysisGenerations(
  previous: AnalysisGenerationSnapshot,
  current: AnalysisGenerationSnapshot,
): AnalysisChange[] {
  if (previous.indexSha256 === current.indexSha256) return [];
  const changes: AnalysisChange[] = [];
  for (const family of Object.keys(current.voices).sort()) {
    const before = previous.voices[family];
    const after = current.voices[family];
    if (!before) continue;
    for (const outcome of ["home", "draw", "away"] as const) {
      const percentagePoints = Math.round((after[outcome] - before[outcome]) * 1000) / 10;
      if (percentagePoints !== 0) changes.push({ family, outcome, percentagePoints });
    }
  }
  return changes.sort(
    (a, b) => Math.abs(b.percentagePoints) - Math.abs(a.percentagePoints)
      || `${a.family}:${a.outcome}`.localeCompare(`${b.family}:${b.outcome}`),
  );
}
