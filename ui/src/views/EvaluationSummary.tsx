import { useState } from "react";
import type { EvalSummary, Fold, FoldModel, ModelFamily, ReportCard } from "../lib/contract";
import { FAMILY_LABELS } from "../lib/contract";
import { fetchEvalSummary } from "../lib/api";
import { num } from "../lib/format";
import { METRIC_GLOSS } from "../lib/glossary";
import { useAsync } from "../lib/hooks";
import { ReliabilityDiagram } from "../components/ReliabilityDiagram";
import { BlockSkeleton, EmptyState, ErrorState, Loading } from "../components/states";

const cell = (v: number | undefined) => (v === undefined ? "—" : num(v, 3));

export function EvaluationSummary() {
  const state = useAsync(fetchEvalSummary, []);
  return (
    <div className="stack" style={{ ["--gap" as string]: "1.6rem" }}>
      <header className="stack" style={{ ["--gap" as string]: ".4rem" }}>
        <h1>Backtests</h1>
        <p className="muted" style={{ maxWidth: "64ch" }}>
          Out-of-sample scores across held-out folds.{" "}
          <b style={{ color: "var(--text)" }}>Log loss is the headline metric</b> — it rewards honest
          probabilities and punishes overconfidence. Lower is better throughout.
        </p>
        <p className="muted small">
          <a href="#/lab/track-record">Your real sealed forecasts live in Track record ›</a>
        </p>
      </header>

      {state.status === "loading" && (
        <>
          <Loading label="Loading evaluation summary" />
          <BlockSkeleton lines={8} />
        </>
      )}
      {state.status === "error" && <ErrorState error={state.error} />}
      {state.status === "ready" && <Summary data={state.data} />}
    </div>
  );
}

function groupByCompetition(folds: Fold[]): [string, Fold[]][] {
  const order: string[] = [];
  const groups = new Map<string, Fold[]>();
  for (const fold of folds) {
    const key = fold.competition ?? "Evaluation";
    if (!groups.has(key)) {
      groups.set(key, []);
      order.push(key);
    }
    groups.get(key)!.push(fold);
  }
  return order.map((key) => [key, groups.get(key)!]);
}

/** Which family had the lowest log loss on each fold, tallied — the honest
 *  "who led, how often" summary that the raw tables bury. Never averaged. */
function leaderTally(folds: Fold[]): { family: ModelFamily; wins: number }[] {
  const wins = new Map<ModelFamily, number>();
  for (const fold of folds) {
    if (fold.models.length === 0) continue;
    const best = fold.models.reduce((a, b) => (b.log_loss < a.log_loss ? b : a));
    wins.set(best.family, (wins.get(best.family) ?? 0) + 1);
  }
  return [...wins.entries()]
    .map(([family, w]) => ({ family, wins: w }))
    .sort((a, b) => b.wins - a.wins);
}

function LeaderStrip({ folds }: { folds: Fold[] }) {
  const tally = leaderTally(folds);
  if (tally.length === 0) return null;
  return (
    <div className="eval-leaders" role="note">
      <span className="small muted">Lowest log loss across {folds.length} folds:</span>
      {tally.map(({ family, wins }) => (
        <span key={family} className="eval-leaders__item">
          <b>{FAMILY_LABELS[family]}</b> {wins} {wins === 1 ? "fold" : "folds"}
        </span>
      ))}
      <span className="small dim">· raw fold leadership can flip by league and season.</span>
    </div>
  );
}

function Summary({ data }: { data: EvalSummary }) {
  if (data.folds.length === 0) {
    return (
      <EmptyState title="No evaluation folds yet">
        Model scores appear once a backtest has been run over a held-out fold.
      </EmptyState>
    );
  }
  return (
    <>
      {data.report_cards && data.report_cards.length > 0 && (
        <ReportCards cards={data.report_cards} />
      )}
      <LeaderStrip folds={data.folds} />
      {groupByCompetition(data.folds).map(([competition, folds]) => (
        <details key={competition} className="lab-group" open>
          <summary className="lab-group__summary">
            <span className="upper muted">{competition}</span>
            <span className="small dim">{folds.length} {folds.length === 1 ? "fold" : "folds"}</span>
          </summary>
          <div className="stack" style={{ ["--gap" as string]: "1rem", marginTop: "1rem" }}>
            {folds.map((fold) => (
              <FoldTable key={fold.fold_id} fold={fold} />
            ))}
          </div>
        </details>
      ))}
      <Calibration folds={data.folds} />
    </>
  );
}

function signedPct(value: number): string {
  const rounded = (value * 100).toFixed(1);
  return `${value > 0 ? "+" : ""}${rounded}%`;
}

function ReportCards({ cards }: { cards: ReportCard[] }) {
  return (
    <section className="stack" style={{ ["--gap" as string]: "1rem" }} aria-labelledby="cards-h">
      <div>
        <h2 id="cards-h" className="upper muted">Model report cards</h2>
        <p className="small dim measure" style={{ margin: ".25rem 0 0" }}>
          Match-weighted held-out performance by competition. Skill compares log loss with the
          team-blind climatological baseline; intervals use a seeded, fold-stratified match bootstrap.
        </p>
      </div>
      {cards.map((card, index) => (
        <ReportCardTable key={card.competition} card={card} initiallyOpen={index === 0} />
      ))}
    </section>
  );
}

function ReportCardTable({ card, initiallyOpen }: { card: ReportCard; initiallyOpen: boolean }) {
  const best = Math.min(...card.models.map((model) => model.log_loss));
  return (
    <details className="lab-group report-card" open={initiallyOpen}>
      <summary className="lab-group__summary">
        <span className="upper muted">{card.competition}</span>
        <span className="small dim">{card.window_start.slice(0, 4)}–{card.window_end.slice(0, 4)}</span>
      </summary>
      <div className="table-wrap" style={{ marginTop: ".8rem" }}>
        <table className="grid">
          <thead>
            <tr>
              <th scope="col">Model</th>
              <th scope="col">Matches</th>
              <th scope="col">Log loss</th>
              <th scope="col">Skill vs baseline (95% CI)</th>
              <th scope="col">ECE</th>
              <th scope="col">Fold rank</th>
            </tr>
          </thead>
          <tbody>
            {card.models.map((model) => (
              <tr key={model.family} className={model.log_loss === best ? "is-leader" : undefined}>
                <th scope="row">{FAMILY_LABELS[model.family]}</th>
                <td className="num">{model.n_matches} / {model.n_folds} folds</td>
                <td className={`num${model.log_loss === best ? " cell-best" : ""}`}>{num(model.log_loss, 3)}</td>
                <td className="num">
                  {model.sample_status === "available" && model.skill_ci_95
                    ? `${signedPct(model.skill_score)} (${signedPct(model.skill_ci_95[0])} to ${signedPct(model.skill_ci_95[1])})`
                    : `Insufficient sample (a fold has <${card.minimum_matches})`}
                </td>
                <td className="num">{num(model.ece, 3)}</td>
                <td className="num">
                  {num(model.mean_rank, 1)} mean · {model.best_rank}–{model.worst_rank}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="small dim" style={{ margin: ".65rem 0 0" }}>
        Positive skill means lower log loss than climatology. {card.bootstrap.replicates.toLocaleString()} deterministic bootstrap samples; seed root {card.bootstrap.seed}.
      </p>
    </details>
  );
}

function FoldTable({ fold }: { fold: Fold }) {
  const minLL = Math.min(...fold.models.map((m) => m.log_loss));
  const minBrier = Math.min(...fold.models.map((m) => m.brier));
  return (
    <div className="card">
      <div className="panel__head">
        <h3>{fold.fold_id}</h3>
        <span className="muted small" style={{ marginLeft: "auto" }}>
          {fold.n_matches} matches
        </span>
      </div>
      <div className="table-wrap" style={{ border: "none", borderRadius: 0 }}>
        <table className="grid">
          <thead>
            <tr>
              <th scope="col">Model</th>
              <th scope="col" className="headline-col">
                <abbr className="th-gloss" title={METRIC_GLOSS.logLoss}>Log loss</abbr>
              </th>
              <th scope="col"><abbr className="th-gloss" title={METRIC_GLOSS.brier}>Brier</abbr></th>
              <th scope="col"><abbr className="th-gloss" title={METRIC_GLOSS.ece}>ECE</abbr></th>
              <th scope="col"><abbr className="th-gloss" title={METRIC_GLOSS.rps}>RPS</abbr></th>
            </tr>
          </thead>
          <tbody>
            {fold.models.map((m) => (
              <tr key={m.family} className={m.log_loss === minLL ? "is-leader" : undefined}>
                <th scope="row" style={{ fontWeight: 550 }}>{FAMILY_LABELS[m.family]}</th>
                <td className={`num headline-col${m.log_loss === minLL ? " cell-best" : ""}`}>
                  {num(m.log_loss, 3)}
                </td>
                <td className={`num${m.brier === minBrier ? " cell-best" : ""}`}>{num(m.brier, 3)}</td>
                <td className="num">{cell(m.ece)}</td>
                <td className="num">{cell(m.rps)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function hasBins(m: FoldModel): boolean {
  return (
    Array.isArray(m.reliability_bins) &&
    m.reliability_bins.some((b) => b.count > 0 && b.accuracy != null)
  );
}

function Calibration({ folds }: { folds: Fold[] }) {
  const defaultFold = folds.find((f) => f.models.some(hasBins)) ?? folds[0];
  const defaultFamily: ModelFamily =
    [...defaultFold.models].filter(hasBins).sort((a, b) => a.log_loss - b.log_loss)[0]?.family ??
    defaultFold.models[0]?.family ??
    "climatological";

  const [foldId, setFoldId] = useState(defaultFold.fold_id);
  const [family, setFamily] = useState<ModelFamily>(defaultFamily);

  const fold = folds.find((f) => f.fold_id === foldId) ?? defaultFold;
  const model = fold.models.find((m) => m.family === family) ?? fold.models[0];
  const bins = model && hasBins(model) ? model.reliability_bins! : null;

  return (
    <section className="stack" style={{ ["--gap" as string]: "1rem" }} aria-labelledby="cal-h">
      <div className="hgroup">
        <h2 id="cal-h" className="upper muted">Reliability diagram</h2>
        <div className="controls">
          <label className="field">
            Fold
            <select className="select" value={foldId} onChange={(e) => setFoldId(e.target.value)}>
              {folds.map((f) => (
                <option key={f.fold_id} value={f.fold_id}>{f.fold_id}</option>
              ))}
            </select>
          </label>
          <label className="field">
            Model
            <select
              className="select"
              value={model?.family ?? ""}
              onChange={(e) => setFamily(e.target.value as ModelFamily)}
            >
              {fold.models.map((m) => (
                <option key={m.family} value={m.family}>{FAMILY_LABELS[m.family]}</option>
              ))}
            </select>
          </label>
        </div>
      </div>

      <div className="card card--pad">
        {bins ? (
          <div className="reliability">
            <ReliabilityDiagram
              bins={bins}
              caption={`${FAMILY_LABELS[model.family]} · ${fold.fold_id} · ${fold.n_matches} matches`}
            />
          </div>
        ) : (
          <EmptyState title="No calibration data for this selection">
            {model ? FAMILY_LABELS[model.family] : ""} has no populated reliability bins for{" "}
            {fold.fold_id}. On the diagram, points on the dashed line mean the model’s confidence
            matched its observed accuracy.
          </EmptyState>
        )}
      </div>
    </section>
  );
}
