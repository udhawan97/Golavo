/**
 * Commentator's Notebook — deterministic, source-backed match facts.
 *
 * Renders facts grouped by label (predictive / context / coincidence). Every
 * fact shows its sample, base rate (when it is a rate), source and freshness.
 * Coincidences are visibly quarantined: they are capped, ranked by specificity
 * not significance, and are never folded into the AI evidence bundle. The whole
 * panel is subordinate to the sealed numbers — it never changes a forecast.
 */
import type { ReactNode } from "react";
import type {
  CommentatorsNotebook as NotebookData,
  FactCategory,
  FactLabel,
  ForecastArtifact,
  NotebookFact,
  NotebookResponse,
  Snapshot,
} from "../lib/contract";
import {
  FACT_CATEGORY,
  FACT_CATEGORY_ORDER,
  FACT_CATEGORY_TEXT,
  FACT_DISPLAY,
  FACT_LABEL_TEXT,
  FACT_SCOPE_TEXT,
} from "../lib/contract";
import { fetchNotebook } from "../lib/api";
import { yearSpan } from "../lib/format";
import type { AsyncState } from "../lib/hooks";
import { useAsync } from "../lib/hooks";
import { topInsights } from "../lib/insights";
import {
  AlertIcon,
  ChevronDown,
  FingerprintIcon,
  PulseIcon,
  TrophyIcon,
  VersusIcon,
} from "./icons";
import { InfoPopover } from "./primitives";
import { BlockSkeleton, EmptyState, ErrorState } from "./states";

const CATEGORY_ICON: Record<FactCategory, ReactNode> = {
  form: <PulseIcon size={15} />,
  head_to_head: <VersusIcon size={15} />,
  records: <TrophyIcon size={15} />,
  signature: <FingerprintIcon size={15} />,
  other: null,
};

const factCategory = (f: NotebookFact): FactCategory => FACT_CATEGORY[f.id] ?? "other";

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
      {!allInSummary && remaining.length > 0 && (
        <div className="nb-reading-key small">
          <span className="nb-reading-key__mark" aria-hidden>01</span>
          <span>
            <b>Quick read first.</b> Open a section for simple stat cards, then open any card for
            the exact wording, date range and source.
          </span>
        </div>
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
      {label === "context" ? (
        // The context label spans many kinds of fact; sub-group it so a reader can
        // scan Form / Head-to-head / Records / Signature at a glance.
        <div className="nb-categories">
          {FACT_CATEGORY_ORDER.map((cat) => {
            const inCat = facts.filter((f) => factCategory(f) === cat);
            if (inCat.length === 0) return null;
            return (
              <details key={cat} className="nb-subgroup">
                <summary className="nb-subgroup__summary">
                  <span className={`nb-subgroup__icon nb-subgroup__icon--${cat}`} aria-hidden>
                    {CATEGORY_ICON[cat]}
                  </span>
                  <span className="nb-subgroup__copy">
                    <b>{FACT_CATEGORY_TEXT[cat]}</b>
                    <span>{categorySummary(inCat)}</span>
                  </span>
                  <span className="nb-subgroup__glance" aria-hidden>
                    {inCat.slice(0, 3).map((fact, i) => (
                      <span key={`${fact.id}-${i}`}>{glanceValue(fact)}</span>
                    ))}
                  </span>
                  <ChevronDown className="nb-subgroup__chevron" size={17} />
                </summary>
                <ul className="nb-list nb-list--grid">
                  {inCat.map((fact, i) => (
                    <FactRow key={`${fact.id}-${i}`} fact={fact} snapshots={snapshots} />
                  ))}
                </ul>
              </details>
            );
          })}
        </div>
      ) : (
        <ul className="nb-list nb-list--grid">
          {facts.map((fact, i) => (
            <FactRow key={`${fact.id}-${i}`} fact={fact} snapshots={snapshots} />
          ))}
        </ul>
      )}
    </div>
  );
}

function FactRow({ fact, snapshots }: { fact: NotebookFact; snapshots: Snapshot[] }) {
  const span = yearSpan(fact.date_range);
  const display = FACT_DISPLAY[fact.id] ?? {
    title: FACT_CATEGORY_TEXT[factCategory(fact)],
    explainer: "A source-backed match fact from the available history.",
  };
  return (
    <li className="nb-fact">
      <div className="nb-fact__top">
        <div className="nb-fact__copy">
          <span className="nb-fact__subj">{fact.subject}</span>
          <h4>{display.title}</h4>
          <p className="nb-fact__simple">{display.explainer}</p>
        </div>
        {fact.base_rate !== null && <RateDial value={fact.base_rate} />}
      </div>
      <div className="nb-fact__meta">
        <span className="nb-metric nb-metric--sample">
          <b>{fact.sample_n.toLocaleString()}</b> {fact.sample_n === 1 ? "match" : "matches"}
          {fact.denominator !== fact.sample_n ? <> / {fact.denominator.toLocaleString()}</> : null}
        </span>
        {span && <span className="nb-metric">{span}</span>}
        <span className="nb-metric">{FACT_SCOPE_TEXT[fact.scope]}</span>
      </div>
      <details className="nb-fact__detail">
        <summary>Full stat &amp; source</summary>
        <div className="nb-fact__detail-body">
          <p className="nb-fact__text">{fact.text}</p>
          <span className="nb-fact__src">
            Source <SourcePopover ids={fact.source_ids} snapshots={snapshots} />
          </span>
        </div>
      </details>
    </li>
  );
}

function RateDial({ value }: { value: number }) {
  const safe = Math.max(0, Math.min(1, value));
  const percent = Math.round(safe * 100);
  return (
    <div
      className="nb-rate"
      style={{ ["--rate" as string]: `${safe * 360}deg` }}
      role="img"
      aria-label={`${percent}% historical rate`}
    >
      <span className="nb-rate__value num">{percent}%</span>
      <span className="nb-rate__label">rate</span>
    </div>
  );
}

function glanceValue(fact: NotebookFact): string {
  if (fact.base_rate !== null) return `${Math.round(fact.base_rate * 100)}%`;
  const preferred = fact.numbers.find((n) =>
    ["run", "goals_for", "avg_goals", "recent_per_game", "goals", "meetings"].includes(n.key),
  );
  return preferred?.display ?? fact.numbers[0]?.display ?? "•";
}

function categorySummary(facts: NotebookFact[]): string {
  const names = [...new Set(facts.map((fact) => FACT_DISPLAY[fact.id]?.title ?? "Other stat"))];
  const preview = names.slice(0, 2).join(" · ");
  const more = names.length > 2 ? ` +${names.length - 2}` : "";
  return `${facts.length} ${facts.length === 1 ? "stat" : "stats"}${preview ? ` · ${preview}${more}` : ""}`;
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
