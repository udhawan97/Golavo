import { useEffect, useState } from "react";
import type { MatchAnalysis } from "../lib/contract";
import {
  analysisGenerationSnapshot,
  diffAnalysisGenerations,
  type AnalysisChange,
  type AnalysisGenerationSnapshot,
} from "../lib/analysisDiff";

export function VerifiedGenerationDiff({
  matchId,
  analysis,
  indexSha256,
}: {
  matchId: string;
  analysis: MatchAnalysis | null;
  indexSha256: string | null;
}) {
  const [comparison, setComparison] = useState<{ previous: string; changes: AnalysisChange[] } | null>(null);
  useEffect(() => {
    setComparison(null);
    if (!analysis || !indexSha256) return;
    const key = `golavo:analysis-generation:${matchId}`;
    const current = analysisGenerationSnapshot(analysis, indexSha256);
    try {
      const raw = localStorage.getItem(key);
      const previous = raw ? JSON.parse(raw) as AnalysisGenerationSnapshot : null;
      if (previous && previous.indexSha256 !== current.indexSha256) {
        setComparison({ previous: previous.indexSha256, changes: diffAnalysisGenerations(previous, current) });
      }
      localStorage.setItem(key, JSON.stringify(current));
    } catch {
      // This is a convenience comparison; private-storage failures never block analysis.
    }
  }, [analysis, indexSha256, matchId]);
  if (!comparison || !indexSha256) return null;
  return (
    <aside className="callout callout--info" aria-live="polite">
      <div>
        <div className="callout__title">What changed in the verified generation?</div>
        <p className="small muted">Index {comparison.previous.slice(0, 10)}… → {indexSha256.slice(0, 10)}…</p>
        {comparison.changes.length ? (
          <ul className="small">
            {comparison.changes.slice(0, 6).map((change) => (
              <li key={`${change.family}:${change.outcome}`}>
                {change.family} · {change.outcome}: {change.percentagePoints > 0 ? "+" : ""}{change.percentagePoints.toFixed(1)} points
              </li>
            ))}
          </ul>
        ) : <p className="small">No displayed council probability moved.</p>}
        <p className="small muted">Deterministic comparison of two locally verified index fingerprints; not a seal and not AI.</p>
      </div>
    </aside>
  );
}
