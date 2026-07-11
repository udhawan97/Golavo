/**
 * Data access layer.
 *
 * Honesty rule: the UI never fabricates a backend. If VITE_GOLAVO_API is set at
 * build time, we GET the three documented read-only endpoints. Otherwise we load
 * the bundled mock fixtures and label the source as "mock" everywhere it matters.
 *
 * Documented endpoints (the ONLY ones assumed to exist):
 *   GET {base}/api/v1/forecasts          -> ForecastArtifact[]  (or {forecasts:[]})
 *   GET {base}/api/v1/forecasts/{id}      -> ForecastArtifact
 *   GET {base}/api/v1/eval/summary        -> EvalSummary
 *   GET {base}/api/v1/calibration         -> CalibrationSummary
 */
import { ACCEPTED_SCHEMA_VERSIONS } from "./contract";
import type {
  CalibrationSummary,
  EvalSummary,
  ForecastArtifact,
  NotebookResponse,
} from "./contract";
import type { AiProvider, NarrativeResponse } from "./ai";
import {
  loadMockCalibration,
  loadMockEval,
  loadMockForecast,
  loadMockForecasts,
  loadMockNotebook,
} from "../mocks";

/**
 * Backend selection, in priority order:
 *   1. window.__GOLAVO_RUNTIME__ — injected by the desktop shell at launch with
 *      the sidecar's ephemeral {apiBase, token}. Never hardcoded; the port and
 *      token change every launch.
 *   2. VITE_GOLAVO_API — a build-time base for source-mode dev against a local
 *      server started by hand.
 *   3. neither — bundled mock fixtures, labelled honestly as such.
 */
type RuntimeConfig = { apiBase?: string; token?: string };

const RUNTIME: RuntimeConfig =
  (globalThis as { __GOLAVO_RUNTIME__?: RuntimeConfig }).__GOLAVO_RUNTIME__ ?? {};

const RAW_BASE =
  RUNTIME.apiBase ?? (import.meta.env.VITE_GOLAVO_API as string | undefined);
const API_BASE = RAW_BASE ? RAW_BASE.replace(/\/+$/, "") : undefined;
const API_TOKEN = RUNTIME.token;
const IS_DESKTOP = typeof RUNTIME.apiBase === "string";

export type DataSource = "live" | "mock";
export const DATA_SOURCE: DataSource = API_BASE ? "live" : "mock";

/** A human-facing description of where the data came from — used honestly in UI. */
export function sourceDescription(): string {
  if (!API_BASE) return "Bundled sample artifacts (no backend connected)";
  return IS_DESKTOP ? `Live: bundled sidecar (${API_BASE})` : `Live: ${API_BASE}`;
}

export class ContractError extends Error {}

const HEX64 = /^[0-9a-f]{64}$/;

function assertVersion(v: unknown, ctx: string): void {
  if (!ACCEPTED_SCHEMA_VERSIONS.includes(v as (typeof ACCEPTED_SCHEMA_VERSIONS)[number]))
    throw new ContractError(
      `${ctx}: schema_version ${String(v ?? "missing")} not in [${ACCEPTED_SCHEMA_VERSIONS.join(", ")}]`,
    );
}

/** Minimal runtime guard so contract drift surfaces loudly instead of silently
 *  rendering malformed data. Not a full validator — the schema owner is Codex. */
function assertForecast(x: unknown, ctx: string): ForecastArtifact {
  const a = x as ForecastArtifact;
  if (!a || typeof a !== "object") throw new ContractError(`${ctx}: not an object`);
  assertVersion(a.schema_version, ctx);
  if (typeof a.artifact_id !== "string" || !a.artifact_id.startsWith("fa_"))
    throw new ContractError(`${ctx}: bad artifact_id`);
  if (!a.match || !a.forecast || !a.model || !a.inputs || !a.provenance)
    throw new ContractError(`${ctx}: missing top-level block`);
  if (!HEX64.test(a.provenance.payload_sha256))
    throw new ContractError(`${ctx}: payload_sha256 is not 64 hex`);
  const p = a.forecast.probs;
  if (p) {
    const sum = p.home + p.draw + p.away;
    if (Math.abs(sum - 1) > 0.001)
      throw new ContractError(`${ctx}: probs sum to ${sum.toFixed(4)} (expected 1 ± 0.001)`);
  }
  return a;
}

function assertEval(x: unknown, ctx: string): EvalSummary {
  const e = x as EvalSummary;
  if (!e || typeof e !== "object") throw new ContractError(`${ctx}: not an object`);
  assertVersion(e.schema_version, ctx);
  if (!Array.isArray(e.folds)) throw new ContractError(`${ctx}: folds is not an array`);
  return e;
}

function assertCalibration(x: unknown, ctx: string): CalibrationSummary {
  const c = x as CalibrationSummary;
  if (!c || typeof c !== "object") throw new ContractError(`${ctx}: not an object`);
  assertVersion(c.schema_version, ctx);
  if (!c.counts || typeof c.counts !== "object")
    throw new ContractError(`${ctx}: missing counts`);
  if (!Array.isArray(c.chains)) throw new ContractError(`${ctx}: chains is not an array`);
  for (const [i, chain] of c.chains.entries()) {
    const p = chain.probs;
    if (p) {
      const sum = p.home + p.draw + p.away;
      if (Math.abs(sum - 1) > 0.001)
        throw new ContractError(`${ctx}: chains[${i}] probs sum to ${sum.toFixed(4)}`);
    }
  }
  return c;
}

async function getJson(path: string): Promise<unknown> {
  const headers: Record<string, string> = { accept: "application/json" };
  // Every request to the sidecar carries the per-launch token when the shell
  // injected one; source-mode dev servers run open and simply omit it.
  if (API_TOKEN) headers["x-golavo-token"] = API_TOKEN;
  const res = await fetch(`${API_BASE}${path}`, { headers });
  if (!res.ok) throw new Error(`GET ${path} → HTTP ${res.status}`);
  return res.json();
}

export async function fetchForecasts(): Promise<ForecastArtifact[]> {
  if (!API_BASE) {
    // Validate mocks too — the contract guard is the point, not a live-only luxury.
    return (await loadMockForecasts()).map((a, i) => assertForecast(a, `mock forecasts[${i}]`));
  }
  const body = await getJson("/api/v1/forecasts");
  // Accept either a bare array or a { forecasts: [...] } envelope.
  const list = Array.isArray(body)
    ? body
    : Array.isArray((body as { forecasts?: unknown }).forecasts)
      ? (body as { forecasts: unknown[] }).forecasts
      : null;
  if (!list) throw new ContractError("forecasts: expected an array");
  const parsed = list.map((x, i) => assertForecast(x, `forecasts[${i}]`));
  return parsed.sort((a, b) =>
    b.forecast.sealed_at_utc.localeCompare(a.forecast.sealed_at_utc),
  );
}

export async function fetchForecast(id: string): Promise<ForecastArtifact | null> {
  if (!API_BASE) {
    const a = await loadMockForecast(id);
    return a ? assertForecast(a, `mock forecast ${id}`) : null;
  }
  try {
    const body = await getJson(`/api/v1/forecasts/${encodeURIComponent(id)}`);
    return assertForecast(body, `forecast ${id}`);
  } catch (err) {
    if (err instanceof Error && /HTTP 404/.test(err.message)) return null;
    throw err;
  }
}

/**
 * Fetch the read-only Commentator's Notebook for an artifact.
 *
 * Deterministic, source-backed facts precomputed by the engine — not a model
 * output, so (unlike the AI narration) it is shown from the bundled mocks in
 * sample-data mode. A 404 or a missing mock yields an honest unavailable
 * envelope rather than an error. This call can never change a probability.
 */
export async function fetchNotebook(id: string): Promise<NotebookResponse> {
  if (!API_BASE) return loadMockNotebook(id);
  try {
    return (await getJson(`/api/v1/forecasts/${encodeURIComponent(id)}/facts`)) as NotebookResponse;
  } catch (err) {
    if (err instanceof Error && /HTTP 404/.test(err.message))
      return { artifact_id: id, available: false, notebook: null };
    throw err;
  }
}

export async function fetchEvalSummary(): Promise<EvalSummary> {
  if (!API_BASE) return assertEval(await loadMockEval(), "eval/summary (mock)");
  return assertEval(await getJson("/api/v1/eval/summary"), "eval/summary");
}

export async function fetchCalibration(): Promise<CalibrationSummary> {
  if (!API_BASE) return assertCalibration(await loadMockCalibration(), "calibration (mock)");
  return assertCalibration(await getJson("/api/v1/calibration"), "calibration");
}

/**
 * Request an OPTIONAL AI narration for one artifact.
 *
 * With no backend (sample-data mode) or provider "off", this returns an honest
 * unavailable/disabled state WITHOUT contacting anything — the UI never fakes a
 * narration. In live mode it POSTs the provider config; the backend returns a
 * guard-validated narration or an explicit local-only fallback. This call can
 * never change or produce a probability.
 */
export async function fetchNarrative(id: string, provider: AiProvider): Promise<NarrativeResponse> {
  const base: NarrativeResponse = {
    status: "disabled",
    provider,
    model: "",
    prompt_version: "",
    bundle_hash: "",
    narration: null,
    cached: false,
    reason: null,
    notes: [],
    sources: [],
    numbers: [],
  };
  if (provider === "off") return base;
  if (!API_BASE) {
    return {
      ...base,
      status: "unavailable",
      reason:
        "AI Deep Read needs the local Golavo app connected to a model. It is not " +
        "available in this sample-data preview. The forecast above is complete without it.",
    };
  }
  const headers: Record<string, string> = {
    accept: "application/json",
    "content-type": "application/json",
  };
  if (API_TOKEN) headers["x-golavo-token"] = API_TOKEN;
  const res = await fetch(`${API_BASE}/api/v1/forecasts/${encodeURIComponent(id)}/narrative`, {
    method: "POST",
    headers,
    body: JSON.stringify({ provider }),
  });
  if (!res.ok) throw new Error(`AI narrative → HTTP ${res.status}`);
  return { ...base, ...(await res.json()) } as NarrativeResponse;
}
