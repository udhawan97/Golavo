/**
 * The rendered AI read. The backend still owns every claim, number, and source;
 * this file only gives the validated response an editorial reading order.
 */
import { DATA_SOURCE } from "../../lib/api";
import type {
  BackgroundNote,
  NarrationClaim,
  NarrativeResponse,
  NumberRef,
  ResearchNote,
  SourceRef,
} from "../../lib/ai";
import type { AiDepth } from "../../lib/ai";
import { buildEvidenceIndex, hostnameOf, sourceKindLine } from "../../lib/aiEvidence";
import type { EvidenceIndex } from "../../lib/aiEvidence";
import { presentAiClaims, presentOutcome, presentVerdictText } from "../../lib/aiPresentation";
import type { HistorySupportLevel, Outcome, Uncertainty } from "../../lib/contract";
import { legacyHistorySupport } from "../../lib/analysisPresentation";
import {
  ChecklistIcon,
  ExternalLinkIcon,
  GlobeIcon,
  PulseIcon,
  ScaleIcon,
  ShieldCheckIcon,
  SparkIcon,
} from "../icons";
import { EvidenceLegend, FootnoteRef } from "./AiEvidence";
import { FallbackCard, OffCard } from "./AiFallback";

export interface AiDisplayContext {
  homeTeam: string;
  awayTeam: string;
  uncertainty?: Uncertainty | null;
  historySupport?: HistorySupportLevel | null;
  /** Deterministic engine result used only when the local model omits verdict. */
  leadingOutcome?: Outcome | null;
}

export function Result({
  data,
  isMatch,
  depth,
  context,
  onSwitchFast,
  onRefresh,
  onRetry,
}: {
  data: NarrativeResponse;
  isMatch: boolean;
  depth: AiDepth;
  context?: AiDisplayContext;
  onSwitchFast?: () => void;
  onRefresh: () => void;
  onRetry: () => void;
}) {
  if (data.status === "disabled") return <OffCard />;
  if (data.status === "unavailable") {
    return (
      <FallbackCard
        reason={data.reason}
        unavailable
        onRetry={DATA_SOURCE === "mock" ? undefined : onRetry}
      />
    );
  }

  const timedOut = data.status === "local_only" && /timed out|reached/i.test(data.reason ?? "");
  if (data.status === "local_only") {
    return (
      <FallbackCard
        reason={data.reason}
        notes={data.notes}
        onRetry={onRetry}
        onSwitchFast={depth === "deep" && timedOut ? onSwitchFast : undefined}
      />
    );
  }
  if (data.status !== "ok" || !data.narration) {
    return <FallbackCard reason={data.reason} notes={data.notes} onRetry={onRetry} />;
  }

  const sourceById = new Map<string, SourceRef>(data.sources.map((source) => [source.source_id, source]));
  const numberById = new Map<string, NumberRef>(data.numbers.map((number) => [number.id, number]));
  const { claims, scenarios } = data.narration;
  const verdict = data.narration.verdict ?? null;
  const fallbackOutcome = verdict ? null : context?.leadingOutcome ?? null;
  const research = data.narration.research_notes ?? [];
  const background = data.narration.background ?? [];
  const evidence = buildEvidenceIndex(data.narration, data.sources);
  const presentation = presentAiClaims(claims);
  const nothing =
    !verdict && !fallbackOutcome && claims.length === 0 && scenarios.length === 0 &&
    research.length === 0 && background.length === 0;

  return (
    <div className="ai-result">
      {(verdict || fallbackOutcome) && (
        <VerdictHero
          claim={verdict}
          fallbackOutcome={fallbackOutcome}
          context={context}
          sourceById={sourceById}
          numberById={numberById}
          evidence={evidence}
        />
      )}

      {presentation.story && (
        <MatchStory
          claim={presentation.story}
          isMatch={isMatch}
          sourceById={sourceById}
          numberById={numberById}
          evidence={evidence}
        />
      )}

      {presentation.signals.length > 0 && (
        <SignalGrid
          claims={presentation.signals}
          sourceById={sourceById}
          numberById={numberById}
          evidence={evidence}
        />
      )}

      {scenarios.length > 0 && (
        <ScenarioGrid
          claims={scenarios}
          sourceById={sourceById}
          numberById={numberById}
          evidence={evidence}
        />
      )}

      {presentation.notes.length > 0 && (
        <FullNotes
          claims={presentation.notes}
          sourceById={sourceById}
          numberById={numberById}
          evidence={evidence}
        />
      )}

      {nothing && <p className="ai-note">The model returned nothing it could ground in the evidence.</p>}
      {research.length > 0 && <ResearchLane notes={research} />}
      {background.length > 0 && <BackgroundLane notes={background} />}
      <EvidenceLegend index={evidence} />

      <p className="ai-meta">
        <span className="ai-meta__verified">
          <ShieldCheckIcon size={13} />
          {isMatch
            ? "Every number above was verified against the engine's own analysis."
            : "Every number above was verified against the sealed forecast."}
        </span>
        {data.cached && <span className="chip chip--neutral">cached</span>}
        <span className="dim">{data.provider} · {data.model} · prompt {data.prompt_version}</span>
        <button
          type="button"
          className="ai-refresh"
          onClick={onRefresh}
          title="Regenerate — skips the cache; the new output still passes every guard"
        >
          Refresh read
        </button>
      </p>
    </div>
  );
}

function claimNumbers(claim: NarrationClaim, numberById: Map<string, NumberRef>): NumberRef[] {
  return claim.number_refs
    .map((ref) => numberById.get(ref))
    .filter((number): number is NumberRef => Boolean(number));
}

function ClaimText({
  claim,
  text,
  sourceById,
  evidence,
}: {
  claim: NarrationClaim;
  text?: string;
  sourceById: Map<string, SourceRef>;
  evidence: EvidenceIndex;
}) {
  return (
    <p className="ai-claim__text measure">
      {text ?? claim.text}
      {claim.source_ids.map((sourceId) => {
        const index = evidence.indexOf(sourceId);
        const source = sourceById.get(sourceId);
        return index && source ? <FootnoteRef key={sourceId} n={index} source={source} /> : null;
      })}
    </p>
  );
}

function MetricStrip({ numbers }: { numbers: NumberRef[] }) {
  if (numbers.length === 0) return null;
  return (
    <dl className="ai-metrics">
      {numbers.map((number) => (
        <div key={number.id} className="ai-metric">
          <dt>{number.label}</dt>
          <dd className="num">{number.display}</dd>
        </div>
      ))}
    </dl>
  );
}

function WhyThis({ claim, sourceById }: { claim: NarrationClaim; sourceById: Map<string, SourceRef> }) {
  const sources = claim.source_ids
    .map((sourceId) => sourceById.get(sourceId))
    .filter((source): source is SourceRef => Boolean(source));
  if (sources.length === 0) return null;
  return (
    <details className="ai-why">
      <summary><ChecklistIcon size={13} /> Why this?</summary>
      <ul>
        {sources.map((source) => (
          <li key={source.source_id}>
            <span>{source.title}</span>
            <small>{sourceKindLine(source.kind)}</small>
          </li>
        ))}
      </ul>
    </details>
  );
}

function VerdictHero({
  claim,
  fallbackOutcome,
  context,
  sourceById,
  numberById,
  evidence,
}: {
  claim: NarrationClaim | null;
  fallbackOutcome: Outcome | null;
  context?: AiDisplayContext;
  sourceById: Map<string, SourceRef>;
  numberById: Map<string, NumberRef>;
  evidence: EvidenceIndex;
}) {
  return (
    <section className="ai-verdict" aria-labelledby="ai-verdict-h">
      <div className="ai-verdict__topline">
        <span className="ai-verdict__icon" aria-hidden><ShieldCheckIcon size={20} /></span>
        <div>
          <span className="ai-verdict__kicker">
            {claim ? "Analyst verdict · engine-verified" : "Engine verdict · deterministic"}
          </span>
          <h3 id="ai-verdict-h">At a glance</h3>
        </div>
        {(context?.historySupport || context?.uncertainty) && (
          <span className={`ai-uncertainty ai-uncertainty--${context.historySupport ?? legacyHistorySupport(context.uncertainty!)}`}>
            {context.historySupport ?? legacyHistorySupport(context.uncertainty!)} history support
          </span>
        )}
      </div>
      {context && (
        <div className="ai-versus" aria-label={`${context.homeTeam} versus ${context.awayTeam}`}>
          <span className="ai-versus__team ai-versus__team--home">{context.homeTeam}</span>
          <span className="ai-versus__mark" aria-hidden>v</span>
          <span className="ai-versus__team ai-versus__team--away">{context.awayTeam}</span>
        </div>
      )}
      {context?.leadingOutcome && (
        <div className="ai-verdict__pick" aria-label={`Engine pick: ${presentOutcome(
          context.leadingOutcome,
          context.homeTeam,
          context.awayTeam,
        )}`}>
          <span className="ai-verdict__pick-label">Engine pick</span>
          <strong>{presentOutcome(context.leadingOutcome, context.homeTeam, context.awayTeam)}</strong>
          <span className="ai-verdict__pick-note">leading outcome</span>
        </div>
      )}
      <div className="ai-verdict__statement">
        {claim ? (
          <ClaimText
            claim={claim}
            text={context
              ? presentVerdictText(claim.text, context.homeTeam, context.awayTeam)
              : claim.text}
            sourceById={sourceById}
            evidence={evidence}
          />
        ) : context && fallbackOutcome ? (
          <p className="ai-claim__text measure">
            {presentOutcome(fallbackOutcome, context.homeTeam, context.awayTeam)}
          </p>
        ) : null}
      </div>
      {claim && <MetricStrip numbers={claimNumbers(claim, numberById)} />}
    </section>
  );
}

function MatchStory({
  claim,
  isMatch,
  sourceById,
  numberById,
  evidence,
}: {
  claim: NarrationClaim;
  isMatch: boolean;
  sourceById: Map<string, SourceRef>;
  numberById: Map<string, NumberRef>;
  evidence: EvidenceIndex;
}) {
  return (
    <section className="ai-story" aria-labelledby="ai-story-h">
      <div className="ai-section-heading">
        <span>01</span>
        <div>
          <p>The central tension</p>
          <h3 id="ai-story-h">{isMatch ? "The match story" : "The forecast story"}</h3>
        </div>
      </div>
      <ClaimText claim={claim} sourceById={sourceById} evidence={evidence} />
      <MetricStrip numbers={claimNumbers(claim, numberById)} />
      <WhyThis claim={claim} sourceById={sourceById} />
    </section>
  );
}

const SIGNAL_ICONS = [PulseIcon, ScaleIcon, ShieldCheckIcon] as const;

function SignalGrid({
  claims,
  sourceById,
  numberById,
  evidence,
}: {
  claims: NarrationClaim[];
  sourceById: Map<string, SourceRef>;
  numberById: Map<string, NumberRef>;
  evidence: EvidenceIndex;
}) {
  return (
    <section className="ai-signals" aria-labelledby="ai-signals-h">
      <div className="ai-section-heading">
        <span>02</span>
        <div><p>What supports the story</p><h3 id="ai-signals-h">Key signals</h3></div>
      </div>
      <ol className="ai-signal-grid">
        {claims.map((claim, index) => {
          const Icon = SIGNAL_ICONS[index] ?? PulseIcon;
          return (
            <li key={index} className="ai-signal" style={{ ["--signal-order" as string]: index }}>
              <div className="ai-signal__head">
                <span aria-hidden><Icon size={16} /></span>
                <b>Signal {String(index + 1).padStart(2, "0")}</b>
              </div>
              <ClaimText claim={claim} sourceById={sourceById} evidence={evidence} />
              <MetricStrip numbers={claimNumbers(claim, numberById)} />
              <WhyThis claim={claim} sourceById={sourceById} />
            </li>
          );
        })}
      </ol>
    </section>
  );
}

function ScenarioGrid({
  claims,
  sourceById,
  numberById,
  evidence,
}: {
  claims: NarrationClaim[];
  sourceById: Map<string, SourceRef>;
  numberById: Map<string, NumberRef>;
  evidence: EvidenceIndex;
}) {
  return (
    <section className="ai-scenarios" aria-labelledby="ai-scenarios-h">
      <div className="ai-section-heading">
        <span>03</span>
        <div><p>Conditional, not another forecast</p><h3 id="ai-scenarios-h">What could happen</h3></div>
      </div>
      <ul className="ai-scenario-grid">
        {claims.map((claim, index) => (
          <li key={index} className="ai-scenario">
            <span className="ai-scenario__icon" aria-hidden><SparkIcon size={15} /></span>
            <div>
              <span className="ai-scenario__label">If the match follows path {index + 1}</span>
              <ClaimText claim={claim} sourceById={sourceById} evidence={evidence} />
              <MetricStrip numbers={claimNumbers(claim, numberById)} />
              <WhyThis claim={claim} sourceById={sourceById} />
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

function FullNotes({
  claims,
  sourceById,
  numberById,
  evidence,
}: {
  claims: NarrationClaim[];
  sourceById: Map<string, SourceRef>;
  numberById: Map<string, NumberRef>;
  evidence: EvidenceIndex;
}) {
  return (
    <details className="ai-notes">
      <summary>
        <span><b>Full analyst notes</b><small>{claims.length} additional grounded note{claims.length === 1 ? "" : "s"}</small></span>
      </summary>
      <ul>
        {claims.map((claim, index) => (
          <li key={index}>
            <ClaimText claim={claim} sourceById={sourceById} evidence={evidence} />
            <MetricStrip numbers={claimNumbers(claim, numberById)} />
            <WhyThis claim={claim} sourceById={sourceById} />
          </li>
        ))}
      </ul>
    </details>
  );
}

function ResearchLane({ notes }: { notes: ResearchNote[] }) {
  return (
    <section className="ai-research" aria-labelledby="ai-research-h">
      <div className="ai-research__head">
        <span className="ai-research__mark" aria-hidden><GlobeIcon size={15} /></span>
        <h3 id="ai-research-h" className="ai-subhead">Analyst research</h3>
        <span className="ai-research__badge">from the web — not engine-verified</span>
      </div>
      <p className="ai-research__note small dim">
        Found by the model while researching. Links open in your browser; the numbers here were
        checked against the quoted text, <b>not</b> against Golavo’s engine.
      </p>
      <ul className="ai-research__list">
        {notes.map((note, index) => (
          <li key={index} className="ai-research__item">
            <p className="ai-research__text measure">{note.text}</p>
            {note.quote && <blockquote className="ai-research__quote">{note.quote}</blockquote>}
            <a className="ai-research__link" href={note.source_url} target="_blank" rel="noreferrer">
              <GlobeIcon size={12} />
              {note.title || hostnameOf(note.source_url)}
              <ExternalLinkIcon size={11} />
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}

function BackgroundLane({ notes }: { notes: BackgroundNote[] }) {
  return (
    <details className="ai-background">
      <summary>
        <span className="ai-background__badge">Model memory — not Golavo data · may be outdated</span>
        <span className="dim small"> · {notes.length} note{notes.length === 1 ? "" : "s"}</span>
      </summary>
      <p className="small dim ai-background__note" style={{ marginTop: ".5rem" }}>
        Qualitative context from the model’s own general knowledge — not verified, not from Golavo’s
        data, and possibly out of date. Any number it tried to state was removed.
      </p>
      <ul className="ai-background__list">
        {notes.map((note, index) => (
          <li key={index}>
            <span className="ai-background__mark" aria-hidden title="unverified">◇</span>
            {note.text}
          </li>
        ))}
      </ul>
    </details>
  );
}
