/**
 * ScoreOutlook — the goal model's exact-score picture for the fixture.
 *
 * The most-likely score, expected goals per side, and confidence (StatTiles),
 * with the full exact-score grid in a drawer. Every number comes straight from
 * the goal voice's coherent matrix — nothing is derived here. Extracted from the
 * council so the cockpit reads: council verdict → style → score.
 */
import { useEffect, useRef, useState } from "react";
import type { MatchAnalysis } from "../lib/contract";
import { pct } from "../lib/format";
import { goalThresholds, totalGoalBands } from "../lib/markets";
import { ChevronDown, DistributionIcon, MatrixIcon, ScaleIcon, ShieldCheckIcon } from "./icons";
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

function teamMark(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (words.length === 1) return words[0].slice(0, 3).toUpperCase();
  return words.slice(0, 3).map((word) => word[0]).join("").toUpperCase();
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
  const revealedMarkets = useRef(false);
  const revealFrame = useRef<number | null>(null);
  const [revealProgress, setRevealProgress] = useState(1);
  useEffect(() => () => {
    if (revealFrame.current !== null) cancelAnimationFrame(revealFrame.current);
  }, []);

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
  const balancedLine = thresholds.reduce((best, current) =>
    Math.abs(current.over - 0.5) < Math.abs(best.over - 0.5) ? current : best,
  );
  const peakBand = bands.reduce((best, current) =>
    current.probability > best.probability ? current : best,
  );
  const labelledBands = new Set(
    [...bands]
      .sort((a, b) => b.probability - a.probability)
      .slice(0, 3)
      .map((band) => band.total),
  );
  const maxBand = Math.max(...bands.map((band) => band.probability), 0.001);
  const expectedTotal = goal.expected_goals.home + goal.expected_goals.away;
  const expectedMarker = Math.min(100, (expectedTotal / Math.max(1, bands.length - 1)) * 100);
  const cleanSheetLeader = markets
    ? markets.clean_sheets.home >= markets.clean_sheets.away
      ? { team: home, probability: markets.clean_sheets.home }
      : { team: away, probability: markets.clean_sheets.away }
    : null;

  // One requestAnimationFrame loop drives every number in the first market
  // reveal. Reopening is instant, and the global reduced-motion rule remains a
  // second line of defence for the CSS entrance/graph animations.
  const revealMarkets = (open: boolean) => {
    if (!open || revealedMarkets.current) return;
    revealedMarkets.current = true;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const duration = 720;
    const started = performance.now();
    setRevealProgress(0);
    const tick = (now: number) => {
      const elapsed = Math.min(1, (now - started) / duration);
      const eased = 1 - (1 - elapsed) ** 3;
      setRevealProgress(eased);
      if (elapsed < 1) revealFrame.current = requestAnimationFrame(tick);
      else revealFrame.current = null;
    };
    revealFrame.current = requestAnimationFrame(tick);
  };

  const animatedPct = (value: number) => `${(value * revealProgress * 100).toFixed(1)}%`;
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

        <details
          className="market-disclosure"
          onToggle={(event) => revealMarkets(event.currentTarget.open)}
        >
          <summary className="market-disclosure__summary">
            <span className="market-disclosure__heading">
              <span className="market-disclosure__heading-icon" aria-hidden><DistributionIcon size={18} /></span>
              <span>
                <strong>More markets</strong>
                <small>Exact views from the same goal model</small>
              </span>
              <ChevronDown className="market-disclosure__chevron" aria-hidden />
            </span>
            <span className={`market-preview${cleanSheetLeader ? "" : " market-preview--two"}`}>
              <span className="market-preview__item">
                <span className="market-preview__icon" aria-hidden><ScaleIcon /></span>
                <span><small>Most balanced line</small><strong>O/U {balancedLine.line}</strong></span>
                <b className="num">{pct(balancedLine.over)} / {pct(balancedLine.under)}</b>
              </span>
              {cleanSheetLeader && (
                <span className="market-preview__item">
                  <span className="market-preview__icon market-preview__icon--green" aria-hidden><ShieldCheckIcon /></span>
                  <span><small>Clean-sheet edge</small><strong>{cleanSheetLeader.team}</strong></span>
                  <b className="num">{pct(cleanSheetLeader.probability)}</b>
                </span>
              )}
              <span className="market-preview__item">
                <span className="market-preview__icon market-preview__icon--wave" aria-hidden><DistributionIcon /></span>
                <span><small>Goal peak</small><strong>{peakBand.total} goals</strong></span>
                <b className="num">{pct(peakBand.probability)}</b>
              </span>
            </span>
          </summary>

          <div className={`market-dashboard${revealProgress < 1 ? " market-dashboard--revealing" : ""}`}>
            <article className="market-card market-card--thresholds">
              <header className="market-card__head">
                <span className="market-card__icon" aria-hidden><ScaleIcon size={18} /></span>
                <span><h3>Total goals</h3><p>Over / under by model line</p></span>
              </header>
              <div className="market-thresholds">
                {thresholds.map((threshold) => (
                  <div className="market-threshold" key={threshold.line}>
                    <div className="market-threshold__labels">
                      <span><b className="num">{animatedPct(threshold.over)}</b> over</span>
                      <strong className="num">{threshold.line}</strong>
                      <span>under <b className="num">{animatedPct(threshold.under)}</b></span>
                    </div>
                    <div
                      className="market-threshold__track"
                      role="img"
                      aria-label={`Over ${threshold.line}: ${pct(threshold.over)}. Under ${threshold.line}: ${pct(threshold.under)}.`}
                    >
                      <span
                        className="market-threshold__over"
                        style={{ width: `${threshold.over * 100}%` }}
                        aria-hidden
                      />
                    </div>
                  </div>
                ))}
              </div>
            </article>

            {markets && (
              <article className="market-card market-card--clean-sheets">
                <header className="market-card__head">
                  <span className="market-card__icon market-card__icon--green" aria-hidden><ShieldCheckIcon size={18} /></span>
                  <span><h3>Clean-sheet chance</h3><p>Probability of conceding zero</p></span>
                </header>
                <div className="clean-sheet-matchup">
                  {([
                    { side: "home", team: home, probability: markets.clean_sheets.home },
                    { side: "away", team: away, probability: markets.clean_sheets.away },
                  ] as const).map((item) => (
                    <div className={`clean-sheet-team clean-sheet-team--${item.side}`} key={item.side}>
                      <span className="team-mark" aria-hidden>{teamMark(item.team)}</span>
                      <span className="clean-sheet-team__copy">
                        <strong>{item.team}</strong>
                        <small>{item.side === "home" ? "Home" : "Away"}</small>
                      </span>
                      <b className="clean-sheet-team__value num">{animatedPct(item.probability)}</b>
                      <span className="clean-sheet-team__track" aria-hidden>
                        <span style={{ width: `${item.probability * 100}%` }} />
                      </span>
                    </div>
                  ))}
                </div>
                <p className="market-card__note">
                  <ShieldCheckIcon size={14} aria-hidden />
                  Higher means the model sees a stronger route to a shutout.
                </p>
              </article>
            )}

            <article className="market-card market-card--distribution">
              <header className="market-card__head market-card__head--split">
                <span className="market-card__head-main">
                  <span className="market-card__icon market-card__icon--wave" aria-hidden><DistributionIcon size={18} /></span>
                  <span><h3>Total-goal distribution</h3><p>Probability mass across every match total</p></span>
                </span>
                <span className="market-card__metric">
                  <small>Expected total</small>
                  <strong className="num">{expectedTotal.toFixed(2)}</strong>
                </span>
              </header>
              <div className="goal-histogram" role="group" aria-label="Total-goal probability distribution">
                <div className="goal-histogram__plot">
                  <span
                    className="goal-histogram__expected"
                    style={{ left: `${expectedMarker}%` }}
                    aria-hidden
                  >
                    <i />
                    <b>μ {expectedTotal.toFixed(2)}</b>
                  </span>
                  {bands.map((band, index) => {
                    const isPeak = band.total === peakBand.total;
                    const isLabelled = labelledBands.has(band.total);
                    const height = Math.max(2, (band.probability / maxBand) * 100);
                    return (
                      <span
                        className={`goal-histogram__column${isPeak ? " is-peak" : ""}`}
                        key={band.total}
                        role="img"
                        tabIndex={0}
                        aria-label={`${band.total} goals: ${pct(band.probability)}${isPeak ? ", most likely total" : ""}`}
                        style={{ ["--bar-order" as string]: index }}
                      >
                        <span className={`goal-histogram__value num${isLabelled ? " is-visible" : ""}`} aria-hidden>
                          {animatedPct(band.probability)}
                        </span>
                        <span className="goal-histogram__bar-wrap" aria-hidden>
                          <span className="goal-histogram__bar" style={{ height: `${height}%` }} />
                        </span>
                        <strong className="num" aria-hidden>{band.total}</strong>
                        <span className="goal-histogram__tooltip num" aria-hidden>{pct(band.probability)}</span>
                      </span>
                    );
                  })}
                </div>
                <div className="goal-histogram__axis" aria-hidden>
                  <span>Fewer goals</span><span>Total goals</span><span>More goals</span>
                </div>
              </div>
            </article>
          </div>
        </details>

        <details className="score-grid-disclosure">
          <summary className="score-grid-disclosure__summary">
            <span className="score-grid-disclosure__icon" aria-hidden><MatrixIcon size={18} /></span>
            <span className="score-grid-disclosure__copy">
              <strong>Exact-score matrix</strong>
              <small>Every scoreline in the goal model</small>
            </span>
            <span className="score-grid-disclosure__meta num">{sm.max_goals + 1} × {sm.max_goals + 1}</span>
            <ChevronDown className="score-grid-disclosure__chevron" aria-hidden />
          </summary>
          <div className="score-grid-disclosure__body">
            <ScoreMatrixHeatmap matrix={sm} home={home} away={away} />
          </div>
        </details>
      </div>
    </section>
  );
}
