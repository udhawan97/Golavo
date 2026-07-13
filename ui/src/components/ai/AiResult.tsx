/**
 * The rendered AI read. Editorial prose with footnote markers, a verdict hero,
 * a clearly-separated web-research lane, the model-memory lane, and one
 * deduplicated evidence legend. Every number and citation comes from the
 * backend envelope; the UI adds nothing of its own.
 */
import { DATA_SOURCE } from "../../lib/api";
import type {
  BackgroundNote, NarrationClaim, NarrativeResponse, NumberRef, ResearchNote, SourceRef,
} from "../../lib/ai";
import type { AiDepth } from "../../lib/ai";
import { buildEvidenceIndex, hostnameOf } from "../../lib/aiEvidence";
import type { EvidenceIndex } from "../../lib/aiEvidence";
import {
  ExternalLinkIcon, GlobeIcon, ShieldCheckIcon, SparkIcon,
} from "../icons";
import { EvidenceLegend, FootnoteRef, NumberChip } from "./AiEvidence";
import { FallbackCard, OffCard } from "./AiFallback";

export function Result({
  data, isMatch, depth, onSwitchFast, onRefresh, onRetry,
}: {
  data: NarrativeResponse;
  isMatch: boolean;
  depth: AiDepth;
  onSwitchFast?: () => void;
  onRefresh: () => void;
  onRetry: () => void;
}) {
  if (data.status === "disabled") return <OffCard />;
  // "unavailable" is recoverable in live mode (start Ollama / pull a model / add a
  // key, then retry) but genuinely terminal in the sample-data preview, so only
  // offer a retry when there's a real backend to retry against.
  if (data.status === "unavailable")
    return (
      <FallbackCard
        reason={data.reason}
        unavailable
        onRetry={DATA_SOURCE === "mock" ? undefined : onRetry}
      />
    );
  const timedOut = data.status === "local_only" && /timed out|reached/i.test(data.reason ?? "");
  if (data.status === "local_only")
    return (
      <FallbackCard
        reason={data.reason}
        notes={data.notes}
        onRetry={onRetry}
        onSwitchFast={depth === "deep" && timedOut ? onSwitchFast : undefined}
      />
    );
  if (data.status !== "ok" || !data.narration)
    return <FallbackCard reason={data.reason} notes={data.notes} onRetry={onRetry} />;

  const sourceById = new Map<string, SourceRef>(data.sources.map((s) => [s.source_id, s]));
  const numberById = new Map<string, NumberRef>(data.numbers.map((n) => [n.id, n]));
  const { claims, scenarios } = data.narration;
  const verdict = data.narration.verdict ?? null;
  const research = data.narration.research_notes ?? [];
  const background = data.narration.background ?? [];
  const evidence = buildEvidenceIndex(data.narration, data.sources);

  const nothing =
    !verdict && claims.length === 0 && scenarios.length === 0 &&
    research.length === 0 && background.length === 0;

  return (
    <div className="stack ai-result" style={{ ["--gap" as string]: "var(--space-5)" }}>
      {verdict && (
        <VerdictHero claim={verdict} sourceById={sourceById} numberById={numberById} evidence={evidence} />
      )}

      {claims.length > 0 && (
        <ClaimList
          title={isMatch ? "The deeper read" : "Reading"}
          items={claims}
          sourceById={sourceById}
          numberById={numberById}
          evidence={evidence}
        />
      )}
      {scenarios.length > 0 && (
        <ClaimList
          title="Scenarios"
          items={scenarios}
          sourceById={sourceById}
          numberById={numberById}
          evidence={evidence}
          bulleted
        />
      )}
      {nothing && (
        <p className="ai-note">The model returned nothing it could ground in the evidence.</p>
      )}

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
        <span className="dim">
          {data.provider} · {data.model} · prompt {data.prompt_version}
        </span>
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

/** Render a claim's text with its footnote markers and inline number chips. */
function ClaimBody({
  claim, sourceById, numberById, evidence,
}: {
  claim: NarrationClaim;
  sourceById: Map<string, SourceRef>;
  numberById: Map<string, NumberRef>;
  evidence: EvidenceIndex;
}) {
  const refs = claim.number_refs
    .map((r) => numberById.get(r))
    .filter((n): n is NumberRef => Boolean(n));
  return (
    <>
      <p className="ai-claim__text measure">
        {claim.text}
        {claim.source_ids.map((sid) => {
          const n = evidence.indexOf(sid);
          const src = sourceById.get(sid);
          return n && src ? <FootnoteRef key={sid} n={n} source={src} /> : null;
        })}
      </p>
      {refs.length > 0 && (
        <span className="ai-claim__nums">
          {refs.map((num) => <NumberChip key={num.id} num={num} />)}
        </span>
      )}
    </>
  );
}

/** The verdict hero: the engine's most-likely outcome, in one line, on a
 *  gold-lit card. Engine-verified numbers only. */
function VerdictHero({
  claim, sourceById, numberById, evidence,
}: {
  claim: NarrationClaim;
  sourceById: Map<string, SourceRef>;
  numberById: Map<string, NumberRef>;
  evidence: EvidenceIndex;
}) {
  return (
    <div className="ai-verdict">
      <span className="ai-verdict__icon" aria-hidden><ShieldCheckIcon size={20} /></span>
      <div className="ai-verdict__body">
        <span className="ai-verdict__kicker">Most likely · engine-verified</span>
        <div className="ai-verdict__text">
          <ClaimBody claim={claim} sourceById={sourceById} numberById={numberById} evidence={evidence} />
        </div>
      </div>
    </div>
  );
}

function ClaimList({
  title, items, sourceById, numberById, evidence, bulleted = false,
}: {
  title: string;
  items: NarrationClaim[];
  sourceById: Map<string, SourceRef>;
  numberById: Map<string, NumberRef>;
  evidence: EvidenceIndex;
  bulleted?: boolean;
}) {
  return (
    <div className="stack" style={{ ["--gap" as string]: "var(--space-3)" }}>
      <h3 className="ai-subhead">{title}</h3>
      <ul className={`ai-claims${bulleted ? " ai-claims--bulleted" : ""}`}>
        {items.map((claim, i) => (
          <li key={i} className="ai-claim">
            {bulleted && <span className="ai-claim__bullet" aria-hidden><SparkIcon size={14} /></span>}
            <div className="ai-claim__main">
              <ClaimBody claim={claim} sourceById={sourceById} numberById={numberById} evidence={evidence} />
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** The web-research lane — clearly second-class: wave-tinted dashed card, globe
 *  mark, an honest "not engine-verified" badge, and outbound links. Numbers here
 *  were checked against the quoted page, never against the engine. */
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
        {notes.map((note, i) => (
          <li key={i} className="ai-research__item">
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

/** The general-knowledge lane: qualitative colour from the model, badged as
 *  not-Golavo-data and may-be-outdated; no numbers (any were deleted server-side). */
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
        {notes.map((n, i) => (
          <li key={i}>
            <span className="ai-background__mark" aria-hidden title="unverified">◇</span>
            {n.text}
          </li>
        ))}
      </ul>
    </details>
  );
}
