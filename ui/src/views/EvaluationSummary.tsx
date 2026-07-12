import { useState } from "react";
import type { EvalSummary, Fold, FoldModel, ModelFamily } from "../lib/contract";
import { FAMILY_LABELS } from "../lib/contract";
import { fetchEvalSummary } from "../lib/api";
import { num } from "../lib/format";
import { useAsync } from "../lib/hooks";
import { ReliabilityDiagram } from "../components/ReliabilityDiagram";
import { BlockSkeleton, EmptyState, ErrorState, Loading } from "../components/states";

const cell = (v: number | undefined) => (v === undefined ? "—" : num(v, 3));

export function EvaluationSummary() {
  const state = useAsync(fetchEvalSummary, []);
  return (
    <div className="stack" style={{ ["--gap" as string]: "1.6rem" }}>
      <header className="stack" style={{ ["--gap" as string]: ".4rem" }}>
        <h1>Evaluation</h1>
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
      {groupByCompetition(data.folds).map(([competition, folds]) => (
        <section key={competition} className="stack" style={{ ["--gap" as string]: "1rem" }}>
          <h2 className="upper muted">{competition}</h2>
          {folds.map((fold) => (
            <FoldTable key={fold.fold_id} fold={fold} />
          ))}
        </section>
      ))}
      <Calibration folds={data.folds} />
    </>
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
              <th scope="col" className="headline-col">Log loss</th>
              <th scope="col">Brier</th>
              <th scope="col">ECE</th>
              <th scope="col">RPS</th>
            </tr>
          </thead>
          <tbody>
            {fold.models.map((m) => (
              <tr key={m.family}>
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
