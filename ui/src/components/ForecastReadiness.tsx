import type { MatchAnalysis, MatchDetailResponse } from "../lib/contract";
import { forecastReadinessItems } from "../lib/forecastReadiness";
import { ShieldCheckIcon } from "./icons";

export function ForecastReadiness({
  detail,
  analysis,
  indexSha256,
}: {
  detail: MatchDetailResponse;
  analysis: MatchAnalysis | null;
  indexSha256: string | null;
}) {
  const items = forecastReadinessItems(detail, analysis, indexSha256);
  return (
    <section className="surface forecast-readiness" aria-labelledby="forecast-readiness-title">
      <header className="section-heading">
        <span className="section-heading__icon"><ShieldCheckIcon /></span>
        <div><p className="eyebrow">Before you trust the preview</p><h2 id="forecast-readiness-title">Forecast readiness</h2></div>
      </header>
      <ul className="trust-grid">
        {items.map((item) => (
          <li key={item.label} className={`trust-grid__item trust-grid__item--${item.state}`}>
            <span className="chip">{item.state}</span>
            <strong>{item.label}</strong>
            <span className="small muted">{item.detail}</span>
          </li>
        ))}
      </ul>
      <p className="small muted">Readiness describes data coverage and sealing capability—not confidence, accuracy, or betting value.</p>
    </section>
  );
}
