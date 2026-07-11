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
import type { CalibrationSummary, EvalSummary, ForecastArtifact } from "./contract";
import {
  loadMockCalibration,
  loadMockEval,
  loadMockForecast,
  loadMockForecasts,
} from "../mocks";

const RAW_BASE = import.meta.env.VITE_GOLAVO_API as string | undefined;
const API_BASE = RAW_BASE ? RAW_BASE.replace(/\/+$/, "") : undefined;

export type DataSource = "live" | "mock";
export const DATA_SOURCE: DataSource = API_BASE ? "live" : "mock";

/** A human-facing description of where the data came from — used honestly in UI. */
export function sourceDescription(): string {
  return API_BASE
    ? `Live: ${API_BASE}`
    : "Bundled sample artifacts (no backend connected)";
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
  const res = await fetch(`${API_BASE}${path}`, { headers: { accept: "application/json" } });
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

export async function fetchEvalSummary(): Promise<EvalSummary> {
  if (!API_BASE) return assertEval(await loadMockEval(), "eval/summary (mock)");
  return assertEval(await getJson("/api/v1/eval/summary"), "eval/summary");
}

export async function fetchCalibration(): Promise<CalibrationSummary> {
  if (!API_BASE) return assertCalibration(await loadMockCalibration(), "calibration (mock)");
  return assertCalibration(await getJson("/api/v1/calibration"), "calibration");
}
