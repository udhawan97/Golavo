/**
 * The AI-at-work experience. Honest, informative, and a little special — icon
 * stages that light up as work advances, an elapsed ticker, and expectation copy
 * so a slow local model never reads as "hung".
 *
 * When the sidecar reports real progress (usePolledProgress), the active stage
 * and the live detail line ("Reading: … — Wikipedia", "3/5") come from the
 * server. When it doesn't (an older sidecar, or before the first poll lands), the
 * stages advance on an honest client simulation with NO fabricated detail line.
 */
import { useEffect, useState } from "react";
import type { ComponentType } from "react";
import { AI_PROVIDERS } from "../../lib/ai";
import type { AiDepth, AiProvider } from "../../lib/ai";
import type { AiProgressStage, ProgressState } from "../../lib/aiProgress";
import { BundleIcon, ChecklistIcon, GlobeIcon, QuillIcon } from "../icons";

interface Stage {
  key: AiProgressStage;
  label: string;
  Icon: ComponentType<{ size?: number }>;
}

const BASE_STAGES: Stage[] = [
  { key: "assembling_evidence", label: "Assembling the evidence", Icon: BundleIcon },
  { key: "writing", label: "The model is reading and writing", Icon: QuillIcon },
  { key: "verifying", label: "Verifying every number against the engine", Icon: ChecklistIcon },
];

const RESEARCH_STAGE: Stage = {
  key: "researching", label: "Researching the web", Icon: GlobeIcon,
};

export function Pipeline({
  provider, refresh, depth, research = false, progress,
}: {
  provider: AiProvider;
  refresh: boolean;
  depth: AiDepth;
  research?: boolean;
  progress?: ProgressState;
}) {
  const stages = research
    ? [BASE_STAGES[0], RESEARCH_STAGE, ...BASE_STAGES.slice(1)]
    : BASE_STAGES;
  const live = progress?.kind === "live" ? progress.progress : null;

  const [simStep, setSimStep] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const meta = AI_PROVIDERS.find((p) => p.value === provider);
  const isDeep = depth === "deep";

  useEffect(() => {
    // The client simulation is only used as a fallback until/unless real progress
    // arrives; it still advances so an old sidecar shows motion.
    const stage = window.setInterval(
      () => setSimStep((s) => Math.min(s + 1, stages.length - 1)),
      isDeep ? 12000 : 1600,
    );
    const tick = window.setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => { window.clearInterval(stage); window.clearInterval(tick); };
  }, [isDeep, stages.length]);

  // The active stage index: real when we have a live sample, else simulated.
  const liveIdx = live ? stages.findIndex((s) => s.key === live.stage) : -1;
  const step = liveIdx >= 0 ? liveIdx : simStep;
  const elapsedS = live ? Math.floor(live.elapsed_s) : elapsed;

  const counts = live?.counts;
  const countLabel =
    counts && typeof counts.fetched === "number" && counts.planned
      ? `${counts.fetched}/${counts.planned}`
      : null;

  const waitNote = isDeep
    ? "Deep analysis — a bigger model is connecting the evidence. This can take a few minutes; nothing shows until every number is verified."
    : elapsedS < 8
      ? refresh
        ? "Regenerating — skipping the cached read."
        : "This runs once, then is cached."
      : meta?.kind === "local"
        ? "Local models think at their own pace — a minute is normal. Nothing shows until every number is verified."
        : "Still waiting on the provider. Nothing shows until every number is verified.";

  const activeLabel = stages[Math.min(step, stages.length - 1)]?.label ?? "";
  return (
    <div className="ai-pipeline" role="status">
      {/* Live region updates only on stage change (aria depends on activeLabel). */}
      <span className="visually-hidden" aria-live="polite">
        {activeLabel}{countLabel ? ` — ${countLabel}` : ""}
      </span>
      <ol className="ai-stages" aria-hidden>
        {stages.map((s, i) => {
          const cls = i < step ? "done" : i === step ? "on" : "";
          const { Icon } = s;
          const showCount = i === step && s.key === "researching" && countLabel;
          return (
            <li key={s.key} className={`ai-stage ${cls}`}>
              <span className="ai-stage__icon"><Icon size={16} /></span>
              <span className="ai-stage__label">
                {s.label}
                {showCount && <span className="ai-stage__count"> · {countLabel}</span>}
              </span>
            </li>
          );
        })}
      </ol>
      {/* A live detail line appears ONLY with real progress — never fabricated. */}
      {live?.detail && <p className="ai-stage__detail">{live.detail}</p>}
      <p className="ai-progress__meta small dim" style={{ margin: 0 }}>
        <span className="num">{elapsedS}s</span> · {waitNote}
      </p>
    </div>
  );
}
