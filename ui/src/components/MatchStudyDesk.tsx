import type { MatchAnalysis, Outcome } from "../lib/contract";
import { FAMILY_LABELS } from "../lib/contract";
import { analysisHistorySupport } from "../lib/analysisPresentation";
import { fairDecimal, goalThresholds } from "../lib/markets";
import { pct } from "../lib/format";
import { DistributionIcon, InfoIcon, MatrixIcon, ScaleIcon } from "./icons";
import { BlockSkeleton } from "./states";

function outcomeLabel(outcome: Outcome, home: string, away: string): string {
  if (outcome === "home") return home;
  if (outcome === "away") return away;
  return "Draw";
}

function leadingOutcome(probs: { home: number; draw: number; away: number }): Outcome {
  return (["home", "draw", "away"] as const).reduce((best, candidate) =>
    probs[candidate] > probs[best] ? candidate : best,
  );
}

function ProbabilityValue({ value }: { value: number }) {
  const equivalent = fairDecimal(value);
  return <span className="study-probability">
    <strong className="num">{pct(value)}</strong>
    {equivalent !== null && (
      <span className="study-probability__equivalent num" title="One divided by the model probability. No margin, market movement or recommendation.">
        1/p {equivalent.toFixed(2)}
      </span>
    )}
  </span>;
}

export function MatchStudyDesk({
  analysis,
  loading,
  error,
  unavailableReason,
  onRetry,
  home,
  away,
}: {
  analysis: MatchAnalysis | null;
  loading: boolean;
  error: Error | null;
  unavailableReason: string | null;
  onRetry: () => void;
  home: string;
  away: string;
}) {
  if (loading) return <section id="match-study-desk" className="study-desk" aria-labelledby="study-desk-title"><BlockSkeleton lines={5} /></section>;
  if (error) {
    return <section id="match-study-desk" className="study-desk" aria-labelledby="study-desk-title">
      <header className="study-desk__header"><div><span className="upper">Deterministic match study</span><h2 id="study-desk-title">Study desk</h2></div><span className="chip chip--muted">Analysis error</span></header>
      <p className="study-desk__empty" role="alert">The local analysis could not be loaded: {error.message}</p>
      <div><button type="button" className="btn btn--ghost" onClick={onRetry}>Retry analysis</button></div>
    </section>;
  }
  if (!analysis) {
    return <section id="match-study-desk" className="study-desk" aria-labelledby="study-desk-title">
      <header className="study-desk__header"><div><span className="upper">Deterministic match study</span><h2 id="study-desk-title">Study desk</h2></div><span className="chip chip--muted">No model read</span></header>
      <p className="study-desk__empty">{unavailableReason ?? "No deterministic analysis is available for this fixture."}</p>
    </section>;
  }
  if (analysis.abstained) {
    return <section id="match-study-desk" className="study-desk" aria-labelledby="study-desk-title">
      <header className="study-desk__header"><div><span className="upper">Deterministic match study</span><h2 id="study-desk-title">Study desk</h2></div><span className="chip chip--muted">Models abstained</span></header>
      <p className="study-desk__empty">{analysis.abstain_reason ?? "The deterministic models abstained without publishing a probability."}</p>
    </section>;
  }

  const voices = analysis.models.filter((model) => model.role === "voice" && !model.abstained && model.probs);
  const over25 = analysis.score_matrix
    ? goalThresholds(analysis.score_matrix).find((threshold) => threshold.line === 2.5) ?? null
    : null;
  const score = analysis.score_matrix?.most_likely ?? null;
  const btts = analysis.derived_markets?.btts ?? null;
  const cleanSheets = analysis.derived_markets?.clean_sheets ?? null;
  const support = analysisHistorySupport(analysis);
  const supportMeaning = analysis.explanation?.history_support.meaning
    ?? "Describes the amount of qualifying pre-cutoff match history; it is not confidence.";
  const disagreement = analysis.explanation?.disagreement ?? null;
  const sourceIds = [...new Set([
    analysis.match.source_id,
    ...(analysis.explanation?.provenance.source_ids ?? []),
    analysis.explanation?.provenance.engine_source_id,
  ].filter((source): source is string => Boolean(source)))];

  return <section id="match-study-desk" className="study-desk" aria-labelledby="study-desk-title">
    <header className="study-desk__header">
      <div>
        <span className="upper">Deterministic match study</span>
        <h2 id="study-desk-title">Study desk</h2>
        <p>Separate model voices and exact score-matrix marginals. Fixed lenses, never ranked or averaged.</p>
      </div>
      <div className="study-desk__stamp">
        <span>{analysis.analysis_kind === "preview" ? "Pre-match preview" : "Leak-safe replay"}</span>
        <strong>{support} history support</strong>
      </div>
    </header>

    <div className="study-voice-grid" aria-label="Deterministic model voices">
      {voices.map((voice) => {
        const probs = voice.probs!;
        const leader = leadingOutcome(probs);
        return <article className="study-voice" key={voice.family}>
          <div className="study-voice__title"><ScaleIcon size={16} /><span><small>Model voice</small><strong>{FAMILY_LABELS[voice.family] ?? voice.family}</strong></span></div>
          <div className="study-voice__call">{outcomeLabel(leader, home, away)}</div>
          <dl className="study-voice__probs">
            <div><dt>{home}</dt><dd className="num">{pct(probs.home)}</dd></div>
            <div><dt>Draw</dt><dd className="num">{pct(probs.draw)}</dd></div>
            <div><dt>{away}</dt><dd className="num">{pct(probs.away)}</dd></div>
          </dl>
        </article>;
      })}
      <article className="study-voice study-voice--disagreement">
        <div className="study-voice__title"><DistributionIcon size={16} /><span><small>Council reading</small><strong>Model disagreement</strong></span></div>
        <div className="study-voice__call">
          {disagreement?.status === "modal_agreement" ? "Voices agree" : disagreement?.status === "modal_split" ? "Voices split" : "Not comparable"}
        </div>
        <p>{disagreement?.largest_gap
          ? `${disagreement.largest_gap.percentage_points.toFixed(1)} percentage-point largest spread on ${outcomeLabel(disagreement.largest_gap.outcome, home, away)}.`
          : "No comparable percentage-point spread is available."}</p>
      </article>
    </div>

    <div className="study-lens-grid" aria-label="Goal-model probability lenses">
      {score && <article className="study-lens"><span className="study-lens__icon"><MatrixIcon size={17} /></span><span><small>Most likely exact score</small><strong className="num">{score.home}–{score.away}</strong></span><ProbabilityValue value={score.probability} /></article>}
      {over25 && <article className="study-lens"><span className="study-lens__icon"><DistributionIcon size={17} /></span><span><small>Goals · 2.5 line</small><strong>{over25.over >= over25.under ? "Over 2.5" : "Under 2.5"}</strong></span><ProbabilityValue value={Math.max(over25.over, over25.under)} /></article>}
      {btts && <article className="study-lens"><span className="study-lens__icon"><DistributionIcon size={17} /></span><span><small>Both teams score</small><strong>{btts.yes >= btts.no ? "Yes" : "No"}</strong></span><ProbabilityValue value={Math.max(btts.yes, btts.no)} /></article>}
      {cleanSheets && <>
        <article className="study-lens"><span className="study-lens__icon"><DistributionIcon size={17} /></span><span><small>Clean-sheet probability</small><strong>{home}</strong></span><ProbabilityValue value={cleanSheets.home} /></article>
        <article className="study-lens"><span className="study-lens__icon"><DistributionIcon size={17} /></span><span><small>Clean-sheet probability</small><strong>{away}</strong></span><ProbabilityValue value={cleanSheets.away} /></article>
      </>}
    </div>

    <div className="study-capabilities" aria-label="Forecast capability limits">
      {[
        ["Scorer forecast", "No approved point-in-time scorer training corpus."],
        ["Corner forecast", "No approved point-in-time corner training corpus."],
        ["Card forecast", "No approved point-in-time card training corpus."],
      ].map(([label, reason]) => <div key={label}><InfoIcon size={15} /><span><strong>{label}</strong><small>{reason}</small></span><b>Unavailable</b></div>)}
    </div>

    <footer className="study-desk__footer">
      <span>Information cutoff <b className="num">{analysis.information_cutoff_utc}</b></span>
      <span>History support means: {supportMeaning}</span>
      <span>Model families: {voices.map((voice) => <code key={voice.family}>{voice.family}</code>)}</span>
      <span>Sources: {sourceIds.map((source) => <code key={source}>{source}</code>)}</span>
      <span>Model-implied equivalents are `1 / probability`: no margin, market movement or recommendation.</span>
    </footer>
  </section>;
}
