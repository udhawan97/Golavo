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
import { goalThresholds, totalGoalBands } from "../lib/markets";
import { StatTile, UncertaintyTag } from "./primitives";
import { ScoreMatrixHeatmap } from "./ScoreMatrixHeatmap";

/** A quiet two-segment "over vs under / yes vs no" mini bar with mono labels. */
function SplitBar({ label, over, overLabel, underLabel }: {
  label: string;
  over: number;
  overLabel: string;
  underLabel: string;
}) {
  const overPct = Math.round(over * 100);
  return (
    <div className="market-tile">
      <div className="market-tile__label">{label}</div>
      <div
        className="market-bar"
        role="img"
        aria-label={`${overLabel} ${overPct}%, ${underLabel} ${100 - overPct}%`}
      >
        <span className="market-bar__over" style={{ width: `${over * 100}%` }} aria-hidden />
      </div>
      <div className="market-tile__legend small dim">
        <span>{overLabel} <b className="num">{overPct}%</b></span>
        <span>{underLabel} <b className="num">{100 - overPct}%</b></span>
      </div>
    </div>
  );
}

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
  // Over/under lines are EXACT re-buckets of the stored grid; BTTS/clean-sheets
  // come from the analysis' derived_markets (exact from the full matrix — not
  // recoverable from the truncated grid), rendered only when present.
  const thresholds = goalThresholds(sm);
  const over25 = thresholds.find((t) => t.line === 2.5);
  const markets = analysis.derived_markets ?? null;
  const bands = totalGoalBands(sm);
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

        {/* Markets — re-bucketed from the same score grid (over/under) and the
            goal voice's full matrix (BTTS / clean sheets). Same numbers, no new
            computation. */}
        {(over25 || markets) && (
          <div className="market-row">
            {over25 && (
              <SplitBar
                label="Over / under 2.5 goals"
                over={over25.over}
                overLabel="Over"
                underLabel="Under"
              />
            )}
            {markets && (
              <SplitBar
                label="Both teams to score"
                over={markets.btts.yes}
                overLabel="Yes"
                underLabel="No"
              />
            )}
          </div>
        )}

        <details className="council-more">
          <summary>More markets (re-bucketed from the grid)</summary>
          <div className="market-detail stack" style={{ ["--gap" as string]: ".8rem", marginTop: ".75rem" }}>
            <div>
              <div className="small dim" style={{ marginBottom: ".35rem" }}>Total goals — over / under</div>
              <ul className="market-lines">
                {thresholds.map((t) => (
                  <li key={t.line}>
                    <span>Over {t.line}</span>
                    <span className="num">{pct(t.over)}</span>
                    <span className="dim num">Under {pct(t.under)}</span>
                  </li>
                ))}
              </ul>
            </div>
            {markets && (
              <div>
                <div className="small dim" style={{ marginBottom: ".35rem" }}>Clean sheets</div>
                <ul className="market-lines">
                  <li><span>{home}</span><span className="num">{pct(markets.clean_sheets.home)}</span></li>
                  <li><span>{away}</span><span className="num">{pct(markets.clean_sheets.away)}</span></li>
                </ul>
              </div>
            )}
            <div>
              <div className="small dim" style={{ marginBottom: ".35rem" }}>Total-goal bands</div>
              <ul className="market-lines">
                {bands.map((b) => (
                  <li key={b.total}><span>{b.total} goals</span><span className="num">{pct(b.probability)}</span></li>
                ))}
              </ul>
            </div>
          </div>
        </details>

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
