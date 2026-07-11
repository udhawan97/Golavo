/**
 * The REAL prediction ledger: every genuine seal and what became of it.
 *
 * This view renders sealed→scored/voided chains aggregated from immutable
 * artifacts — never evaluation backtests. Those live under #/eval and are
 * labeled as such; the split is the product's honesty boundary.
 */
import type { CalibrationChain, CalibrationSummary, Probs } from "../lib/contract";
import { FAMILY_LABELS, HORIZON_LABELS } from "../lib/contract";
import { fetchCalibration } from "../lib/api";
import { num, pct, utc, utcDate } from "../lib/format";
import { useAsync } from "../lib/hooks";
import { ReliabilityDiagram } from "../components/ReliabilityDiagram";
import { BlockSkeleton, EmptyState, ErrorState, Loading } from "../components/states";

export function PredictionLedger() {
  const state = useAsync(fetchCalibration, []);
  return (
    <div className="stack" style={{ ["--gap" as string]: "1.6rem" }}>
      <header className="stack" style={{ ["--gap" as string]: ".4rem" }}>
        <h1>Prediction ledger</h1>
        <p className="muted" style={{ maxWidth: "64ch" }}>
          Real sealed forecasts and what happened after the whistle — never backtests.
          Each row is an immutable seal; scoring appends a successor from a strictly
          newer data snapshot and can never edit the seal.{" "}
          <b style={{ color: "var(--text)" }}>Backtest folds live under Evaluation.</b>
        </p>
      </header>

      {state.status === "loading" && (
        <>
          <Loading label="Loading the prediction ledger" />
          <BlockSkeleton lines={6} />
        </>
      )}
      {state.status === "error" && <ErrorState error={state.error} />}
      {state.status === "ready" && <Ledger data={state.data} />}
    </div>
  );
}

function Ledger({ data }: { data: CalibrationSummary }) {
  const { counts } = data;
  const total = counts.sealed + counts.abstained;
  if (total === 0) {
    return (
      <EmptyState title="No sealed forecasts yet">
        The ledger fills only with genuine pre-kickoff seals. When an upcoming
        international is sealed, it appears here; after full time a newer snapshot
        scores it and the calibration record grows.
      </EmptyState>
    );
  }
  return (
    <>
      <section aria-label="Ledger counts" className="card card--pad">
        <div className="controls" style={{ flexWrap: "wrap", gap: ".5rem" }}>
          <span className="chip chip--sealed">{counts.sealed} sealed</span>
          <span className="chip chip--abstained">{counts.abstained} abstained</span>
          <span className="chip chip--scored">{counts.scored} scored</span>
          <span className="chip chip--voided">{counts.voided} voided</span>
          <span className="chip chip--neutral">{counts.pending} awaiting full time</span>
          <span className="muted small" style={{ marginLeft: "auto" }}>
            {data.generated_from}
          </span>
        </div>
      </section>

      <RunningCalibration data={data} />

      <section className="stack" style={{ ["--gap" as string]: "1rem" }} aria-labelledby="chains-h">
        <h2 id="chains-h" className="upper muted">Sealed → scored chains</h2>
        <div className="card">
          <div className="table-wrap" style={{ border: "none", borderRadius: 0 }}>
            <table className="grid">
              <thead>
                <tr>
                  <th scope="col">Fixture</th>
                  <th scope="col">Kickoff (day proxy)</th>
                  <th scope="col">Sealed</th>
                  <th scope="col">P(H/D/A)</th>
                  <th scope="col">Outcome</th>
                  <th scope="col" className="headline-col">Log loss</th>
                  <th scope="col">Brier</th>
                </tr>
              </thead>
              <tbody>
                {data.chains.map((chain) => (
                  <ChainRow key={chain.sealed_artifact_id} chain={chain} />
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <p className="small dim" style={{ maxWidth: "70ch" }}>
          The source publishes dates, not kickoff times, so seals close at 00:00 UTC on
          match day — a conservative day-before cutoff. A voided row records a
          postponement or abandonment with its reason; it never fabricates a result.
        </p>
      </section>
    </>
  );
}

function probsLabel(probs: Probs | null): string {
  if (!probs) return "abstained";
  return `${pct(probs.home)} / ${pct(probs.draw)} / ${pct(probs.away)}`;
}

function ChainRow({ chain }: { chain: CalibrationChain }) {
  const { match, resolution } = chain;
  return (
    <tr>
      <th scope="row" style={{ fontWeight: 550 }}>
        <a href={`#/forecast/${encodeURIComponent(chain.sealed_artifact_id)}`}>
          {match.home_team} v {match.away_team}
        </a>
        <div className="small dim">
          {match.competition} · {FAMILY_LABELS[chain.family]} · {HORIZON_LABELS[chain.horizon]}
        </div>
      </th>
      <td>{utcDate(match.kickoff_utc)}</td>
      <td title={utc(chain.sealed_at_utc)}>{utcDate(chain.sealed_at_utc)}</td>
      <td className="num">{probsLabel(chain.probs)}</td>
      <td><Resolution chain={chain} /></td>
      <td className="num headline-col">
        {resolution.metrics ? num(resolution.metrics.log_loss, 3) : "—"}
      </td>
      <td className="num">{resolution.metrics ? num(resolution.metrics.brier, 3) : "—"}</td>
    </tr>
  );
}

function Resolution({ chain }: { chain: CalibrationChain }) {
  const { resolution } = chain;
  if (resolution.status === "scored" && resolution.actual) {
    return (
      <span className="chip chip--scored" title={`scored ${utc(resolution.resolved_at_utc ?? "")}`}>
        {resolution.actual.home_goals}–{resolution.actual.away_goals} ({resolution.actual.outcome})
      </span>
    );
  }
  if (resolution.status === "voided") {
    return (
      <span className="chip chip--voided" title={resolution.void_reason ?? undefined}>
        voided
      </span>
    );
  }
  return <span className="chip chip--neutral">awaiting full time</span>;
}

function RunningCalibration({ data }: { data: CalibrationSummary }) {
  const { running } = data;
  const populated = data.reliability_bins.some((b) => b.count > 0 && b.accuracy != null);
  return (
    <section className="stack" style={{ ["--gap" as string]: "1rem" }} aria-labelledby="running-h">
      <h2 id="running-h" className="upper muted">Running calibration</h2>
      {running ? (
        <div className="card card--pad stack" style={{ ["--gap" as string]: "1rem" }}>
          <div className="controls" style={{ flexWrap: "wrap", gap: "1.5rem" }}>
            <Stat label="Scored seals" value={String(running.n_scored)} />
            <Stat label="Running log loss" value={num(running.log_loss, 3)} headline />
            <Stat label="Running Brier" value={num(running.brier, 3)} />
            <Stat label="Mean P(outcome)" value={pct(running.prob_assigned_to_outcome)} />
          </div>
          {populated && (
            <div className="reliability">
              <ReliabilityDiagram
                bins={data.reliability_bins}
                caption={`Sealed forecasts · ${running.n_scored} scored`}
              />
            </div>
          )}
        </div>
      ) : (
        <div className="card card--pad">
          <EmptyState title="No scored seals yet">
            Running log loss and the reliability diagram appear after the first sealed
            forecast is scored from a newer snapshot.
          </EmptyState>
        </div>
      )}
    </section>
  );
}

function Stat({ label, value, headline }: { label: string; value: string; headline?: boolean }) {
  return (
    <div className="stack" style={{ ["--gap" as string]: ".15rem" }}>
      <span className="small upper muted">{label}</span>
      <span
        className="num"
        style={{
          fontSize: "1.35rem",
          fontWeight: 620,
          color: headline ? "var(--gold)" : "var(--text)",
        }}
      >
        {value}
      </span>
    </div>
  );
}
