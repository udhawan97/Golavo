import { useEffect, useRef, useState } from "react";
import type { ForecastArtifact } from "../lib/contract";
import { fetchNarrative } from "../lib/api";
import {
  AI_PROVIDERS,
  useAiProvider,
} from "../lib/ai";
import type {
  AiProvider,
  NarrationClaim,
  NarrativeResponse,
  NumberRef,
  SourceRef,
} from "../lib/ai";
import { AlertIcon, CheckIcon, InfoIcon, LinkIcon } from "./icons";

type RunState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "done"; data: NarrativeResponse }
  | { status: "error"; error: Error };

// Factual pipeline stages — what the app actually does to assemble and check
// the evidence. Deliberately NOT a depiction of model reasoning.
const PIPELINE_STAGES = [
  "Assembling the sealed evidence bundle",
  "Listing the numbers the engine allows",
  "Reading the evidence with the model",
  "Verifying every number against the seal",
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

export function AiDeepRead({ artifact }: { artifact: ForecastArtifact }) {
  const [provider, setProvider] = useAiProvider();
  const [state, setState] = useState<RunState>({ status: "idle" });
  const runId = useRef(0);

  // Changing the provider (including back to Off) resets any prior result so the
  // panel never shows a narration attributed to the wrong provider.
  useEffect(() => { setState({ status: "idle" }); }, [provider, artifact.artifact_id]);

  const run = () => {
    const id = ++runId.current;
    setState({ status: "loading" });
    fetchNarrative(artifact.artifact_id, provider).then(
      (data) => { if (id === runId.current) setState({ status: "done", data }); },
      (error) => {
        if (id === runId.current)
          setState({ status: "error", error: error instanceof Error ? error : new Error(String(error)) });
      },
    );
  };

  return (
    <section className="panel ai-panel" aria-labelledby="ai-h">
      <div className="panel__head ai-panel__head">
        <span className="ai-panel__mark" aria-hidden><ReadMark /></span>
        <h2 id="ai-h">AI Deep Read</h2>
        <span className="chip chip--neutral ai-panel__opt">Optional</span>
        <label className="ai-provider" style={{ marginLeft: "auto" }}>
          <span className="visually-hidden">AI provider</span>
          <select
            value={provider}
            onChange={(e) => setProvider(e.target.value as AiProvider)}
            aria-label="AI provider"
          >
            {AI_PROVIDERS.map((p) => (
              <option key={p.value} value={p.value}>{p.label}</option>
            ))}
          </select>
        </label>
      </div>

      <div className="panel__body stack" style={{ ["--gap" as string]: ".9rem" }}>
        <p className="ai-disclaimer">
          <InfoIcon size={16} />
          <span>
            AI only reads and cites the sealed numbers above. It <b>cannot change a
            probability</b> and <b>does not improve accuracy</b>. Every number it may state is
            one the deterministic engine already produced; anything unverifiable is dropped.
          </span>
        </p>

        {provider === "off" && <OffCard />}
        {provider !== "off" && state.status === "idle" && <IdleCard provider={provider} onRun={run} />}
        {state.status === "loading" && <Pipeline />}
        {state.status === "error" && <FallbackCard reason={state.error.message} />}
        {state.status === "done" && <Result data={state.data} onRetry={run} />}
      </div>
    </section>
  );
}

function OffCard() {
  return (
    <p className="ai-note">
      AI is <b>off</b> — the default. The sealed forecast above stands entirely on its own.
      Choose a local model or your own key from the selector to add an optional, cited reading.
    </p>
  );
}

function IdleCard({ provider, onRun }: { provider: AiProvider; onRun: () => void }) {
  const meta = AI_PROVIDERS.find((p) => p.value === provider);
  return (
    <div className="stack" style={{ ["--gap" as string]: ".7rem" }}>
      <p className="ai-note">
        {meta?.kind === "cloud"
          ? "Uses your own API key (kept in your OS keychain, never logged). A short request is sent to your chosen provider."
          : "Uses a local model on your machine — no key, no cloud. Start Ollama or llama.cpp first."}
      </p>
      <div>
        <button type="button" className="ai-run" onClick={onRun}>Run AI Deep Read</button>
      </div>
    </div>
  );
}

function Pipeline() {
  const [step, setStep] = useState(0);
  useEffect(() => {
    const t = window.setInterval(() => setStep((s) => (s + 1) % PIPELINE_STAGES.length), 900);
    return () => window.clearInterval(t);
  }, []);
  return (
    <div className="ai-pipeline" role="status" aria-live="polite">
      <span className="visually-hidden">Preparing the AI deep read…</span>
      <ol>
        {PIPELINE_STAGES.map((label, i) => (
          <li key={label} className={i === step ? "on" : i < step ? "done" : ""} aria-hidden>
            <span className="ai-pipeline__dot" />{label}
          </li>
        ))}
      </ol>
    </div>
  );
}

function Result({ data, onRetry }: { data: NarrativeResponse; onRetry: () => void }) {
  if (data.status === "disabled") return <OffCard />;
  if (data.status === "unavailable") return <FallbackCard reason={data.reason} unavailable />;
  if (data.status === "local_only") return <FallbackCard reason={data.reason} onRetry={onRetry} />;
  if (data.status !== "ok" || !data.narration) return <FallbackCard reason={data.reason} onRetry={onRetry} />;

  const sourceById = new Map<string, SourceRef>(data.sources.map((s) => [s.source_id, s]));
  const numberById = new Map<string, NumberRef>(data.numbers.map((n) => [n.id, n]));
  const { claims, scenarios } = data.narration;

  return (
    <div className="stack" style={{ ["--gap" as string]: "1rem" }}>
      <div className="ai-verified">
        <CheckIcon size={15} />
        <span>Every number below was verified against the sealed forecast. It explains those
          numbers — it does not change them.</span>
      </div>

      {claims.length > 0 && (
        <ClaimList title="Reading" items={claims} sourceById={sourceById} numberById={numberById} />
      )}
      {scenarios.length > 0 && (
        <ClaimList title="Scenarios" items={scenarios} sourceById={sourceById} numberById={numberById} />
      )}
      {claims.length === 0 && scenarios.length === 0 && (
        <p className="ai-note">The model returned nothing it could ground in the evidence.</p>
      )}

      <p className="ai-meta">
        {data.cached && <span className="chip chip--neutral">cached</span>}
        <span className="dim">
          {data.provider} · {data.model} · prompt {data.prompt_version}
        </span>
        <button type="button" className="ai-refresh" onClick={onRetry}>Re-run</button>
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

function FallbackCard({
  reason, unavailable = false, onRetry,
}: { reason: string | null; unavailable?: boolean; onRetry?: () => void }) {
  return (
    <div className="callout callout--info ai-fallback">
      {unavailable ? <InfoIcon size={18} /> : <AlertIcon size={18} />}
      <div>
        <div className="callout__title">
          {unavailable ? "AI unavailable" : "Showing the local forecast only"}
        </div>
        {reason ??
          "AI output could not be verified against the sealed numbers, so it was discarded. " +
          "The forecast above is unaffected."}
        {onRetry && (
          <div style={{ marginTop: ".5rem" }}>
            <button type="button" className="ai-refresh" onClick={onRetry}>Try again</button>
          </div>
        )}
      </div>
    </div>
  );
}
