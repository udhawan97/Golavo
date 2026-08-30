import type { CalibrationSlice, CalibrationSummary, ForecastArtifact } from "../lib/contract";
import { FAMILY_LABELS } from "../lib/contract";
import { num } from "../lib/format";

function SliceCard({
  label,
  slice,
}: {
  label: string;
  slice: CalibrationSlice | undefined;
}) {
  if (!slice) {
    return <div className="card card--pad"><strong>{label}</strong><p className="small dim">No matching scored-seal slice exists yet.</p></div>;
  }
  return (
    <div className="card card--pad stack">
      <strong>{label}</strong>
      <span className="small">{slice.n_scored} scored seals · exact key <code>{slice.key}</code></span>
      {slice.metrics
        ? <span className="small num">Log loss {num(slice.metrics.log_loss, 3)} · Brier {num(slice.metrics.brier, 3)}</span>
        : <span className="small dim">Proper scores held back until {slice.thresholds.metrics_min_scored} scored seals.</span>}
      <span className="small dim">{slice.caveat}</span>
    </div>
  );
}

export function LocalTrackRecordContext({
  artifact,
  calibration,
}: {
  artifact: ForecastArtifact;
  calibration: CalibrationSummary;
}) {
  const slices = calibration.slices ?? [];
  const competition = slices.find((slice) =>
    slice.dimension === "competition" && slice.key === artifact.match.competition);
  const family = slices.find((slice) =>
    slice.dimension === "model_family" && slice.key === artifact.model.family);
  return (
    <section className="panel" aria-labelledby="local-record-context-heading">
      <div className="panel__head"><h2 id="local-record-context-heading">Relevant local sealed record</h2></div>
      <div className="panel__body stack">
        <p className="small dim">Two independent views of this installation’s real sealed-and-scored history. They do not change this forecast or estimate confidence for this match.</p>
        <div className="two-col">
          <SliceCard label={artifact.match.competition} slice={competition} />
          <SliceCard label={FAMILY_LABELS[artifact.model.family] ?? artifact.model.family} slice={family} />
        </div>
        <p className="small dim">Source: {calibration.generated_from}</p>
        <a className="small" href="#/lab/track-record">Open the full track record ›</a>
      </div>
    </section>
  );
}
