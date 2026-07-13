/**
 * Optional AI layer — client types and settings.
 *
 * Honesty rules mirrored from the backend:
 *  - AI is OFF by default and additive. The forecast is complete without it.
 *  - The UI never fabricates a narration. In sample-data mode (no backend) the
 *    AI path is simply "unavailable"; it is never faked.
 *  - Every rendered number/citation comes from the backend envelope, which the
 *    gateway already validated against the sealed evidence bundle. The UI adds
 *    no number of its own.
 */
import { useCallback, useEffect, useState } from "react";

export type AiProvider = "off" | "ollama" | "llama_server" | "openai" | "anthropic";

/** Read depth. "fast" = a small model, quick claims (~seconds). "deep" = a bigger
 *  model, a fuller prompt and richer synthesis (minutes). */
export type AiDepth = "fast" | "deep";

// The server applies these budgets; the client sends a matching timeout hint so a
// slow deep read isn't abandoned early. Deep is up to 8 minutes.
export const FAST_TIMEOUT_S = 120;
export const DEEP_TIMEOUT_S = 480;

export const AI_PROVIDERS: { value: AiProvider; label: string; kind: "off" | "local" | "cloud" }[] = [
  { value: "off", label: "Off", kind: "off" },
  { value: "ollama", label: "Local · Ollama", kind: "local" },
  { value: "llama_server", label: "Local · llama.cpp", kind: "local" },
  { value: "openai", label: "OpenAI · BYOK", kind: "cloud" },
  { value: "anthropic", label: "Anthropic · BYOK", kind: "cloud" },
];

export type NarrationStatus = "ok" | "disabled" | "unavailable" | "local_only";

export interface NarrationClaim {
  text: string;
  source_ids: string[];
  number_refs: string[];
}

/** A note in the optional general-knowledge lane — no numbers, no citations. */
export interface BackgroundNote {
  text: string;
  about?: "home" | "away" | "match";
}

export interface AiNarration {
  schema_version: string;
  claims: NarrationClaim[];
  scenarios: NarrationClaim[];
  candidate_facts: unknown[];
  /** Optional: present only when the background lane was enabled (may be empty). */
  background?: BackgroundNote[];
}

export interface SourceRef {
  source_id: string;
  kind: "engine" | "snapshot";
  title: string;
  url: string;
}

export interface NumberRef {
  id: string;
  display: string;
  label: string;
  unit: string;
}

export interface NarrativeResponse {
  status: NarrationStatus;
  provider: string;
  model: string;
  prompt_version: string;
  bundle_hash: string;
  narration: AiNarration | null;
  cached: boolean;
  reason: string | null;
  notes: string[];
  sources: SourceRef[];
  numbers: NumberRef[];
}

// ---- Settings (persisted, OFF by default) -----------------------------------

const AI_KEY = "golavo-ai-provider";
const AI_LAST_KEY = "golavo-ai-last-provider";
// One event keeps every useAiProvider() instance in sync, so the header quick
// toggle, Settings, and the Deep Read panels always agree.
const AI_EVENT = "golavo-ai-provider-changed";

function readProvider(): AiProvider {
  try {
    const stored = localStorage.getItem(AI_KEY);
    if (stored && AI_PROVIDERS.some((p) => p.value === stored)) return stored as AiProvider;
  } catch { /* ignore */ }
  return "off";
}

/** The last non-off provider the user chose — what the quick toggle re-enables. */
export function lastAiProvider(): AiProvider | null {
  try {
    const stored = localStorage.getItem(AI_LAST_KEY);
    if (stored && stored !== "off" && AI_PROVIDERS.some((p) => p.value === stored))
      return stored as AiProvider;
  } catch { /* ignore */ }
  return null;
}

/** The chosen provider, persisted and app-wide reactive. Defaults to "off" —
 *  the whole app works identically with this untouched. Choosing a real
 *  provider also remembers it, so the quick toggle can re-enable it later. */
export function useAiProvider(): [AiProvider, (p: AiProvider) => void] {
  const [provider, setProvider] = useState<AiProvider>(readProvider);
  useEffect(() => {
    const sync = () => setProvider(readProvider());
    window.addEventListener(AI_EVENT, sync);
    window.addEventListener("storage", sync); // another tab/window
    return () => {
      window.removeEventListener(AI_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);
  const set = useCallback((p: AiProvider) => {
    setProvider(p);
    try {
      localStorage.setItem(AI_KEY, p);
      if (p !== "off") localStorage.setItem(AI_LAST_KEY, p);
    } catch { /* ignore */ }
    window.dispatchEvent(new Event(AI_EVENT));
  }, []);
  return [provider, set];
}

const AI_BG_KEY = "golavo-ai-background";
const AI_BG_EVENT = "golavo-ai-background-changed";

function readBackground(): boolean {
  try {
    return localStorage.getItem(AI_BG_KEY) === "1";
  } catch {
    return false;
  }
}

/** Whether the optional general-knowledge "background" lane is enabled. Off by
 *  default; persisted and app-wide reactive (Settings and the Deep Read panels
 *  stay in sync). Enabling it never weakens the grounded whitelist. */
export function useAiBackground(): [boolean, (on: boolean) => void] {
  const [on, setOn] = useState<boolean>(readBackground);
  useEffect(() => {
    const sync = () => setOn(readBackground());
    window.addEventListener(AI_BG_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(AI_BG_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);
  const set = useCallback((next: boolean) => {
    setOn(next);
    try {
      localStorage.setItem(AI_BG_KEY, next ? "1" : "0");
    } catch { /* ignore */ }
    window.dispatchEvent(new Event(AI_BG_EVENT));
  }, []);
  return [on, set];
}

// ---- Fast / Deep model assignment (persisted, app-wide reactive) ------------
// The user assigns which installed model runs each mode (Settings). Empty means
// "let the server auto-pick". Reads send the assigned model for the chosen depth.

const AI_FAST_MODEL_KEY = "golavo-ai-fast-model";
const AI_DEEP_MODEL_KEY = "golavo-ai-deep-model";
const AI_MODELS_EVENT = "golavo-ai-models-changed";

function readModel(key: string): string {
  try {
    return localStorage.getItem(key) || "";
  } catch {
    return "";
  }
}

export interface AiModelAssignment {
  fastModel: string;
  deepModel: string;
  setFastModel: (m: string) => void;
  setDeepModel: (m: string) => void;
}

/** The Fast and Deep model assignments, persisted and reactive across the app
 *  (Settings and every Deep Read panel stay in sync). */
export function useAiModels(): AiModelAssignment {
  const [fastModel, setFast] = useState(() => readModel(AI_FAST_MODEL_KEY));
  const [deepModel, setDeep] = useState(() => readModel(AI_DEEP_MODEL_KEY));
  useEffect(() => {
    const sync = () => {
      setFast(readModel(AI_FAST_MODEL_KEY));
      setDeep(readModel(AI_DEEP_MODEL_KEY));
    };
    window.addEventListener(AI_MODELS_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(AI_MODELS_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);
  const setFastModel = useCallback((m: string) => {
    setFast(m);
    try { localStorage.setItem(AI_FAST_MODEL_KEY, m); } catch { /* ignore */ }
    window.dispatchEvent(new Event(AI_MODELS_EVENT));
  }, []);
  const setDeepModel = useCallback((m: string) => {
    setDeep(m);
    try { localStorage.setItem(AI_DEEP_MODEL_KEY, m); } catch { /* ignore */ }
    window.dispatchEvent(new Event(AI_MODELS_EVENT));
  }, []);
  return { fastModel, deepModel, setFastModel, setDeepModel };
}
