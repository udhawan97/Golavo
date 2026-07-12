/**
 * Commentator's Notebook — deterministic, source-backed match facts.
 *
 * Renders facts grouped by label (predictive / context / coincidence). Every
 * fact shows its sample, base rate (when it is a rate), source and freshness.
 * Coincidences are visibly quarantined: they are capped, ranked by specificity
 * not significance, and are never folded into the AI evidence bundle. The whole
 * panel is subordinate to the sealed numbers — it never changes a forecast.
 */
import type {
  CommentatorsNotebook as NotebookData,
  FactLabel,
  ForecastArtifact,
  NotebookFact,
  NotebookResponse,
  Snapshot,
} from "../lib/contract";
import { FACT_LABEL_TEXT, FACT_SCOPE_TEXT } from "../lib/contract";
import { fetchNotebook } from "../lib/api";
import { yearSpan } from "../lib/format";
import type { AsyncState } from "../lib/hooks";
import { useAsync } from "../lib/hooks";
import { topInsights } from "../lib/insights";
import { AlertIcon } from "./icons";
import { InfoPopover, RateBar } from "./primitives";
import { BlockSkeleton, EmptyState, ErrorState } from "./states";

/** A fact's identity within one notebook: template id + which team/pair it is
 *  about. Used to drop the facts already shown in "Three things to know" so the
 *  notebook is genuinely the deeper cut, not a repeat of the summary. */
const factKey = (f: { id: string; subject: string }): string => `${f.id}::${f.subject}`;

const GROUP_ORDER: FactLabel[] = ["predictive", "context", "coincidence"];

const GROUP_NOTE: Record<FactLabel, string> = {
  predictive: "Historical frequencies — shown for context, never fed into the forecast.",
  context: "Background from results — the setting the fixture sits in.",
  coincidence: "",
};

export function CommentatorsNotebook({ artifact }: { artifact: ForecastArtifact }) {
  const state = useAsync(() => fetchNotebook(artifact.artifact_id), [artifact.artifact_id]);
  const snapshots = artifact.inputs.snapshots;

  return (
    <section className="panel" aria-labelledby="nb-h">
      <div className="panel__head">
        <h2 id="nb-h">Commentator’s Notebook</h2>
        <span className="chip chip--neutral" style={{ marginLeft: "auto" }}>
          deterministic · source-backed
        </span>
      </div>
      <div className="panel__body stack" style={{ ["--gap" as string]: "1rem" }}>
        <p className="small muted" style={{ margin: 0 }}>
          Facts computed from the vendored packs. They are background for reading the match —
          they never change the sealed forecast above, and no AI wrote any of them.
        </p>
        <NotebookBody state={state} snapshots={snapshots} />
      </div>
    </section>
  );
}

function NotebookBody({
  state,
  snapshots,
}: {
  state: AsyncState<NotebookResponse>;
  snapshots: Snapshot[];
}) {
  if (state.status === "loading") return <BlockSkeleton lines={4} />;
  if (state.status === "error") return <ErrorState error={state.error} />;
  const { notebook, available } = state.data;
  return <NotebookFacts notebook={available ? notebook : null} snapshots={snapshots} />;
}

/**
 * Presentational notebook body — renders a resolved notebook (facts grouped by
 * label, plus the provenance footer) or its honest empty state. Shared by the
 * forecast-facts panel above and the per-match notebook block, which feeds a
 * notebook that has no owning artifact. Callers own the loading/error framing;
 * this component only renders a settled `notebook` value. `snapshots` resolves
 * source chips to links when known — an empty list degrades to plain source ids.
 */
export function NotebookFacts({
  notebook,
  snapshots = [],
}: {
  notebook: NotebookData | null;
  snapshots?: Snapshot[];
}) {
  if (!notebook || notebook.facts.length === 0) {
    return (
      <EmptyState title="No notebook for this fixture">
        No deterministic facts have been computed for this fixture, or every candidate was
        suppressed by the sample and freshness guards. Nothing is invented to fill the gap.
      </EmptyState>
    );
  }

  // Drop the facts already surfaced in "Three things to know" above, so the
  // notebook is the deeper cut rather than a repeat. Same pure selector, same
  // notebook — so the two panels partition the facts instead of overlapping.
  const summaryKeys = new Set(topInsights(notebook).map(factKey));
  const remaining = notebook.facts.filter((f) => !summaryKeys.has(factKey(f)));
  const allInSummary = remaining.length === 0 && summaryKeys.size > 0;

  return (
    <>
      {summaryKeys.size > 0 && !allInSummary && (
        <p className="small dim" style={{ margin: 0 }}>
          The headline picks are in “Three things to know” above; here is the rest of the notebook.
        </p>
      )}
      {allInSummary && (
        <p className="small dim" style={{ margin: 0 }}>
          Every fact that cleared the guards is in the highlights above — nothing is padded out to
          look fuller.
        </p>
      )}
      {GROUP_ORDER.map((label) => {
        const facts = remaining.filter((f) => f.label === label);
        if (facts.length === 0) return null;
        return (
          <FactGroup
            key={label}
            label={label}
            facts={facts}
            snapshots={snapshots}
            coincidenceCap={notebook.coincidence_cap}
          />
        );
      })}
      <div className="nb-foot small dim">
        <span>
          {notebook.family_size} fixed fact-checks · rule set {notebook.registry_version}
        </span>
        {notebook.suppressed.length > 0 && (
          <span>
            {notebook.suppressed.length} candidate
            {notebook.suppressed.length === 1 ? "" : "s"} suppressed by sample / staleness / cap
            guards
          </span>
        )}
        <span>as of {notebook.as_of_utc.slice(0, 10)}</span>
      </div>
    </>
  );
}

function FactGroup({
  label,
  facts,
  snapshots,
  coincidenceCap,
}: {
  label: FactLabel;
  facts: NotebookFact[];
  snapshots: Snapshot[];
  coincidenceCap: number;
}) {
  const quarantine = label === "coincidence";
  return (
    <div className={quarantine ? "nb-group nb-group--quarantine" : "nb-group"}>
      <div className="nb-group__head">
        <span className={`chip chip--fact-${label}`}>
          <span className="chip__dot" aria-hidden />
          {FACT_LABEL_TEXT[label]}
        </span>
        {quarantine ? (
          <span className="small nb-warn">
            <AlertIcon size={15} /> For the pub, not the forecast — capped at {coincidenceCap},
            never shown to the AI.
          </span>
        ) : (
          <span className="small muted">{GROUP_NOTE[label]}</span>
        )}
      </div>
      <ul className="nb-list">
        {facts.map((fact, i) => (
          <FactRow key={`${fact.id}-${i}`} fact={fact} snapshots={snapshots} />
        ))}
      </ul>
    </div>
  );
}

function FactRow({ fact, snapshots }: { fact: NotebookFact; snapshots: Snapshot[] }) {
  const span = yearSpan(fact.date_range);
  return (
    <li className="nb-fact">
      <p className="nb-fact__text">{fact.text}</p>
      {fact.base_rate !== null && (
        <RateBar value={fact.base_rate} caption={`${(fact.base_rate * 100).toFixed(1)}% base rate`} />
      )}
      <div className="nb-fact__meta">
        <span className="nb-fact__subj">{fact.subject} · {FACT_SCOPE_TEXT[fact.scope]}</span>
        <span className="nb-metric">
          <b>{fact.sample_n.toLocaleString()}</b> in sample
          {fact.denominator !== fact.sample_n ? <> / {fact.denominator.toLocaleString()}</> : null}
        </span>
        {span && <span className="nb-metric">{span}</span>}
        <span className="nb-fact__src">
          <SourcePopover ids={fact.source_ids} snapshots={snapshots} />
        </span>
      </div>
    </li>
  );
}

/** Source as a quiet ⓘ reveal rather than a row of mono pack-id chips — the same
 *  attribution, far less noise. Links out when the snapshot resolves to a URL. */
function SourcePopover({ ids, snapshots }: { ids: string[]; snapshots: Snapshot[] }) {
  return (
    <InfoPopover label="Source">
      <span className="small">
        Computed from{" "}
        {ids.map((id, i) => {
          const snap = snapshots.find((s) => s.snapshot_id === id);
          const label = snap?.source_id ?? id;
          return (
            <span key={id}>
              {i > 0 ? ", " : ""}
              {snap?.url ? (
                <a href={snap.url} target="_blank" rel="noreferrer">{label}</a>
              ) : (
                <span className="mono">{label}</span>
              )}
            </span>
          );
        })}
        . Descriptive history — never a forecast.
      </span>
    </InfoPopover>
  );
}
