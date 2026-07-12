import type { ForecastArtifact } from "../lib/contract";
import { num, pct, utc } from "../lib/format";
import { SealIcon } from "./icons";
import { ProbabilityBar, Hash, StatTile } from "./primitives";

/** "After the whistle" — the sealed forecast set beside the full-time result.
 *  No win/loss verdict: a forecast is a probability, scored by how much it
 *  committed to what actually happened. */
export function ScoredPanel({ artifact }: { artifact: ForecastArtifact }) {
  const { evaluation, forecast, match, provenance } = artifact;
  if (!evaluation || !forecast.probs) return null;
  const { actual, metrics, scored_at_utc } = evaluation;

  const winnerText =
    actual.outcome === "home" ? `${match.home_team} won`
    : actual.outcome === "away" ? `${match.away_team} won`
    : "Draw";
  const outcomeName =
    actual.outcome === "home" ? match.home_team
    : actual.outcome === "away" ? match.away_team
    : "a draw";

  return (
    <section className="panel stack" aria-labelledby="scored-h" style={{ ["--gap" as string]: "1.1rem" }}>
      <div className="panel__head">
        <h2 id="scored-h">After the whistle</h2>
        <span className="chip chip--neutral" style={{ marginLeft: "auto" }}>Full time</span>
      </div>

      <div className="panel__body stack" style={{ ["--gap" as string]: "1.25rem" }}>
        <div className="result-line">
          <span className="result-score num" aria-label={`Final score ${actual.home_goals} to ${actual.away_goals}`}>
            {actual.home_goals} <span className="dim">–</span> {actual.away_goals}
          </span>
          <span>
            <span className="result-outcome">Result</span><br />
            <b>{winnerText}</b>
          </span>
        </div>

        <div>
          <p className="upper muted" style={{ marginBottom: ".5rem" }}>Sealed probabilities · unchanged</p>
          <ProbabilityBar probs={forecast.probs} home={match.home_team} away={match.away_team} />
          <p className="small muted" style={{ marginTop: ".6rem" }}>
            The model had assigned <b className="num" style={{ color: "var(--text)" }}>{pct(metrics.prob_assigned_to_outcome)}</b> to {outcomeName}.
          </p>
        </div>

        <div className="stat-grid">
          <StatTile
            value={num(metrics.prob_assigned_to_outcome, 3)}
            label="Prob. assigned to outcome"
            hint="Higher means the seal committed more to what happened."
          />
          <StatTile
            value={num(metrics.log_loss, 3)}
            tone="gold"
            label={<>Log loss <span className="dim">· headline</span></>}
            hint="−ln(p) of the sealed probability. Lower is better."
          />
          <StatTile
            value={num(metrics.brier, 3)}
            label="Brier score"
            hint="Squared error across all three outcomes (0–2). Lower is better."
          />
        </div>

        <div className="seal-note">
          <SealIcon size={18} style={{ color: "var(--gold)" }} />
          <div>
            <b>The seal never changed.</b> These probabilities are exactly those committed at{" "}
            {utc(forecast.sealed_at_utc)} — pinned by payload sha256{" "}
            <span style={{ display: "inline-flex", verticalAlign: "middle" }}><Hash value={provenance.payload_sha256} /></span>
            {" "}and scored only afterwards, at {utc(scored_at_utc)}.
          </div>
        </div>
      </div>
    </section>
  );
}
