/**
 * ScoreOutlook — the goal model's exact-score picture for the fixture.
 *
 * The most-likely score, expected goals per side, and confidence (StatTiles),
 * with the full exact-score grid in a drawer. Every number comes straight from
 * the goal voice's coherent matrix — nothing is derived here. Extracted from the
 * council so the cockpit reads: council verdict → style → score.
 */
import type { MatchAnalysis } from "../lib/contract";
import { pct } from "../lib/format";
import { StatTile, UncertaintyTag } from "./primitives";
import { ScoreMatrixHeatmap } from "./ScoreMatrixHeatmap";

export function ScoreOutlook({
  analysis,
  home,
  away,
}: {
  analysis: MatchAnalysis;
  home: string;
  away: string;
}) {
  const goal = analysis.models.find((m) => m.family === analysis.score_matrix_family);
  if (!goal?.score_matrix || !goal.expected_goals) return null;
  const sm = goal.score_matrix;
  return (
    <section className="panel" aria-labelledby="so-h">
      <div className="panel__head">
        <h2 id="so-h">Score outlook</h2>
        <span className="chip chip--neutral" style={{ marginLeft: "auto" }}>
          goal model
        </span>
      </div>
      <div className="panel__body stack" style={{ ["--gap" as string]: ".6rem" }}>
        <div className="stat-grid">
          <StatTile
            value={`${sm.most_likely.home}–${sm.most_likely.away}`}
            label="Most likely score"
            hint={`${pct(sm.most_likely.probability)} · goal model`}
          />
          <StatTile
            value={goal.expected_goals.home.toFixed(2)}
            label={`Model goals · ${home}`}
            hint="expected, not predicted"
          />
          <StatTile
            value={goal.expected_goals.away.toFixed(2)}
            label={`Model goals · ${away}`}
            hint="expected, not predicted"
          />
          <StatTile value={<UncertaintyTag level={analysis.uncertainty} />} label="Confidence" />
        </div>
        <details className="council-more">
          <summary>Full exact-score grid (goal model)</summary>
          <div style={{ marginTop: ".75rem" }}>
            <ScoreMatrixHeatmap matrix={sm} home={home} away={away} />
          </div>
        </details>
      </div>
    </section>
  );
}
