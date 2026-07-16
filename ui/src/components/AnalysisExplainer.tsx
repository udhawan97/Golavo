import type { MatchAnalysis, Outcome } from "../lib/contract";
import { CheckIcon, ChevronDown, InfoIcon, ShieldCheckIcon } from "./icons";

const OUTCOME_LABEL = (outcome: Outcome, home: string, away: string) =>
  outcome === "home" ? home : outcome === "away" ? away : "Draw";

const SUPPORT_LABEL = {
  limited: "Limited history",
  moderate: "Moderate history",
  strong: "Strong history",
} as const;

export function AnalysisExplainer({
  analysis,
  home,
  away,
}: {
  analysis: MatchAnalysis;
  home: string;
  away: string;
}) {
  const explanation = analysis.explanation;
  if (!explanation) return null;
  const { history_support: support, disagreement, capability_coverage: coverage } = explanation;
  const gap = disagreement.largest_gap;
  const sourceIds = explanation.provenance.source_ids;
  const comparisonLabel = disagreement.status === "modal_split"
    ? "voices split"
    : disagreement.status === "modal_agreement"
      ? "voices align on the leading outcome"
      : "voice comparison unavailable";

  return (
    <section className="analysis-depth" aria-labelledby="analysis-depth-title">
      <header className="analysis-depth__head">
        <span>
          <span className="upper">How to read this</span>
          <strong id="analysis-depth-title">Depth without false certainty</strong>
        </span>
        <span className="chip chip--neutral">Descriptive only</span>
      </header>

      <p className="analysis-depth__glance">
        {SUPPORT_LABEL[support.level]} ·{" "}
        {comparisonLabel} ·{" "}
        {coverage.available_count} of {coverage.assessed_count} capability checks available
      </p>

      <details className="analysis-depth__disclosure">
        <summary>
          <span>Show evidence limits and change triggers</span>
          <ChevronDown aria-hidden />
        </summary>
        <div className="analysis-depth__disclosure-body">
          <div className="analysis-depth__grid">
        <article className="analysis-depth__metric">
          <span className="analysis-depth__icon" aria-hidden><ShieldCheckIcon /></span>
          <span className="upper">History support</span>
          <strong>{SUPPORT_LABEL[support.level]}</strong>
          <p>
            <span className="num">{support.minimum_qualifying_matches}</span> qualifying matches
            for the thinner side. This measures training coverage, not confidence or accuracy.
          </p>
        </article>

        <article className="analysis-depth__metric">
          <span className="analysis-depth__icon analysis-depth__icon--wave" aria-hidden><InfoIcon /></span>
          <span className="upper">Voice comparison</span>
          <strong>
            {disagreement.status === "modal_split"
              ? "Different leading outcomes"
              : disagreement.status === "modal_agreement"
                ? "Same leading outcome"
                : "Not enough voices to compare"}
          </strong>
          <p>
            {gap
              ? `Largest gap: ${gap.percentage_points.toFixed(1)} percentage points on ${OUTCOME_LABEL(gap.outcome, home, away)}.`
              : "Golavo does not manufacture a comparison when a voice is unavailable."}
            {" "}No probabilities are averaged.
          </p>
        </article>

        <article className="analysis-depth__metric">
          <span className="analysis-depth__icon analysis-depth__icon--green" aria-hidden><CheckIcon /></span>
          <span className="upper">Capability coverage</span>
          <strong><span className="num">{coverage.available_count}</span> of {coverage.assessed_count} checks</strong>
          <p>Known inputs and product capabilities only. This is not a forecast-quality score.</p>
        </article>
          </div>

          <div className="analysis-depth__details">
        <details>
          <summary>
            <span>What would change this analysis?</span>
            <ChevronDown aria-hidden />
          </summary>
          <div className="analysis-depth__detail-body">
            <p className="small muted">
              These are hypothetical system triggers, not estimated effects. They never rewrite a
              sealed forecast.
            </p>
            <ul>
              {explanation.change_triggers.map((trigger) => (
                <li key={trigger.id}><strong>{trigger.label}</strong><span>{trigger.description}</span></li>
              ))}
            </ul>
          </div>
        </details>

        <details>
          <summary>
            <span>What evidence is missing?</span>
            <ChevronDown aria-hidden />
          </summary>
          <div className="analysis-depth__detail-body">
            <p>
              Golavo has no verified lineup, injury, or observed-xG feed here. It does not estimate
              their effect or relabel model-implied goals as observed xG.
            </p>
          </div>
        </details>
          </div>

          <footer className="analysis-depth__provenance">
            Formula <code>{explanation.provenance.formula_version}</code>
            <span aria-hidden>·</span>
            Inputs {sourceIds.length > 0 ? sourceIds.join(", ") : "current indexed source"}
            <span aria-hidden>·</span>
            Engine <code>{explanation.provenance.engine_source_id}</code>
          </footer>
        </div>
      </details>
    </section>
  );
}
