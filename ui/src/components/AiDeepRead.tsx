import { useEffect, useRef, useState } from "react";
import { DATA_SOURCE, fetchMatchNarrative, fetchNarrative } from "../lib/api";
import {
  AI_PROVIDERS,
  useAiBackground,
  useAiProvider,
} from "../lib/ai";
import type {
  AiProvider,
  BackgroundNote,
  NarrationClaim,
  NarrativeResponse,
  NumberRef,
  SourceRef,
} from "../lib/ai";
import { AlertIcon, CheckIcon, InfoIcon, LinkIcon } from "./icons";

/** What the deep read runs over: a sealed forecast artifact, or a match's
 *  on-demand notes + council (the cockpit). Same guards either way. */
export type DeepReadSource =
  | { kind: "forecast"; artifactId: string }
  | { kind: "match"; matchId: string };

type RunState =
  | { status: "idle" }
  | { status: "loading"; refresh: boolean }
  | { status: "done"; data: NarrativeResponse }
  | { status: "error"; error: Error };

// Factual pipeline stages — what the app actually does to assemble and check
// the evidence. Deliberately NOT a depiction of model reasoning.
const PIPELINE_STAGES = [
  "Assembling the evidence bundle",
  "Listing the numbers the engine allows",
  "The model is reading and writing",
  "Verifying every number against the whitelist",
];

/** A tiny neutral mark for the AI panel header (kept local to avoid implying a
 *  brand or agent identity). */
function ReadMark() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M4 5h10a3 3 0 0 1 3 3v11a2.5 2.5 0 0 0-2.5-2.5H4z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M20 5h-3a3 3 0 0 0-3 3v11" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" opacity="0.55" />
    </svg>
  );
}

export function AiDeepRead({ source }: { source: DeepReadSource }) {
  const [provider, setProvider] = useAiProvider();
  const [allowBackground, setAllowBackground] = useAiBackground();
  const [state, setState] = useState<RunState>({ status: "idle" });
  const runId = useRef(0);
  const sourceKey = source.kind === "forecast" ? source.artifactId : source.matchId;

  // Changing the provider (including back to Off) resets any prior result so the
  // panel never shows a narration attributed to the wrong provider.
  useEffect(() => {
    // Invalidate any request started for the previous provider/subject. Without
    // this, a slow old response can repopulate the panel after the selector has
    // changed and be shown under the wrong provider.
    runId.current += 1;
    setState({ status: "idle" });
  }, [provider, sourceKey]);

  const run = (refresh = false) => {
    const id = ++runId.current;
    setState({ status: "loading", refresh });
    const opts = { refresh, allowBackground };
    const request =
      source.kind === "forecast"
        ? fetchNarrative(source.artifactId, provider, opts)
        : fetchMatchNarrative(source.matchId, provider, opts);
    request.then(
      (data) => { if (id === runId.current) setState({ status: "done", data }); },
      (error) => {
        if (id === runId.current)
          setState({ status: "error", error: error instanceof Error ? error : new Error(String(error)) });
      },
    );
  };

  const isMatch = source.kind === "match";
  return (
    <section className="panel ai-panel" aria-labelledby="ai-h">
      <div className="panel__head ai-panel__head">
        <span className="ai-panel__mark" aria-hidden><ReadMark /></span>
        <h2 id="ai-h">{isMatch ? "AI Analyst Read" : "AI Deep Read"}</h2>
        <span className="chip chip--neutral ai-panel__opt">Optional</span>
        <label className="ai-provider" style={{ marginLeft: "auto" }}>
          <span className="visually-hidden">AI provider</span>
          <select
            value={provider}
            onChange={(e) => {
              // Invalidate synchronously at selection time; the effect below is
              // the second line of defense for provider and subject changes.
              runId.current += 1;
              setProvider(e.target.value as AiProvider);
            }}
            aria-label="AI provider"
          >
            {AI_PROVIDERS.map((p) => (
              <option key={p.value} value={p.value}>{p.label}</option>
            ))}
          </select>
        </label>
      </div>

      <div className="panel__body stack" style={{ ["--gap" as string]: ".9rem" }}>
        {DATA_SOURCE === "mock" && (
          <p className="callout callout--info" style={{ fontSize: ".9rem" }}>
            <InfoIcon size={18} />
            <span>
              This is the sample-data preview — the AI read needs the local Golavo app
              connected to a model.
            </span>
          </p>
        )}
        <p className="ai-disclaimer">
          <InfoIcon size={16} />
          <span>
            {isMatch ? (
              <>
                AI reads the notes and the model council above and writes a <b>deeper
                synthesis</b> — connecting facts to each other and to the probabilities. It{" "}
                <b>cannot change a number</b>; every figure it states is one the deterministic
                engine already produced, and anything unverifiable is dropped.
              </>
            ) : (
              <>
                AI only reads and cites the sealed numbers above. It <b>cannot change a
                probability</b> and <b>does not improve accuracy</b>. Every number it may state is
                one the deterministic engine already produced; anything unverifiable is dropped.
              </>
            )}
          </span>
        </p>

        {provider === "off" && <OffCard />}
        {provider !== "off" && state.status === "idle" && (
          <IdleCard
            provider={provider}
            isMatch={isMatch}
            onRun={() => run(false)}
            allowBackground={allowBackground}
            onToggleBackground={setAllowBackground}
          />
        )}
        {state.status === "loading" && <Pipeline provider={provider} refresh={state.refresh} />}
        {state.status === "error" && <FallbackCard reason={state.error.message} onRetry={() => run(false)} />}
        {state.status === "done" && (
          <Result data={state.data} isMatch={isMatch} onRefresh={() => run(true)} onRetry={() => run(false)} />
        )}
      </div>
    </section>
  );
}

function OffCard() {
  return (
    <p className="ai-note">
      AI is <b>off</b> — the default. The analysis above stands entirely on its own.
      Choose a local model or your own key from the selector (or the AI toggle in the header)
      to add an optional, cited reading.
    </p>
  );
}

function IdleCard({
  provider, isMatch, onRun, allowBackground, onToggleBackground,
}: {
  provider: AiProvider;
  isMatch: boolean;
  onRun: () => void;
  allowBackground: boolean;
  onToggleBackground: (on: boolean) => void;
}) {
  const meta = AI_PROVIDERS.find((p) => p.value === provider);
  return (
    <div className="stack" style={{ ["--gap" as string]: ".7rem" }}>
      <p className="ai-note">
        {meta?.kind === "cloud"
          ? "Uses your own API key (kept in your OS keychain, never logged). A short request is sent to your chosen provider."
          : "Uses a local model on your machine — no key, no cloud. Start Ollama or llama.cpp first."}
      </p>
      <label className="ai-bg-toggle">
        <input
          type="checkbox"
          checked={allowBackground}
          onChange={(e) => onToggleBackground(e.target.checked)}
        />
        <span>
          Also ask for <b>AI background</b> — the model’s own general knowledge (managers, style,
          rivalries). Clearly badged, may be outdated, and <b>no numbers</b> allowed.
        </span>
      </label>
      <div>
        <button type="button" className="ai-run" onClick={onRun}>
          {isMatch ? "Write the deeper read" : "Run AI Deep Read"}
        </button>
      </div>
    </div>
  );
}

/** Honest, informative progress: the factual stages, an indeterminate bar, and
 *  an elapsed-seconds ticker with expectation-setting copy — a local model can
 *  legitimately take a minute, and the user should never wonder if it hung. */
function Pipeline({ provider, refresh }: { provider: AiProvider; refresh: boolean }) {
  const [step, setStep] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const meta = AI_PROVIDERS.find((p) => p.value === provider);
  useEffect(() => {
    const stage = window.setInterval(() => setStep((s) => (s + 1) % PIPELINE_STAGES.length), 1400);
    const tick = window.setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => { window.clearInterval(stage); window.clearInterval(tick); };
  }, []);
  const waitNote =
    elapsed < 8
      ? refresh
        ? "Regenerating — skipping the cached read."
        : "This runs once, then is cached."
      : meta?.kind === "local"
        ? "Local models think at their own pace — a minute is normal. Nothing shows until every number is verified."
        : "Still waiting on the provider. Nothing shows until every number is verified.";
  return (
    <div className="ai-pipeline" role="status" aria-live="polite">
      <span className="visually-hidden">Preparing the AI read…</span>
      <div className="ai-progress" aria-hidden>
        <span className="ai-progress__fill" />
      </div>
      <ol>
        {PIPELINE_STAGES.map((label, i) => (
          <li key={label} className={i === step ? "on" : i < step ? "done" : ""} aria-hidden>
            <span className="ai-pipeline__dot" />{label}
          </li>
        ))}
      </ol>
      <p className="ai-progress__meta small dim" style={{ margin: 0 }}>
        <span className="num">{elapsed}s</span> · {waitNote}
      </p>
    </div>
  );
}

function Result({
  data, isMatch, onRefresh, onRetry,
}: { data: NarrativeResponse; isMatch: boolean; onRefresh: () => void; onRetry: () => void }) {
  if (data.status === "disabled") return <OffCard />;
  if (data.status === "unavailable") return <FallbackCard reason={data.reason} unavailable />;
  if (data.status === "local_only") return <FallbackCard reason={data.reason} onRetry={onRetry} />;
  if (data.status !== "ok" || !data.narration) return <FallbackCard reason={data.reason} onRetry={onRetry} />;

  const sourceById = new Map<string, SourceRef>(data.sources.map((s) => [s.source_id, s]));
  const numberById = new Map<string, NumberRef>(data.numbers.map((n) => [n.id, n]));
  const { claims, scenarios } = data.narration;
  const background = data.narration.background ?? [];

  return (
    <div className="stack" style={{ ["--gap" as string]: "1rem" }}>
      <div className="ai-verified">
        <CheckIcon size={15} />
        <span>
          {isMatch
            ? "Every number below was verified against the engine's own analysis. The AI connects the evidence — it does not change it."
            : "Every number below was verified against the sealed forecast. It explains those numbers — it does not change them."}
        </span>
      </div>

      {claims.length > 0 && (
        <ClaimList title={isMatch ? "The deeper read" : "Reading"} items={claims} sourceById={sourceById} numberById={numberById} />
      )}
      {scenarios.length > 0 && (
        <ClaimList title="Scenarios" items={scenarios} sourceById={sourceById} numberById={numberById} />
      )}
      {claims.length === 0 && scenarios.length === 0 && (
        <p className="ai-note">The model returned nothing it could ground in the evidence.</p>
      )}

      {background.length > 0 && <BackgroundLane notes={background} />}

      <p className="ai-meta">
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

function ClaimList({
  title, items, sourceById, numberById,
}: {
  title: string;
  items: NarrationClaim[];
  sourceById: Map<string, SourceRef>;
  numberById: Map<string, NumberRef>;
}) {
  return (
    <div className="stack" style={{ ["--gap" as string]: ".55rem" }}>
      <h3 className="ai-subhead">{title}</h3>
      <ul className="ai-claims">
        {items.map((claim, i) => (
          <li key={i} className="ai-claim">
            <p>{claim.text}</p>
            <div className="ai-chips">
              {claim.number_refs.map((ref) => {
                const num = numberById.get(ref);
                return num ? (
                  <span key={ref} className="ai-chip ai-chip--num" title={num.label}>{num.display}</span>
                ) : null;
              })}
              {claim.source_ids.map((sid) => {
                const src = sourceById.get(sid);
                if (!src) return null;
                return (
                  <a
                    key={sid}
                    className={`ai-chip ai-chip--src ai-chip--${src.kind}`}
                    href={src.url}
                    target="_blank"
                    rel="noreferrer"
                    title={`${src.kind}: ${src.title}`}
                  >
                    <LinkIcon size={12} />{src.title}
                  </a>
                );
              })}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** The second, clearly-separated lane: general-knowledge colour from the model.
 *  Badged as not-Golavo-data, may-be-outdated; no number chips, no source chips
 *  (there are none by design — anything numeric was deleted server-side). */
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

function FallbackCard({
  reason, unavailable = false, onRetry,
}: { reason: string | null; unavailable?: boolean; onRetry?: () => void }) {
  return (
    <div className="callout callout--info ai-fallback">
      {unavailable ? <InfoIcon size={18} /> : <AlertIcon size={18} />}
      <div>
        <div className="callout__title">
          {unavailable ? "AI unavailable" : "Showing the deterministic analysis only"}
        </div>
        {reason ??
          "AI output could not be verified against the engine's numbers, so it was discarded. " +
          "The analysis above is unaffected."}
        {onRetry && (
          <div style={{ marginTop: ".5rem" }}>
            <button type="button" className="ai-refresh" onClick={onRetry}>Try again</button>
          </div>
        )}
      </div>
    </div>
  );
}
