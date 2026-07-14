import { useCallback, useEffect, useRef, useState } from "react";
import {
  DATA_SOURCE,
  defaultModelAssignment,
  fetchLocalModelStatus,
  fetchMatchNarrative,
  fetchNarrative,
} from "../../lib/api";
import type { LocalModelInfo, LocalProviderStatus } from "../../lib/api";
import {
  AI_PROVIDERS,
  DEEP_TIMEOUT_S,
  FAST_TIMEOUT_S,
  useAiBackground,
  useAiModels,
  useAiProvider,
  useAiResearch,
} from "../../lib/ai";
import type { AiDepth, AiProvider, NarrativeResponse } from "../../lib/ai";
import { newJobId, usePolledProgress } from "../../lib/aiProgress";
import { ClockIcon, GlobeIcon, InfoIcon, SearchIcon } from "../icons";
import { Pipeline } from "./AiPipeline";
import { Result } from "./AiResult";
import type { AiDisplayContext } from "./AiResult";
import { FallbackCard, humanizeError, OffCard } from "./AiFallback";
import { OllamaModelGuide } from "./OllamaModelGuide";

/** A short size label for a model, e.g. "12B" or "" when unknown. */
function modelSize(m: LocalModelInfo): string {
  return m.parameter_size ? ` · ${m.parameter_size}` : "";
}

/** What the deep read runs over: a sealed forecast artifact, or a match's
 *  on-demand notes + council (the cockpit). Same guards either way. */
export type DeepReadSource =
  | { kind: "forecast"; artifactId: string }
  | { kind: "match"; matchId: string };

type RunState =
  | { status: "idle" }
  | { status: "loading"; refresh: boolean; jobId: string | null }
  | { status: "done"; data: NarrativeResponse }
  | { status: "error"; error: Error };

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

export function AiDeepRead({
  source,
  context,
}: {
  source: DeepReadSource;
  context?: AiDisplayContext;
}) {
  const [provider, setProvider] = useAiProvider();
  const [allowBackground, setAllowBackground] = useAiBackground();
  const [allowResearch, setAllowResearch] = useAiResearch();
  const { fastModel, deepModel, setFastModel, setDeepModel } = useAiModels();
  // Depth is per-panel (resets to Fast each session); the model assignments live
  // in Settings. `override` is the advanced "run this exact model" choice.
  const [depth, setDepth] = useState<AiDepth>("fast");
  const [override, setOverride] = useState<string>("");
  const [models, setModels] = useState<LocalModelInfo[]>([]);
  const [localStatus, setLocalStatus] = useState<LocalProviderStatus | null>(null);
  const [checkingLocal, setCheckingLocal] = useState(false);
  const [state, setState] = useState<RunState>({ status: "idle" });
  const runId = useRef(0);
  const skipInvalidate = useRef(false);
  const sourceKey = source.kind === "forecast" ? source.artifactId : source.matchId;
  const isLocal = provider === "ollama" || provider === "llama_server";

  // Load the installed local models, then SEED the Fast/Deep assignments if they
  // are unset or no longer installed — so Deep runs the bigger model even if the
  // user never opened Settings (Settings' picker does the same, idempotently).
  const refreshLocalStatus = useCallback(async (): Promise<LocalProviderStatus | null> => {
    if (!isLocal) {
      setLocalStatus(null);
      setModels([]);
      return null;
    }
    setCheckingLocal(true);
    try {
      const status = await fetchLocalModelStatus(provider);
      setLocalStatus(status);
      setModels(status.models);
      if (status.models.length > 0) {
        const names = new Set(status.models.map((x) => x.name));
        const def = defaultModelAssignment(status.models);
        if (!fastModel || !names.has(fastModel)) setFastModel(def.fast);
        if (!deepModel || !names.has(deepModel)) setDeepModel(def.deep);
      }
      return status;
    } finally {
      setCheckingLocal(false);
    }
  }, [deepModel, fastModel, isLocal, provider, setDeepModel, setFastModel]);

  useEffect(() => {
    let live = true;
    setOverride("");
    if (!isLocal) { setModels([]); setLocalStatus(null); return; }
    setCheckingLocal(true);
    fetchLocalModelStatus(provider).then((status) => {
      if (!live) return;
      setLocalStatus(status);
      setModels(status.models);
      if (status.models.length === 0) return;
      const names = new Set(status.models.map((x) => x.name));
      const def = defaultModelAssignment(status.models);
      if (!fastModel || !names.has(fastModel)) setFastModel(def.fast);
      if (!deepModel || !names.has(deepModel)) setDeepModel(def.deep);
    }).finally(() => {
      if (live) setCheckingLocal(false);
    });
    return () => { live = false; };
    // Re-seed only when the provider changes; the assignment setters are stable.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [provider, isLocal]);

  // A cloud provider has no depth/override UI; drop any leftover local choices so
  // a stale "deep"/override can't ride along to a cloud request.
  useEffect(() => {
    if (!isLocal) { setDepth("fast"); setOverride(""); }
  }, [isLocal]);

  // Changing the provider, depth, model override, research choice, or subject resets any prior
  // result so the panel never shows a narration attributed to the wrong run — but
  // a deliberate switch-and-run (below) opts out so its in-flight run survives.
  useEffect(() => {
    if (skipInvalidate.current) { skipInvalidate.current = false; return; }
    runId.current += 1;
    setState({ status: "idle" });
  }, [provider, sourceKey, depth, override, allowResearch]);

  const run = (refresh = false, depthArg: AiDepth = depth) => {
    void startRun(refresh, depthArg);
  };

  const startRun = async (refresh = false, depthArg: AiDepth = depth) => {
    if (isLocal && DATA_SOURCE !== "mock") {
      const status = await refreshLocalStatus();
      if (status && status.status !== "ready") {
        setState({ status: "idle" });
        return;
      }
    }
    const id = ++runId.current;
    const jobId = newJobId();
    setState({ status: "loading", refresh, jobId });
    // The model to run (local only): an explicit override wins, else the depth's
    // assigned model, else undefined (server auto-picks). A cloud provider never
    // sends a local model id. Deep gets the long budget.
    const model = isLocal
      ? override || (depthArg === "deep" ? deepModel : fastModel) || undefined
      : undefined;
    const opts = {
      refresh,
      allowBackground,
      allowResearch,
      depth: depthArg,
      model,
      timeoutS: depthArg === "deep" ? DEEP_TIMEOUT_S : FAST_TIMEOUT_S,
      jobId,
    };
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

  // "Switch to Fast" after a deep timeout: flip the mode AND immediately run a
  // fast read (one tap), surviving the depth-change invalidation.
  const switchToFast = () => {
    skipInvalidate.current = true;
    setDepth("fast");
    setOverride("");
    run(false, "fast");
  };

  const loadingJobId = state.status === "loading" ? state.jobId : null;
  const progress = usePolledProgress(loadingJobId, state.status === "loading");

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

      <div className="panel__body stack" style={{ ["--gap" as string]: "var(--space-4)" }}>
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

        {provider !== "off" && isLocal && (
          <DepthControls
            depth={depth}
            onDepth={setDepth}
            models={models}
            override={override}
            onOverride={setOverride}
            deepModel={deepModel}
            fastModel={fastModel}
            localStatus={localStatus}
            checkingLocal={checkingLocal}
            onRefreshLocal={refreshLocalStatus}
          />
        )}

        {provider === "ollama" && (
          <OllamaModelGuide compact onModelsChanged={refreshLocalStatus} />
        )}

        {provider !== "off" && (
          <label className={`ai-web-toggle${allowResearch ? " is-on" : ""}`}>
            <input
              type="checkbox"
              checked={allowResearch}
              disabled={state.status === "loading"}
              onChange={(e) => setAllowResearch(e.target.checked)}
            />
            <span className="ai-web-toggle__icon" aria-hidden><GlobeIcon size={16} /></span>
            <span className="ai-web-toggle__copy">
              <b>Search the web for this read</b>
              <small>
                Optional. Adds clearly labeled web findings; they never change the engine forecast.
              </small>
            </span>
          </label>
        )}

        {provider === "off" && <OffCard />}
        {provider !== "off" && state.status === "idle" && (
          <IdleCard
            provider={provider}
            isMatch={isMatch}
            depth={depth}
            onRun={() => run(false)}
            allowBackground={allowBackground}
            onToggleBackground={setAllowBackground}
            localStatus={localStatus}
            checkingLocal={checkingLocal}
            onRefreshLocal={refreshLocalStatus}
          />
        )}
        {state.status === "loading" && (
          <Pipeline
            provider={provider}
            refresh={state.refresh}
            depth={depth}
            research={allowResearch}
            progress={progress}
          />
        )}
        {state.status === "error" && (
          <ErrorCard error={state.error} onRetry={() => run(false)} />
        )}
        {state.status === "done" && (
          <Result
            data={state.data}
            isMatch={isMatch}
            depth={depth}
            context={context}
            onSwitchFast={depth === "deep" ? switchToFast : undefined}
            onRefresh={() => run(true)}
            onRetry={() => run(false)}
          />
        )}
      </div>
    </section>
  );
}

function ErrorCard({ error, onRetry }: { error: Error; onRetry: () => void }) {
  return <FallbackCard reason={humanizeError(error)} onRetry={onRetry} />;
}

/** The Fast / Deep segmented toggle plus a collapsed advanced model override.
 *  Deep runs a bigger model for a richer read; the assignments live in Settings. */
function DepthControls({
  depth, onDepth, models, override, onOverride, deepModel, fastModel,
  localStatus, checkingLocal, onRefreshLocal,
}: {
  depth: AiDepth;
  onDepth: (d: AiDepth) => void;
  models: LocalModelInfo[];
  override: string;
  onOverride: (m: string) => void;
  deepModel: string;
  fastModel: string;
  localStatus: LocalProviderStatus | null;
  checkingLocal: boolean;
  onRefreshLocal: () => Promise<LocalProviderStatus | null>;
}) {
  const [modelPickerOpen, setModelPickerOpen] = useState(false);
  const active = override || (depth === "deep" ? deepModel : fastModel);
  const installed = models.length === 0 || models.some((m) => m.name === active);
  // Only promise "a bigger model" when Deep really resolves to a different model
  // than Fast; with one model installed both are the same, so describe what
  // actually changes (a fuller prompt) instead of overclaiming.
  const biggerModel = Boolean(deepModel) && deepModel !== fastModel;
  return (
    <div className="ai-depth stack" style={{ ["--gap" as string]: ".5rem" }}>
      <div className="ai-seg" role="group" aria-label="Analysis depth">
        <button
          type="button"
          className={depth === "fast" ? "on" : ""}
          aria-pressed={depth === "fast"}
          onClick={() => onDepth("fast")}
        >
          <ClockIcon size={14} /> Fast
        </button>
        <button
          type="button"
          className={depth === "deep" ? "on" : ""}
          aria-pressed={depth === "deep"}
          onClick={() => onDepth("deep")}
        >
          <SearchIcon size={14} /> Deep analysis
        </button>
      </div>
      <p className="small dim" style={{ margin: 0 }}>
        {depth === "deep"
          ? biggerModel
            ? "A bigger model sees more of the evidence and writes scenarios. Deep analysis usually takes 5–8 minutes."
            : "A fuller prompt connects more evidence and writes scenarios. Deep analysis usually takes 5–8 minutes."
          : "A quick read from a small model — grounded claims in seconds."}
      </p>
      <LocalStatusLine
        status={localStatus}
        checking={checkingLocal}
        onRefresh={onRefreshLocal}
      />
      {models.length > 0 && (
        <>
          <button
            type="button"
            className="ai-depth__adv-toggle small dim"
            aria-expanded={modelPickerOpen}
            onClick={() => setModelPickerOpen((open) => !open)}
          >
            {depth === "fast" ? <ClockIcon size={13} /> : <SearchIcon size={13} />}
            {depth === "fast" ? "Basic" : "Advanced"} · {active
              ? `model: ${active}${installed ? "" : " (not installed)"}`
              : "auto model"}
          </button>
          {modelPickerOpen && (
            <label className="ai-depth__adv small">
              <span className="dim">Run a specific model (this read only)</span>
              <select value={override} onChange={(e) => onOverride(e.target.value)}>
                <option value="">
                  Auto — {depth === "deep" ? "Deep" : "Fast"} model{active ? ` (${active})` : ""}
                </option>
                {models.map((m) => (
                  <option key={m.name} value={m.name}>{m.name}{modelSize(m)}</option>
                ))}
              </select>
            </label>
          )}
        </>
      )}
    </div>
  );
}

function IdleCard({
  provider, isMatch, depth, onRun, allowBackground, onToggleBackground,
  localStatus, checkingLocal, onRefreshLocal,
}: {
  provider: AiProvider;
  isMatch: boolean;
  depth: AiDepth;
  onRun: () => void;
  allowBackground: boolean;
  onToggleBackground: (on: boolean) => void;
  localStatus: LocalProviderStatus | null;
  checkingLocal: boolean;
  onRefreshLocal: () => Promise<LocalProviderStatus | null>;
}) {
  const meta = AI_PROVIDERS.find((p) => p.value === provider);
  const localBlocked =
    DATA_SOURCE !== "mock" && meta?.kind === "local" && localStatus?.status !== "ready";
  return (
    <div className="stack" style={{ ["--gap" as string]: ".7rem" }}>
      <p className="ai-note">
        {meta?.kind === "cloud"
          ? "Uses your own API key (kept in your OS keychain, never logged). A short request is sent to your chosen provider."
          : "Uses a local model on your machine — no key, no cloud. Start Ollama or llama.cpp first."}
      </p>
      {meta?.kind === "local" && localBlocked && (
        <LocalStatusCard
          status={localStatus}
          checking={checkingLocal}
          onRefresh={onRefreshLocal}
        />
      )}
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
        <button type="button" className="ai-run" onClick={onRun} disabled={localBlocked || checkingLocal}>
          {localBlocked
            ? "Local AI not ready"
            : depth === "deep"
              ? "Run deep analysis"
              : isMatch ? "Write the read" : "Run AI Deep Read"}
        </button>
      </div>
    </div>
  );
}

function localStatusCopy(status: LocalProviderStatus | null): { tone: "ok" | "warn"; title: string; body: string } {
  if (!status) {
    return {
      tone: "warn",
      title: "Checking local AI",
      body: "Golavo is checking whether your local model server is available.",
    };
  }
  if (status.status === "ready") {
    return {
      tone: "ok",
      title: "Local AI ready",
      body: `${status.models.length} usable model${status.models.length === 1 ? "" : "s"} available.`,
    };
  }
  if (status.status === "no_models") {
    return {
      tone: "warn",
      title: "Ollama is running, but no model is installed",
      body: status.reason || "Pull a chat model, then check again.",
    };
  }
  if (status.status === "no_chat_models") {
    return {
      tone: "warn",
      title: "No chat model available",
      body: status.reason || "Install a chat-capable model, then check again.",
    };
  }
  return {
    tone: "warn",
    title: status.provider === "ollama" ? "Ollama is not reachable" : "Local model server is not reachable",
    body: status.reason || "Start the local model server, then check again.",
  };
}

function LocalStatusLine({
  status, checking, onRefresh,
}: {
  status: LocalProviderStatus | null;
  checking: boolean;
  onRefresh: () => Promise<LocalProviderStatus | null>;
}) {
  const copy = localStatusCopy(status);
  return (
    <div className={`ai-local-line ai-local-line--${copy.tone}`}>
      <span className="ai-local-line__dot" aria-hidden />
      <span>{checking ? "Checking local AI…" : `${copy.title}. ${copy.body}`}</span>
      {copy.tone !== "ok" && (
        <button type="button" onClick={() => { void onRefresh(); }}>Check again</button>
      )}
    </div>
  );
}

function LocalStatusCard({
  status, checking, onRefresh,
}: {
  status: LocalProviderStatus | null;
  checking: boolean;
  onRefresh: () => Promise<LocalProviderStatus | null>;
}) {
  const copy = localStatusCopy(status);
  return (
    <div className={`ai-local-card ai-local-card--${copy.tone}`} role="status">
      <div>
        <b>{checking ? "Checking local AI…" : copy.title}</b>
        <span>{checking ? "Looking for Ollama or llama.cpp now." : copy.body}</span>
      </div>
      <button type="button" onClick={() => { void onRefresh(); }} disabled={checking}>
        {checking ? "Checking…" : "Check again"}
      </button>
    </div>
  );
}
