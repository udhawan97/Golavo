import { useCallback, useEffect, useRef, useState } from "react";
import {
  cancelOllamaModelDownload,
  fetchLocalModelStatus,
  fetchOllamaDownloadJob,
  startOllamaModelDownload,
} from "../../lib/api";
import type {
  LocalProviderStatus,
  OllamaDownloadJob,
  RecommendedOllamaModel,
} from "../../lib/api";
import { useAiModels } from "../../lib/ai";
import { newJobId } from "../../lib/aiProgress";
import { formatBytes } from "../../lib/updater";
import { CheckIcon, DownloadIcon, LinkIcon } from "../icons";

export const LOCAL_MODELS_CHANGED_EVENT = "golavo-local-models-changed";

const FALLBACK_MODELS: RecommendedOllamaModel[] = [
  {
    name: "llama3.2:latest",
    role: "fast",
    label: "Fast read",
    description: "A lightweight local model for quick, grounded summaries.",
    download_size_bytes: 2_000_000_000,
    library_url: "https://ollama.com/library/llama3.2",
    installed: false,
  },
  {
    name: "gemma4:12b-it-qat",
    role: "deep",
    label: "Deep analysis",
    description: "A larger model for connected evidence and match scenarios.",
    download_size_bytes: 7_200_000_000,
    library_url: "https://ollama.com/library/gemma4",
    installed: false,
  },
];

type ActiveDownload = {
  jobId: string;
  model: string;
  role: "fast" | "deep";
};

function formatModelSize(bytes: number): string {
  // Catalog sizes are intentionally approximate decimal download sizes; show
  // them the same way a casual user sees disk capacity instead of 1907.3 MB.
  if (bytes >= 1_000_000_000) return `${(bytes / 1_000_000_000).toFixed(1)} GB`;
  return formatBytes(bytes);
}

export function OllamaModelGuide({
  compact = false,
  ollamaActive = true,
  onActivateOllama,
  onModelsChanged,
}: {
  compact?: boolean;
  ollamaActive?: boolean;
  onActivateOllama?: () => void;
  onModelsChanged?: () => void | Promise<unknown>;
}) {
  const { fastModel, deepModel, setFastModel, setDeepModel } = useAiModels();
  const [status, setStatus] = useState<LocalProviderStatus | null>(null);
  const [checking, setChecking] = useState(true);
  const [active, setActive] = useState<ActiveDownload | null>(null);
  const [progress, setProgress] = useState<OllamaDownloadJob | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const mounted = useRef(true);

  useEffect(() => {
    // React Strict Mode intentionally mounts, cleans up, then remounts effects
    // in development. Reset the flag on every mount so an async status check
    // is not discarded forever after that rehearsal cleanup.
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  const refresh = useCallback(async () => {
    setChecking(true);
    try {
      const next = await fetchLocalModelStatus("ollama");
      if (mounted.current) setStatus(next);
      return next;
    } finally {
      if (mounted.current) setChecking(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  useEffect(() => {
    if (!active) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const poll = async () => {
      try {
        const job = await fetchOllamaDownloadJob(active.jobId);
        if (stopped || !mounted.current) return;
        setProgress(job);
        if (job.state === "running") {
          timer = setTimeout(poll, 650);
          return;
        }
        if (job.state === "done") {
          // End the polling lifecycle before assignment events re-render the
          // parent and replace its refresh callback.
          setActive(null);
          onActivateOllama?.();
          if (active.role === "fast") setFastModel(active.model);
          else setDeepModel(active.model);
          setMessage(`${active.model} is installed and ready for ${active.role === "fast" ? "Fast" : "Deep"} analysis.`);
          const next = await refresh();
          window.dispatchEvent(new Event(LOCAL_MODELS_CHANGED_EVENT));
          await onModelsChanged?.();
          if (mounted.current) setStatus(next);
        } else if (job.state === "cancelled") {
          setMessage("Download cancelled. Ollama may reuse any completed layers next time.");
        } else {
          setMessage(job.error || "The model download failed. Check Ollama and try again.");
        }
        if (mounted.current) setActive(null);
      } catch (error) {
        if (!stopped && mounted.current) {
          setMessage(error instanceof Error ? error.message : "Download progress was lost.");
          setActive(null);
        }
      }
    };
    void poll();
    return () => {
      stopped = true;
      if (timer) clearTimeout(timer);
    };
  }, [active, onActivateOllama, onModelsChanged, refresh, setDeepModel, setFastModel]);

  const start = async (model: RecommendedOllamaModel) => {
    setMessage(null);
    setProgress(null);
    try {
      onActivateOllama?.();
      const jobId = newJobId("dl");
      await startOllamaModelDownload(model.name, jobId);
      setActive({ jobId, model: model.name, role: model.role });
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "The model download could not start.");
    }
  };

  const cancel = async () => {
    if (!active) return;
    try {
      await cancelOllamaModelDownload(active.jobId);
      setMessage("Cancelling download…");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "The download could not be cancelled.");
    }
  };

  const catalog = status?.recommended?.length ? status.recommended : FALLBACK_MODELS;
  const ollamaReady = status?.status === "ready" || status?.status === "no_models" || status?.status === "no_chat_models";
  const completed = progress?.counts.completed ?? 0;
  const total = progress?.counts.total ?? 0;
  const percent = total > 0 ? Math.min(100, Math.round((completed / total) * 100)) : null;

  const modelCards = (
    <div className="ollama-guide__models">
      {catalog.map((model) => {
        const assignedModel = model.role === "fast" ? fastModel === model.name : deepModel === model.name;
        const ready = ollamaActive && assignedModel;
        const downloading = active?.model === model.name;
        return (
          <article className={`ollama-model${model.installed ? " is-installed" : ""}`} key={model.name}>
            <div className="ollama-model__head">
              <span className={`ollama-model__role ollama-model__role--${model.role}`}>
                {model.label}
              </span>
              <span className="ollama-model__size">about {formatModelSize(model.download_size_bytes)}</span>
            </div>
            <strong>{model.name}</strong>
            <p>{model.description}</p>
            <div className="ollama-model__actions">
              {model.installed ? (
                <button
                  type="button"
                  className="btn btn--ghost"
                  disabled={ready || Boolean(active)}
                  onClick={() => {
                    onActivateOllama?.();
                    if (model.role === "fast") setFastModel(model.name);
                    else setDeepModel(model.name);
                    setMessage(`${model.name} will run ${model.label}.`);
                  }}
                >
                  <CheckIcon size={14} /> {ready ? "Ready" : `Use for ${model.role === "fast" ? "Fast" : "Deep"}`}
                </button>
              ) : (
                <button
                  type="button"
                  className="btn btn--primary"
                  disabled={!ollamaReady || Boolean(active)}
                  onClick={() => { void start(model); }}
                >
                  <DownloadIcon size={14} /> {downloading ? "Downloading…" : "Download model"}
                </button>
              )}
              <a href={model.library_url} target="_blank" rel="noreferrer">
                Model details <LinkIcon size={12} />
              </a>
            </div>
          </article>
        );
      })}
    </div>
  );

  const body = (
    <div className={`ollama-guide${compact ? " ollama-guide--compact" : ""}`}>
      {!compact && (
        <ol className="ollama-guide__steps">
          <li><span>1</span><div><b>Install Ollama</b><small>Download the official macOS app, move it to Applications, then open it once.</small></div></li>
          <li><span>2</span><div><b>Keep Ollama open</b><small>Golavo connects only to Ollama on this Mac. No API key or cloud account is needed.</small></div></li>
          <li><span>3</span><div><b>Choose a model</b><small>Start with Fast. Add Deep when you want richer analysis and have the extra disk space.</small></div></li>
        </ol>
      )}

      <div className="ollama-guide__status" role="status" aria-live="polite">
        <span className={`ai-local-line__dot${ollamaReady ? " is-ready" : ""}`} aria-hidden />
        <span>
          {checking
            ? "Checking Ollama…"
            : ollamaReady
              ? `Ollama is running. ${status?.models.length ?? 0} chat model${status?.models.length === 1 ? "" : "s"} installed.`
              : status?.reason || "Ollama is not reachable yet."}
        </span>
        <button type="button" className="link-btn" onClick={() => { void refresh(); }} disabled={checking}>
          Check again
        </button>
      </div>

      {!ollamaReady && (
        <div className="ollama-guide__install">
          <span>Already installed? Open Ollama from Applications, then choose <b>Check again</b>.</span>
          <a className="btn btn--primary" href={status?.download_url || "https://ollama.com/download/mac"} target="_blank" rel="noreferrer">
            <DownloadIcon size={15} /> Download Ollama
          </a>
          <a href={status?.guide_url || "https://docs.ollama.com/macos"} target="_blank" rel="noreferrer">
            macOS setup help <LinkIcon size={12} />
          </a>
        </div>
      )}

      {modelCards}

      {active && progress && (
        <div className="ollama-download" aria-live="polite">
          <div className="ollama-download__label">
            <span>{progress.detail || `Downloading ${active.model}`}</span>
            <span>{percent === null ? "Preparing…" : `${percent}%`}</span>
          </div>
          <progress max={total || 1} value={total ? completed : undefined} />
          <div className="ollama-download__meta">
            <span>{total ? `${formatBytes(completed)} of ${formatBytes(total)}` : "Waiting for Ollama’s size estimate"}</span>
            <button type="button" className="btn btn--ghost" onClick={() => { void cancel(); }}>Cancel</button>
          </div>
        </div>
      )}

      {message && <p className="ollama-guide__message" role="status">{message}</p>}
      <p className="ollama-guide__privacy">
        Downloads start only when you click. Ollama fetches the model from its registry and stores it locally; Golavo never uploads your match data during installation.
      </p>
    </div>
  );

  if (!compact) return body;
  return (
    <details className="ollama-guide-disclosure">
      <summary><DownloadIcon size={14} /> Get or manage local models</summary>
      {body}
    </details>
  );
}
