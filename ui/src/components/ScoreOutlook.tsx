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
import { doubleChanceMarkets, goalThresholds, totalGoalBands } from "../lib/markets";
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
  headingLevel = 2,
  expert = false,
}: {
  analysis: MatchAnalysis;
  home: string;
  away: string;
  headingLevel?: 2 | 3;
  expert?: boolean;
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
  const doubleChance = goal.probs ? doubleChanceMarkets(goal.probs) : null;
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
  const cleanSheetPreview = markets
    ? Math.round(markets.clean_sheets.home * 1000) === Math.round(markets.clean_sheets.away * 1000)
      ? {
          label: "Clean sheets level",
          team: "Even",
          probability: markets.clean_sheets.home,
          suffix: " each",
        }
      : markets.clean_sheets.home > markets.clean_sheets.away
        ? { label: "Clean-sheet edge", team: home, probability: markets.clean_sheets.home, suffix: "" }
        : { label: "Clean-sheet edge", team: away, probability: markets.clean_sheets.away, suffix: "" }
    : null;
  const doubleChanceRows = doubleChance ? [
    { label: "1X", description: `${home} or draw`, value: doubleChance.home_or_draw },
    { label: "12", description: "Either side wins", value: doubleChance.home_or_away },
    { label: "X2", description: `Draw or ${away}`, value: doubleChance.draw_or_away },
  ] : [];
  const strongestDoubleChance = doubleChanceRows.reduce<typeof doubleChanceRows[number] | null>(
    (best, row) => !best || row.value > best.value ? row : best,
    null,
  );

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
  const Heading = headingLevel === 3 ? "h3" : "h2";
  return (
    <section className="panel" aria-labelledby="so-h">
      <div className="panel__head">
        <Heading id="so-h">Score outlook</Heading>
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
                <strong>{expert ? "Full market detail" : "Quick market read"}</strong>
                <small>{expert ? "Every exact view from the same goal model" : "One concise takeaway from the same model"}</small>
              </span>
              <ChevronDown className="market-disclosure__chevron" aria-hidden />
            </span>
            {expert ? <span className={`market-preview${cleanSheetPreview ? "" : " market-preview--two"}`}>
              <span className="market-preview__item">
                <span className="market-preview__icon" aria-hidden><ScaleIcon /></span>
                <span><small>Most balanced line</small><strong>O/U {balancedLine.line}</strong></span>
                <b className="num">{pct(balancedLine.over)} / {pct(balancedLine.under)}</b>
              </span>
              {cleanSheetPreview && (
                <span className="market-preview__item">
                  <span className="market-preview__icon market-preview__icon--green" aria-hidden><ShieldCheckIcon /></span>
                  <span><small>{cleanSheetPreview.label}</small><strong>{cleanSheetPreview.team}</strong></span>
                  <b className="num">{pct(cleanSheetPreview.probability)}{cleanSheetPreview.suffix}</b>
                </span>
              )}
              <span className="market-preview__item">
                <span className="market-preview__icon market-preview__icon--wave" aria-hidden><DistributionIcon /></span>
                <span><small>Goal peak</small><strong>{peakBand.total} goals</strong></span>
                <b className="num">{pct(peakBand.probability)}</b>
              </span>
            </span> : strongestDoubleChance ? (
              <span className="market-preview market-preview--casual">
                <span className="market-preview__item">
                  <span className="market-preview__icon" aria-hidden><ScaleIcon /></span>
                  <span><small>Widest safety net</small><strong>{strongestDoubleChance.description}</strong></span>
                  <b className="num">{pct(strongestDoubleChance.value)}</b>
                </span>
              </span>
            ) : null}
          </summary>

          <div className={`market-dashboard${revealProgress < 1 ? " market-dashboard--revealing" : ""}`}>
            {!expert && strongestDoubleChance && (
              <p className="market-casual-takeaway">
                The widest safety net is <strong>{strongestDoubleChance.description}</strong> at <span className="num">{pct(strongestDoubleChance.value)}</span>. Switch to Expert for every line, distribution and score cell.
              </p>
            )}
            {expert && doubleChanceRows.length > 0 && (
              <article className="market-card market-card--double-chance">
                <header className="market-card__head">
                  <span className="market-card__icon" aria-hidden><ScaleIcon size={18} /></span>
                  <span><h3>Double chance</h3><p>Exact pair-sums of the 1X2 voice</p></span>
                </header>
                <dl className="double-chance-list">
                  {doubleChanceRows.map((row) => (
                    <div key={row.label}><dt className="num">{row.label}</dt><dd><span>{row.description}</span><strong className="num">{animatedPct(row.value)}</strong></dd></div>
                  ))}
                </dl>
              </article>
            )}
            {expert && <article className="market-card market-card--thresholds">
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
            </article>}

            {expert && markets && (
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

            {expert && (
              <article className="market-card market-card--tail">
                <header className="market-card__head">
                  <span className="market-card__icon market-card__icon--wave" aria-hidden><DistributionIcon size={18} /></span>
                  <span><h3>Beyond the grid</h3><p>Scores above {sm.max_goals} for either side</p></span>
                </header>
                <p className="small dim">The hidden tail is <strong className="num">{pct(sm.tail.probability)}</strong> of the model distribution, split exactly by outcome:</p>
                <dl className="tail-split">
                  <div><dt>{home} win</dt><dd className="num">{animatedPct(sm.tail.home)}</dd></div>
                  <div><dt>Draw</dt><dd className="num">{animatedPct(sm.tail.draw)}</dd></div>
                  <div><dt>{away} win</dt><dd className="num">{animatedPct(sm.tail.away)}</dd></div>
                </dl>
                <p className="market-card__note">Per-team totals are not shown: this payload splits the tail by outcome, not by which team crossed the grid limit.</p>
              </article>
            )}

            {expert && <article className="market-card market-card--distribution">
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
            </article>}
          </div>
        </details>

        {expert && <details className="score-grid-disclosure">
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
        </details>}
      </div>
    </section>
  );
}
