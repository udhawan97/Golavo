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
import { useCallback, useState } from "react";

export type AiProvider = "off" | "ollama" | "llama_server" | "openai" | "anthropic";

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

export interface AiNarration {
  schema_version: string;
  claims: NarrationClaim[];
  scenarios: NarrationClaim[];
  candidate_facts: unknown[];
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

/** The chosen provider, persisted. Defaults to "off" — the whole app works
 *  identically with this untouched. */
export function useAiProvider(): [AiProvider, (p: AiProvider) => void] {
  const [provider, setProvider] = useState<AiProvider>(() => {
    try {
      const stored = localStorage.getItem(AI_KEY);
      if (stored && AI_PROVIDERS.some((p) => p.value === stored)) return stored as AiProvider;
    } catch { /* ignore */ }
    return "off";
  });
  const set = useCallback((p: AiProvider) => {
    setProvider(p);
    try { localStorage.setItem(AI_KEY, p); } catch { /* ignore */ }
  }, []);
  return [provider, set];
}
