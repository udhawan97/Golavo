/**
 * The AI-at-work experience. Honest, informative, and a little special — icon
 * stages that light up as work advances, an elapsed ticker, and expectation copy
 * so a slow local model never reads as "hung".
 *
 * Loop 1 drives the stages on a client-side simulation (no server progress yet);
 * the stage set and detail line are structured so Loop 5 can feed REAL progress
 * without changing the markup. No fabricated per-source detail appears until a
 * real progress signal exists.
 */
import { useEffect, useState } from "react";
import type { ComponentType } from "react";
import { AI_PROVIDERS } from "../../lib/ai";
import type { AiDepth, AiProvider } from "../../lib/ai";
import {
  BundleIcon, ChecklistIcon, GlobeIcon, QuillIcon,
} from "../icons";

interface Stage {
  key: string;
  label: string;
  Icon: ComponentType<{ size?: number }>;
}

// The factual pipeline stages — what the app actually does. Deliberately NOT a
// depiction of the model's private reasoning. "Researching" only appears when a
// web-research run is happening (Loop 6); the base flow omits it.
const BASE_STAGES: Stage[] = [
  { key: "assembling", label: "Assembling the evidence", Icon: BundleIcon },
  { key: "writing", label: "The model is reading and writing", Icon: QuillIcon },
  { key: "verifying", label: "Verifying every number against the engine", Icon: ChecklistIcon },
];

const RESEARCH_STAGE: Stage = { key: "researching", label: "Researching the web", Icon: GlobeIcon };

export function Pipeline({
  provider, refresh, depth, research = false,
}: {
  provider: AiProvider;
  refresh: boolean;
  depth: AiDepth;
  /** Whether the run includes a web-research stage (opt-in; Loop 6). */
  research?: boolean;
}) {
  const stages = research ? [BASE_STAGES[0], RESEARCH_STAGE, ...BASE_STAGES.slice(1)] : BASE_STAGES;
  const [step, setStep] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const meta = AI_PROVIDERS.find((p) => p.value === provider);
  const isDeep = depth === "deep";
  useEffect(() => {
    // Advance and STOP at the last stage — never wrap back, which would un-check
    // completed steps and read as "restarting/stuck". The rail fill and elapsed
    // timer carry the sense of ongoing progress. Deep dwells longer per stage.
    const stage = window.setInterval(
      () => setStep((s) => Math.min(s + 1, stages.length - 1)),
      isDeep ? 12000 : 1600,
    );
    const tick = window.setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => { window.clearInterval(stage); window.clearInterval(tick); };
  }, [isDeep, stages.length]);

  const waitNote = isDeep
    ? "Deep analysis — a bigger model is connecting the evidence. This can take a few minutes; nothing shows until every number is verified."
    : elapsed < 8
      ? refresh
        ? "Regenerating — skipping the cached read."
        : "This runs once, then is cached."
      : meta?.kind === "local"
        ? "Local models think at their own pace — a minute is normal. Nothing shows until every number is verified."
        : "Still waiting on the provider. Nothing shows until every number is verified.";

  const activeLabel = stages[Math.min(step, stages.length - 1)]?.label ?? "";
  return (
    <div className="ai-pipeline" role="status">
      <span className="visually-hidden" aria-live="polite">{activeLabel}…</span>
      <ol className="ai-stages" aria-hidden>
        {stages.map((s, i) => {
          const cls = i < step ? "done" : i === step ? "on" : "";
          const { Icon } = s;
          return (
            <li key={s.key} className={`ai-stage ${cls}`}>
              <span className="ai-stage__icon"><Icon size={16} /></span>
              <span className="ai-stage__label">{s.label}</span>
            </li>
          );
        })}
      </ol>
      <p className="ai-progress__meta small dim" style={{ margin: 0 }}>
        <span className="num">{elapsed}s</span> · {waitNote}
      </p>
    </div>
  );
}
