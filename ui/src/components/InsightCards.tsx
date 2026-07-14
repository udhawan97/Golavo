/**
 * "Three things to know" — the casual payoff.
 *
 * A small, scannable summary of the fixture, built ONLY from facts the engine
 * already computed and selected by the pure, documented rule in lib/insights.ts.
 * Nothing here is written or ranked by AI, and no number is invented — which is
 * exactly what the caption says. It reads the same deterministic notebook the
 * full Commentator's Notebook below renders; the source is stable, so the two
 * always agree.
 */
import type { CommentatorsNotebook, Snapshot } from "../lib/contract";
import { FACT_LABEL_TEXT } from "../lib/contract";
import { fetchMatchNotebook, fetchNotebook } from "../lib/api";
import { sinceYear } from "../lib/format";
import { useAsync } from "../lib/hooks";
import { topInsights } from "../lib/insights";
import type { NotebookFact } from "../lib/contract";
import { InfoPopover, RateBar } from "./primitives";

type InsightSource =
  | { kind: "forecast"; artifactId: string; snapshots: Snapshot[] }
  | { kind: "match"; matchId: string };

export function InsightCards({
  source,
  omitKeys = new Set(),
}: {
  source: InsightSource;
  omitKeys?: ReadonlySet<string>;
}) {
  const key = source.kind === "forecast" ? source.artifactId : source.matchId;
  const state = useAsync(
    () =>
      source.kind === "forecast"
        ? fetchNotebook(source.artifactId).then((r) => r.notebook)
        : fetchMatchNotebook(source.matchId).then((r) => r.notebook),
    [source.kind, key],
  );
  // Stay quiet until we have something real — no skeleton box for a section that
  // may legitimately be empty (small sample, all-stale, no notebook).
  if (state.status !== "ready" || !state.data) return null;
  const snapshots = source.kind === "forecast" ? source.snapshots : [];
  return <ResolvedInsightCards notebook={state.data} snapshots={snapshots} omitKeys={omitKeys} />;
}

export function ResolvedInsightCards({
  notebook,
  snapshots = [],
  omitKeys = new Set(),
}: {
  notebook: CommentatorsNotebook | null;
  snapshots?: Snapshot[];
  omitKeys?: ReadonlySet<string>;
}) {
  if (!notebook) return null;
  const visible = {
    ...notebook,
    facts: notebook.facts.filter((fact) => !omitKeys.has(`${fact.id}::${fact.subject}`)),
  };
  const facts = topInsights(visible);
  if (facts.length === 0) return null;

  return (
    <section className="panel" aria-labelledby="ins-h">
      <div className="panel__head">
        <h2 id="ins-h">Three things to know</h2>
        <span className="chip chip--neutral" style={{ marginLeft: "auto" }}>
          chosen by fixed rules · not AI
        </span>
      </div>
      <div className="panel__body">
        <ul className="insight-grid">
          {facts.map((f, i) => (
            <InsightCard key={`${f.id}-${i}`} fact={f} snapshots={snapshots} />
          ))}
        </ul>
      </div>
    </section>
  );
}

function InsightCard({ fact, snapshots }: { fact: NotebookFact; snapshots: Snapshot[] }) {
  const since = sinceYear(fact.date_range);
  return (
    <li className={`insight-card insight-card--${fact.label}`}>
      <div className="insight-card__head">
        <span className={`chip chip--fact-${fact.label}`}>
          <span className="chip__dot" aria-hidden />
          {FACT_LABEL_TEXT[fact.label]}
        </span>
        <span className="insight-card__subj">{fact.subject}</span>
      </div>
      <p className="insight-card__text">{fact.text}</p>
      {fact.base_rate !== null && (
        <RateBar value={fact.base_rate} caption={`${Math.round(fact.base_rate * 100)}% base rate`} />
      )}
      <div className="insight-card__meta">
        <span>{fact.sample_n.toLocaleString()} matches</span>
        {since && <span>· {since}</span>}
        <span style={{ marginLeft: "auto" }}>
          <InfoPopover label="Source">
            <span className="small">
              Computed from{" "}
              {fact.source_ids
                .map((id) => snapshots.find((s) => s.snapshot_id === id)?.source_id ?? id)
                .join(", ")}
              . Descriptive history — never a forecast.
            </span>
          </InfoPopover>
        </span>
      </div>
    </li>
  );
}
