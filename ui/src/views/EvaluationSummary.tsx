import { useState } from "react";
import type { EvalSummary, Fold, FoldModel } from "../lib/contract";
import { fetchEvalSummary } from "../lib/api";
import { num } from "../lib/format";
import { useAsync } from "../lib/hooks";
import { ReliabilityDiagram } from "../components/ReliabilityDiagram";
import { BlockSkeleton, EmptyState, ErrorState, Loading } from "../components/states";

const SHORT_LABELS: Record<string, string> = {
  clim: "Climatological", elo: "Elo · ordered logit", poi: "Poisson (independent)",
  dc: "Dixon–Coles", bvp: "Bivariate Poisson",
};
function modelLabel(model_id: string): string {
  const short = model_id.split("-")[0];
  return SHORT_LABELS[short] ?? model_id;
}
const cell = (v: number | undefined) => (v === undefined ? "—" : num(v, 3));

export function EvaluationSummary() {
  const state = useAsync(fetchEvalSummary, []);
  return (
    <div className="stack" style={{ ["--gap" as string]: "1.6rem" }}>
      <header className="stack" style={{ ["--gap" as string]: ".4rem" }}>
        <h1>Evaluation</h1>
        <p className="muted" style={{ maxWidth: "64ch" }}>
          Out-of-sample scores across held-out tournaments. <b style={{ color: "var(--text)" }}>Log loss is the headline metric</b> —
          it rewards honest probabilities and punishes overconfidence. Lower is better throughout.
        </p>
      </header>

      {state.status === "loading" && (<><Loading label="Loading evaluation summary" /><BlockSkeleton lines={8} /></>)}
      {state.status === "error" && <ErrorState error={state.error} />}
      {state.status === "ready" && <Summary data={state.data} />}
    </div>
  );
}

function Summary({ data }: { data: EvalSummary }) {
  if (data.folds.length === 0) {
    return <EmptyState title="No evaluation folds yet">Model scores appear once a backtest has been run over a held-out tournament.</EmptyState>;
  }
  return (
    <>
      <section className="stack" style={{ ["--gap" as string]: "1rem" }} aria-labelledby="scores-h">
        <h2 id="scores-h" className="upper muted">Model scores by fold</h2>
        {data.folds.map((fold) => <FoldTable key={fold.fold_id} fold={fold} />)}
      </section>
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
        <span className="muted small" style={{ marginLeft: "auto" }}>{fold.n_matches} matches</span>
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
              <tr key={m.model_id}>
                <th scope="row" style={{ fontWeight: 550 }}>{modelLabel(m.model_id)}</th>
                <td className={`num headline-col${m.log_loss === minLL ? " cell-best" : ""}`}>{num(m.log_loss, 3)}</td>
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
  return Array.isArray(m.reliability_bins) && m.reliability_bins.length > 0;
}

function Calibration({ folds }: { folds: Fold[] }) {
  // Default to the first fold + model that actually carry calibration data.
  const defaultFold = folds.find((f) => f.models.some(hasBins)) ?? folds[0];
  const defaultModel =
    [...defaultFold.models].filter(hasBins).sort((a, b) => a.log_loss - b.log_loss)[0]?.model_id
    ?? defaultFold.models[0]?.model_id ?? "";

  const [foldId, setFoldId] = useState(defaultFold.fold_id);
  const [modelId, setModelId] = useState(defaultModel);

  const fold = folds.find((f) => f.fold_id === foldId) ?? defaultFold;
  const model = fold.models.find((m) => m.model_id === modelId) ?? fold.models[0];
  const bins = model && hasBins(model) ? model.reliability_bins! : null;

  return (
    <section className="stack" style={{ ["--gap" as string]: "1rem" }} aria-labelledby="cal-h">
      <div className="hgroup">
        <h2 id="cal-h" className="upper muted">Reliability diagram</h2>
        <div className="controls">
          <label className="field">Fold
            <select className="select" value={foldId} onChange={(e) => setFoldId(e.target.value)}>
              {folds.map((f) => <option key={f.fold_id} value={f.fold_id}>{f.fold_id}</option>)}
            </select>
          </label>
          <label className="field">Model
            {/* Bind to the resolved model so the value always matches an option,
                even if the retained selection is absent from a newly picked fold. */}
            <select className="select" value={model?.model_id ?? ""} onChange={(e) => setModelId(e.target.value)}>
              {fold.models.map((m) => <option key={m.model_id} value={m.model_id}>{modelLabel(m.model_id)}</option>)}
            </select>
          </label>
        </div>
      </div>

      <div className="card card--pad">
        {bins ? (
          <div className="reliability">
            <ReliabilityDiagram bins={bins} caption={`${modelLabel(model.model_id)} · ${fold.fold_id} · ${fold.n_matches} matches`} />
          </div>
        ) : (
          <EmptyState title="No calibration data for this selection">
            {modelLabel(model?.model_id ?? "")} has no reliability bins recorded for {fold.fold_id}.
            Try another fold or model — points on the dashed line mean the model’s stated
            probabilities matched observed frequencies.
          </EmptyState>
        )}
      </div>
    </section>
  );
}
