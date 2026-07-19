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
import { factKey } from "../lib/factPairs";
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
  ChecklistIcon,
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
 *  notebook is genuinely the deeper cut, not a repeat of the summary. Defined in
 *  lib/factPairs, whose absence lookup is only correct while every caller agrees
 *  on the exact key format; re-exported here so existing importers are unmoved. */
export { factKey };

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
    <section className="panel nb-panel" aria-labelledby="nb-h">
      <div className="panel__head nb-panel__head">
        <span className="nb-panel__mark" aria-hidden><ChecklistIcon size={17} /></span>
        <div>
          <span className="nb-panel__kicker">Official match briefing</span>
          <h2 id="nb-h">Commentator’s Notebook</h2>
        </div>
        <span className="chip chip--neutral" style={{ marginLeft: "auto" }}>
          deterministic · source-backed
        </span>
      </div>
      <div className="panel__body stack" style={{ ["--gap" as string]: "1rem" }}>
        <p className="small muted nb-panel__intro">
          A fixed-rule briefing from vendored match history. Descriptive context only: it never
          changes the forecast, and no AI wrote it.
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
  omitKeys = new Set(),
}: {
  notebook: NotebookData | null;
  snapshots?: Snapshot[];
  omitKeys?: ReadonlySet<string>;
}) {
  const visibleFacts = notebook?.facts.filter((fact) => !omitKeys.has(factKey(fact))) ?? [];
  if (!notebook || visibleFacts.length === 0) {
    return (
      <EmptyState title="No notebook for this fixture">
        No deterministic facts have been computed for this fixture, or every candidate was
        suppressed by the sample and freshness guards. Nothing is invented to fill the gap.
      </EmptyState>
    );
  }

  // One fetch, one panel: lead with the fixed-rule briefing, then place every
  // remaining fact in the deeper ledger. No duplicate panel or parallel ranking.
  const visibleNotebook = { ...notebook, facts: visibleFacts };
  const briefing = topInsights(visibleNotebook);
  const summaryKeys = new Set(briefing.map(factKey));
  const remaining = visibleFacts.filter((f) => !summaryKeys.has(factKey(f)));
  const allInSummary = remaining.length === 0 && summaryKeys.size > 0;

  return (
    <>
      {briefing.length > 0 && (
        <BriefingShelf facts={briefing} notebook={notebook} snapshots={snapshots} />
      )}
      {allInSummary && (
        <p className="small dim nb-all-briefed">
          Every fact that cleared the guards is in the briefing — nothing is padded out.
        </p>
      )}
      {remaining.length > 0 && (
        <div className="nb-ledger">
          <div className="nb-ledger__head">
            <span>Deep notebook</span>
            <p>Open a category for the remaining source-backed facts.</p>
          </div>
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
        </div>
      )}
      <NotebookProvenance notebook={notebook} snapshots={snapshots} />
    </>
  );
}

function BriefingShelf({
  facts,
  notebook,
  snapshots,
}: {
  facts: NotebookFact[];
  notebook: NotebookData;
  snapshots: Snapshot[];
}) {
  return (
    <section className="nb-brief" aria-labelledby="nb-brief-h">
      <div className="nb-brief__head">
        <div>
          <span className="nb-brief__eyebrow">Quick briefing · fixed rules, not AI</span>
          <h3 id="nb-brief-h">Three things to know</h3>
        </div>
        <div className="nb-brief__fixture" aria-label={`${notebook.match.home_team} versus ${notebook.match.away_team}`}>
          <span className="nb-brief__team nb-brief__team--home">{notebook.match.home_team}</span>
          <span aria-hidden>v</span>
          <span className="nb-brief__team nb-brief__team--away">{notebook.match.away_team}</span>
        </div>
      </div>
      <ol className="nb-brief__grid">
        {facts.map((fact, index) => {
          const display = FACT_DISPLAY[fact.id] ?? {
            title: FACT_CATEGORY_TEXT[factCategory(fact)],
            explainer: "A source-backed match fact from the available history.",
          };
          const tone =
            fact.subject === notebook.match.home_team
              ? "home"
              : fact.subject === notebook.match.away_team
                ? "away"
                : "neutral";
          return (
            <li key={factKey(fact)} className={`nb-brief-card nb-brief-card--${tone}`}>
              <div className="nb-brief-card__top">
                <span className="nb-brief-card__index num">{String(index + 1).padStart(2, "0")}</span>
                <span className={`chip chip--fact-${fact.label}`}>
                  <span className="chip__dot" aria-hidden />
                  {FACT_LABEL_TEXT[fact.label]}
                </span>
              </div>
              <span className="nb-brief-card__subject">{fact.subject}</span>
              <div className="nb-brief-card__payoff">
                <strong className="num">{glanceValue(fact)}</strong>
                <div><h4>{display.title}</h4><p>{display.explainer}</p></div>
              </div>
              <details className="nb-brief-card__why">
                <summary>Why this?</summary>
                <div>
                  <p>{fact.text}</p>
                  <span>{fact.sample_n.toLocaleString()} matches · {yearSpan(fact.date_range) ?? "available history"}</span>
                  <span>Source <SourcePopover ids={fact.source_ids} snapshots={snapshots} /></span>
                </div>
              </details>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

function NotebookProvenance({
  notebook,
  snapshots,
}: {
  notebook: NotebookData;
  snapshots: Snapshot[];
}) {
  return (
    <details className="nb-provenance">
      <summary>
        <span><ChecklistIcon size={15} aria-hidden /></span>
        <span>
          <b>Evidence, method &amp; provenance</b>
          <small>{notebook.source_ids.length} source{notebook.source_ids.length === 1 ? "" : "s"} · as of {notebook.as_of_utc.slice(0, 10)}</small>
        </span>
      </summary>
      <div className="nb-provenance__body small">
        <p>
          {notebook.family_size} fixed fact-checks · rule set {notebook.registry_version}. Facts are
          selected and suppressed by deterministic sample, freshness, and coincidence-cap guards.
        </p>
        {notebook.suppressed.length > 0 && (
          <p>{notebook.suppressed.length} candidate{notebook.suppressed.length === 1 ? " was" : "s were"} suppressed by those guards.</p>
        )}
        <p>Source <SourcePopover ids={notebook.source_ids} snapshots={snapshots} /></p>
      </div>
    </details>
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
    <section className={quarantine ? "nb-group nb-group--quarantine" : "nb-group"}>
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
        <details className="nb-subgroup nb-subgroup--single">
          <summary className="nb-subgroup__summary">
            <span className="nb-subgroup__icon" aria-hidden>
              {label === "predictive" ? <PulseIcon size={15} /> : <AlertIcon size={15} />}
            </span>
            <span className="nb-subgroup__copy">
              <b>{facts.length} {facts.length === 1 ? "briefing stat" : "briefing stats"}</b>
              <span>{categorySummary(facts)}</span>
            </span>
            <span className="nb-subgroup__glance" aria-hidden>
              {facts.slice(0, 3).map((fact, i) => <span key={`${fact.id}-${i}`}>{glanceValue(fact)}</span>)}
            </span>
            <ChevronDown className="nb-subgroup__chevron" size={17} />
          </summary>
          <ul className="nb-list nb-list--grid">
            {facts.map((fact, i) => (
              <FactRow key={`${fact.id}-${i}`} fact={fact} snapshots={snapshots} />
            ))}
          </ul>
        </details>
      )}
    </section>
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

export function RateDial({ value }: { value: number }) {
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
export function SourcePopover({ ids, snapshots }: { ids: string[]; snapshots: Snapshot[] }) {
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
