/**
 * Data access layer.
 *
 * Honesty rule: the UI never fabricates a backend. If VITE_GOLAVO_API is set at
 * build time, we use the documented local read/write API. Otherwise we load
 * the bundled mock fixtures and label the source as "mock" everywhere it matters.
 *
 * Core documented endpoints include:
 *   GET {base}/api/v1/forecasts          -> ForecastArtifact[]  (or {forecasts:[]})
 *   GET {base}/api/v1/forecasts/{id}      -> ForecastArtifact
 *   GET {base}/api/v1/eval/summary        -> EvalSummary
 *   GET {base}/api/v1/calibration         -> CalibrationSummary
 *   GET {base}/api/v1/analytics/competitions/{id} -> CompetitionAnalytics
 *   POST {base}/api/v1/forecasts/settle   -> SettlementReport
 */
import { ACCEPTED_SCHEMA_VERSIONS } from "./contract";
import type {
  CalibrationSummary,
  ConditionsSnapshot,
  CompetitionAnalytics,
  CompetitionsResponse,
  EvalSummary,
  FixturesCheckResponse,
  ForecastArtifact,
  CompetitionCount,
  MatchAnalysisResponse,
  MatchDetailResponse,
  MatchNotebookResponse,
  MatchRow,
  MatchSearchResponse,
  MatchWindow,
  MatchesWindowResponse,
  NotebookResponse,
  PickResponse,
  PicksListResponse,
  PicksSummary,
  RecentMatchesResponse,
  SealEligibility,
  SealResult,
  SettlementReport,
  SourceKind,
  WorldMap,
} from "./contract";
import type { AiDepth, AiProvider, NarrativeResponse } from "./ai";
import {
  loadMockCalibration,
  loadMockEval,
  loadMockForecast,
  loadMockForecasts,
  loadMockMatches,
  loadMockNarrative,
  loadMockNotebook,
} from "../mocks";
import {
  MockPickError,
  mockDeletePick,
  mockFetchPick,
  mockFetchPicks,
  mockFetchPicksSummary,
  mockSavePick,
} from "../mocks/picks";

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
export const API_BASE = RAW_BASE ? RAW_BASE.replace(/\/+$/, "") : undefined;
const API_TOKEN = RUNTIME.token;
const IS_DESKTOP = typeof RUNTIME.apiBase === "string";

export type DataSource = "live" | "mock";
export const DATA_SOURCE: DataSource = API_BASE ? "live" : "mock";

/** Whether the UI depends on a backend that may still be starting up. In mock
 *  mode there is nothing to wait for. */
export const HAS_BACKEND = !!API_BASE;

/** Cheap liveness probe against the sidecar/server `/health` — used by the
 *  startup splash to know when the (slow-to-extract) engine is actually up.
 *  Returns true immediately in mock mode. Never throws. */
export async function pingHealth(): Promise<boolean> {
  if (!API_BASE) return true;
  try {
    const headers: Record<string, string> = { accept: "application/json" };
    if (API_TOKEN) headers["x-golavo-token"] = API_TOKEN;
    // Abort a hung probe so a blocked/slow engine can't leave the poll pending
    // forever (a stalled /health is what strands the startup splash).
    const ctrl = new AbortController();
    const timeout = setTimeout(() => ctrl.abort(), 3000);
    try {
      const res = await fetch(`${API_BASE}/health`, { headers, signal: ctrl.signal });
      return res.ok;
    } finally {
      clearTimeout(timeout);
    }
  } catch {
    return false;
  }
}

/** The engine warm-up state reported by GET /api/v1/status. Drives the staged
 *  splash (real stages, not a fake curve) and the home warming card. */
export interface EngineStatus {
  index_ready: boolean;
  index_state: "cold" | "warming" | "ready" | "error";
  index_rows: number | null;
  warming_since: string | null;
}

/** Poll the engine's warm-up status.
 *
 *  Deliberately a DIRECT fetch (not routed through the 30s read-through cache in
 *  getJson) — a cached "warming" would strand the splash forever. Returns:
 *   - EngineStatus on success,
 *   - "unsupported" for a 404 (an older sidecar without the route — the caller
 *     then behaves exactly as it did before this feature: treat as ready),
 *   - null on any network failure/timeout (keep polling).
 *  Mock mode reports ready instantly. Never throws. */
export async function fetchEngineStatus(): Promise<EngineStatus | "unsupported" | null> {
  if (!API_BASE) {
    return { index_ready: true, index_state: "ready", index_rows: null, warming_since: null };
  }
  try {
    const headers: Record<string, string> = { accept: "application/json" };
    if (API_TOKEN) headers["x-golavo-token"] = API_TOKEN;
    const ctrl = new AbortController();
    const timeout = setTimeout(() => ctrl.abort(), 3000);
    try {
      const res = await fetch(`${API_BASE}/api/v1/status`, { headers, signal: ctrl.signal });
      if (res.status === 404) return "unsupported";
      if (!res.ok) return null;
      const body = (await res.json()) as Partial<EngineStatus>;
      return {
        index_ready: body.index_ready === true,
        index_state: body.index_state ?? "warming",
        index_rows: typeof body.index_rows === "number" ? body.index_rows : null,
        warming_since: body.warming_since ?? null,
      };
    } finally {
      clearTimeout(timeout);
    }
  } catch {
    return null;
  }
}

export type ForecastSource = "mock" | "sample" | "ledger";

/** Whether the forecast list is real user seals ("ledger") or bundled synthetic
 *  samples ("sample", a fresh install with an empty ledger), or the web-mock
 *  bundle ("mock"). Drives the honest data-source badge + first-run banner so
 *  synthetic samples are never passed off as live forecasts. Never throws;
 *  falls back to "ledger" if the meta route can't be read (avoids a false
 *  "sample" label). */
export async function fetchForecastSource(): Promise<ForecastSource> {
  if (!API_BASE) return "mock";
  try {
    const headers: Record<string, string> = { accept: "application/json" };
    if (API_TOKEN) headers["x-golavo-token"] = API_TOKEN;
    const res = await fetch(`${API_BASE}/api/v1/meta`, { headers });
    if (!res.ok) return "ledger";
    const body = (await res.json()) as { forecast_source?: string };
    return body.forecast_source === "sample" ? "sample" : "ledger";
  } catch {
    return "ledger";
  }
}

/** A human-facing description of where the data came from — used honestly in UI. */
export function sourceDescription(source?: ForecastSource): string {
  if (!API_BASE) return "Bundled sample artifacts (no backend connected)";
  if (source === "sample") return "Sample forecasts (your sealed forecasts will replace these)";
  return IS_DESKTOP ? `Live: bundled sidecar (${API_BASE})` : `Live: ${API_BASE}`;
}

export class ContractError extends Error {}

/** A live HTTP error that carries the status code so a view can react to a
 *  specific state — notably a 503 from the match index while it is still being
 *  built by the engine. The message stays recognizable for older `/HTTP \d+/`
 *  detection too. */
export class ApiError extends Error {
  readonly status: number;
  constructor(message: string, status: number) {
    super(`${message} (HTTP ${status})`);
    this.name = "ApiError";
    this.status = status;
  }
}

/** A typed failure from the seal write route: carries the machine `reason_code`
 *  the backend returns so the view can show honest, specific copy (a played
 *  fixture reads differently from a closed seal window). `status === 0` marks a
 *  client-side refusal that never hit the network (e.g. the sample-data preview,
 *  which has no engine to run). */
export class SealApiError extends Error {
  readonly status: number;
  readonly reasonCode: string;
  constructor(message: string, status: number, reasonCode: string) {
    super(message);
    this.name = "SealApiError";
    this.status = status;
    this.reasonCode = reasonCode;
  }
}

export class PickApiError extends Error {
  readonly status: number;
  readonly reasonCode: string;
  constructor(message: string, status: number, reasonCode: string) {
    super(message);
    this.name = "PickApiError";
    this.status = status;
    this.reasonCode = reasonCode;
  }
}

const HEX64 = /^[0-9a-f]{64}$/;

function assertVersion(v: unknown, ctx: string): void {
  if (!ACCEPTED_SCHEMA_VERSIONS.includes(v as (typeof ACCEPTED_SCHEMA_VERSIONS)[number]))
    throw new ContractError(
      `${ctx}: schema_version ${String(v ?? "missing")} not in [${ACCEPTED_SCHEMA_VERSIONS.join(", ")}]`,
    );
}

/** Minimal runtime guard so contract drift surfaces loudly instead of silently
 *  rendering malformed data. Not a full validator — the schema owner is Codex. */
/** A score grid must be exactly (max_goals+1)² — the heatmap and market
 *  re-buckets index it directly, so a short/ragged grid would throw mid-render.
 *  Surface any drift as a loud ContractError instead of a silent TypeError. */
function assertScoreMatrix(
  sm: { max_goals?: unknown; grid?: unknown } | null | undefined,
  ctx: string,
): void {
  if (!sm) return;
  const n = sm.max_goals;
  if (typeof n !== "number" || !Number.isInteger(n) || n < 0)
    throw new ContractError(`${ctx}: score_matrix.max_goals must be a non-negative integer`);
  if (!Array.isArray(sm.grid) || sm.grid.length !== n + 1)
    throw new ContractError(
      `${ctx}: score grid has ${(sm.grid as unknown[])?.length} rows (expected ${n + 1})`,
    );
  for (let i = 0; i < sm.grid.length; i++) {
    const row = sm.grid[i];
    if (!Array.isArray(row) || row.length !== n + 1)
      throw new ContractError(
        `${ctx}: score grid row ${i} has ${(row as unknown[])?.length} cols (expected ${n + 1})`,
      );
  }
}

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
  assertScoreMatrix(a.forecast.score_matrix, ctx);
  return a;
}

function assertEval(x: unknown, ctx: string): EvalSummary {
  const e = x as EvalSummary;
  if (!e || typeof e !== "object") throw new ContractError(`${ctx}: not an object`);
  assertVersion(e.schema_version, ctx);
  if (!Array.isArray(e.folds)) throw new ContractError(`${ctx}: folds is not an array`);
  return e;
}

function assertCompetitionAnalytics(x: unknown, ctx: string): CompetitionAnalytics {
  const data = x as CompetitionAnalytics;
  if (!data || typeof data !== "object") throw new ContractError(`${ctx}: not an object`);
  if (typeof data.competition_id !== "string")
    throw new ContractError(`${ctx}: missing competition_id`);
  if (!Array.isArray(data.strength_trends?.teams))
    throw new ContractError(`${ctx}: strength_trends.teams is not an array`);
  if (!Array.isArray(data.rest_congestion?.teams))
    throw new ContractError(`${ctx}: rest_congestion.teams is not an array`);
  if (!data.schedule_difficulty?.status)
    throw new ContractError(`${ctx}: missing schedule_difficulty state`);
  return data;
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

const SOURCE_KINDS = ["international", "club"] as const;

function isSourceKind(v: unknown): v is SourceKind {
  return SOURCE_KINDS.includes(v as SourceKind);
}

function assertNonNegNumber(v: unknown, ctx: string, field: string): void {
  if (typeof v !== "number" || !Number.isFinite(v) || v < 0)
    throw new ContractError(`${ctx}: ${field} must be a finite number ≥ 0`);
}

function assertMatchRow(x: unknown, ctx: string): MatchRow {
  const m = x as MatchRow;
  if (!m || typeof m !== "object") throw new ContractError(`${ctx}: not an object`);
  if (typeof m.match_id !== "string" || !m.match_id.startsWith("m_"))
    throw new ContractError(`${ctx}: match_id must start with "m_"`);
  if (!isSourceKind(m.source_kind))
    throw new ContractError(
      `${ctx}: source_kind ${String(m.source_kind)} not in [${SOURCE_KINDS.join(", ")}]`,
    );
  if (m.kickoff_precision !== undefined && m.kickoff_precision !== "exact" && m.kickoff_precision !== "day")
    throw new ContractError(`${ctx}: kickoff_precision must be exact or day`);
  const bothScores = m.home_score !== null && m.away_score !== null;
  if (m.is_complete !== bothScores)
    throw new ContractError(
      `${ctx}: is_complete=${m.is_complete} must equal (both scores present)=${bothScores}`,
    );
  if (!Array.isArray(m.forecasts)) throw new ContractError(`${ctx}: forecasts is not an array`);
  return m;
}

function assertMatchSearch(x: unknown, ctx: string): MatchSearchResponse {
  const r = x as MatchSearchResponse;
  if (!r || typeof r !== "object") throw new ContractError(`${ctx}: not an object`);
  assertVersion(r.schema_version, ctx);
  assertNonNegNumber(r.total, ctx, "total");
  assertNonNegNumber(r.limit, ctx, "limit");
  assertNonNegNumber(r.offset, ctx, "offset");
  if (!Array.isArray(r.matches)) throw new ContractError(`${ctx}: matches is not an array`);
  r.matches.forEach((m, i) => assertMatchRow(m, `${ctx}.matches[${i}]`));
  return r;
}

function assertMatchDetail(x: unknown, ctx: string): MatchDetailResponse {
  const r = x as MatchDetailResponse;
  if (!r || typeof r !== "object") throw new ContractError(`${ctx}: not an object`);
  assertVersion(r.schema_version, ctx);
  assertMatchRow(r.match, `${ctx}.match`);
  return r;
}

function assertCompetitions(x: unknown, ctx: string): CompetitionsResponse {
  const r = x as CompetitionsResponse;
  if (!r || typeof r !== "object") throw new ContractError(`${ctx}: not an object`);
  assertVersion(r.schema_version, ctx);
  if (!Array.isArray(r.competitions))
    throw new ContractError(`${ctx}: competitions is not an array`);
  r.competitions.forEach((c, i) => {
    if (!isSourceKind(c.source_kind))
      throw new ContractError(`${ctx}: competitions[${i}].source_kind invalid`);
    assertNonNegNumber(c.n_matches, ctx, `competitions[${i}].n_matches`);
  });
  return r;
}

function assertMatchNotebook(x: unknown, ctx: string): MatchNotebookResponse {
  const r = x as MatchNotebookResponse;
  if (!r || typeof r !== "object") throw new ContractError(`${ctx}: not an object`);
  if (typeof r.available !== "boolean")
    throw new ContractError(`${ctx}: available is not a boolean`);
  if (r.available && !r.notebook)
    throw new ContractError(`${ctx}: available but notebook is missing`);
  return r;
}

/** Read-only request headers. Every request to the sidecar carries the
 *  per-launch token when the shell injected one; source-mode dev servers run
 *  open and simply omit it. */
export function apiHeaders(): Record<string, string> {
  const headers: Record<string, string> = { accept: "application/json" };
  if (API_TOKEN) headers["x-golavo-token"] = API_TOKEN;
  return headers;
}

/** Small read-through cache for idempotent GETs: coalesces concurrent identical
 *  requests and serves a recent result, so back-navigation and the two
 *  notebook/insight readers on one page don't each re-hit the network. Short
 *  TTL — this is a courtesy, not a source of truth. Bypassed for search and
 *  fixtures/check (which don't route through here), and cleared on any mutation
 *  via `clearApiCache()`. */
const GET_TTL_MS = 30_000;
const GET_CACHE_MAX = 60;
const getCache = new Map<string, { at: number; value: unknown }>();
const getInflight = new Map<string, Promise<unknown>>();

/** Drop all cached GETs — call after a write so stale reads can't survive it. */
export function clearApiCache(): void {
  getCache.clear();
  getInflight.clear();
}

async function getJson(path: string): Promise<unknown> {
  const hit = getCache.get(path);
  if (hit && performance.now() - hit.at < GET_TTL_MS) return hit.value;
  const inflight = getInflight.get(path);
  if (inflight) return inflight;

  const request = (async () => {
    const res = await fetch(`${API_BASE}${path}`, { headers: apiHeaders() });
    if (!res.ok) throw new Error(`GET ${path} → HTTP ${res.status}`);
    return res.json();
  })();
  getInflight.set(path, request);
  try {
    const value = await request;
    if (getCache.size >= GET_CACHE_MAX) getCache.clear(); // crude LRU: bounded memory
    getCache.set(path, { at: performance.now(), value });
    return value;
  } finally {
    getInflight.delete(path);
  }
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

export async function fetchCompetitionAnalytics(
  competitionId: string,
  asOfUtc?: string,
): Promise<CompetitionAnalytics> {
  if (!API_BASE) {
    return {
      schema_version: "0.1.0",
      competition_id: competitionId,
      competition_name: competitionId,
      as_of_utc: asOfUtc ?? new Date().toISOString(),
      scope: {
        team_category: "club",
        strength_comparison: "this_competition_only",
        model_input: false,
      },
      provenance: { source_ids: [] },
      strength_trends: {
        status: "unavailable",
        reason: "Connect the Golavo engine to calculate strengths from the local index.",
        method: "time-decayed-poisson-rates-v1",
        minimum_matches: 8,
        teams: [],
      },
      rest_congestion: {
        status: "unavailable",
        reason: "Connect the Golavo engine to calculate workload from the local index.",
        method: "indexed-match-counts-v1",
        coverage_note: "Counts include only competitions present in Golavo's local index.",
        teams: [],
      },
      schedule_difficulty: {
        status: "blocked",
        reason: "A complete remaining-fixture list is required.",
        required_capability: "complete_remaining_fixtures",
      },
    };
  }
  const query = asOfUtc ? `?as_of_utc=${encodeURIComponent(asOfUtc)}` : "";
  return assertCompetitionAnalytics(
    await getJson(`/api/v1/analytics/competitions/${encodeURIComponent(competitionId)}${query}`),
    `analytics/competitions/${competitionId}`,
  );
}

export async function fetchCalibration(): Promise<CalibrationSummary> {
  if (!API_BASE) return assertCalibration(await loadMockCalibration(), "calibration (mock)");
  return assertCalibration(await getJson("/api/v1/calibration"), "calibration");
}

/** User-authorized result refresh + immutable settlement of every eligible seal. */
export async function settleForecasts(): Promise<SettlementReport> {
  if (!API_BASE) throw new Error("Result settlement requires the connected Golavo app.");
  const res = await fetch(`${API_BASE}/api/v1/forecasts/settle`, {
    method: "POST",
    headers: apiHeaders(),
  });
  if (!res.ok) {
    let message = `result check failed (HTTP ${res.status})`;
    try {
      const body = (await res.json()) as { detail?: { message?: unknown } | string };
      if (typeof body.detail === "string") message = body.detail;
      if (body.detail && typeof body.detail === "object" && typeof body.detail.message === "string")
        message = body.detail.message;
    } catch { /* keep the status-based fallback */ }
    throw new Error(message);
  }
  const body = (await res.json()) as Partial<SettlementReport>;
  assertVersion(body.schema_version, "forecast settlement");
  if (
    typeof body.checked_at_utc !== "string"
    || typeof body.pending_before_check !== "number"
    || typeof body.eligible !== "number"
    || !Array.isArray(body.deferred_in_progress)
    || !Array.isArray(body.sources_checked)
    || !Array.isArray(body.scored)
    || !Array.isArray(body.still_pending)
    || !Array.isArray(body.errors)
  ) throw new ContractError("forecast settlement: malformed report");
  clearApiCache();
  return body as SettlementReport;
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
export interface NarrativeOptions {
  /** Skip the server cache read and regenerate (the user's "Refresh" action).
   *  The regenerated output still runs the full fail-closed guard pipeline. */
  refresh?: boolean;
  /** Opt into the second, general-knowledge "background" lane (off by default).
   *  It never weakens the grounded whitelist; any number it writes is deleted. */
  allowBackground?: boolean;
  /** "fast" (small model, quick claims) or "deep" (bigger model, richer read,
   *  minutes). Chooses the timeout the server applies and the prompt depth. */
  depth?: AiDepth;
  /** Explicit local model to run (overrides the server's auto-pick). */
  model?: string;
  /** Client timeout hint the server clamps; deep reads get a long budget. */
  timeoutS?: number;
  /** Opt into the web-research lane (Wikipedia + web search). The ONLY flag that
   *  lets the read reach the general web; off by default. */
  allowResearch?: boolean;
  /** Client-generated progress-tracking id; enables the live pipeline. */
  jobId?: string;
}

/** A local model the server reports as installed (with size, when known). */
export interface LocalModelInfo {
  name: string;
  parameter_size: string | null;
  params_b: number | null;
  size_bytes: number | null;
}

export interface RecommendedOllamaModel {
  name: string;
  role: "fast" | "deep";
  label: string;
  description: string;
  download_size_bytes: number;
  library_url: string;
  installed: boolean;
}

export type LocalModelStatus =
  | "unsupported"
  | "unreachable"
  | "no_models"
  | "no_chat_models"
  | "ready";

export interface LocalProviderStatus {
  provider: AiProvider;
  status: LocalModelStatus;
  models: LocalModelInfo[];
  reason: string | null;
  recommended?: RecommendedOllamaModel[];
  download_url?: string;
  guide_url?: string;
}

/** Default Fast/Deep assignment from installed models (server lists smallest
 *  first): Fast = smallest, Deep = largest. With one model, both use it. */
export function defaultModelAssignment(models: LocalModelInfo[]): { fast: string; deep: string } {
  if (models.length === 0) return { fast: "", deep: "" };
  return { fast: models[0].name, deep: models[models.length - 1].name };
}

/** Reachability + installed local chat models, for local AI status UI. */
export async function fetchLocalModelStatus(provider: AiProvider): Promise<LocalProviderStatus> {
  const empty = (status: LocalModelStatus, reason: string | null): LocalProviderStatus => ({
    provider,
    status,
    models: [],
    reason,
  });
  if (!API_BASE || (provider !== "ollama" && provider !== "llama_server"))
    return empty("unsupported", "Local model discovery is unavailable in this build.");
  const headers: Record<string, string> = { accept: "application/json" };
  if (API_TOKEN) headers["x-golavo-token"] = API_TOKEN;
  try {
    const res = await fetch(
      `${API_BASE}/api/v1/ai/local-models?provider=${encodeURIComponent(provider)}`,
      { headers },
    );
    if (!res.ok) return empty("unreachable", "The local model server could not be checked.");
    const body = (await res.json()) as Partial<LocalProviderStatus>;
    const models = Array.isArray(body.models) ? body.models : [];
    const status = body.status ?? (models.length > 0 ? "ready" : "unreachable");
    return {
      provider,
      status,
      models,
      reason: typeof body.reason === "string" ? body.reason : null,
      recommended: Array.isArray(body.recommended) ? body.recommended : undefined,
      download_url: typeof body.download_url === "string" ? body.download_url : undefined,
      guide_url: typeof body.guide_url === "string" ? body.guide_url : undefined,
    };
  } catch {
    return empty("unreachable", "The local model server could not be reached.");
  }
}

/** List the local models installed on a provider (with sizes), for the model
 *  picker. Empty in sample mode or when the local server is unreachable. */
export async function fetchLocalModels(provider: AiProvider): Promise<LocalModelInfo[]> {
  return (await fetchLocalModelStatus(provider)).models;
}

export interface OllamaDownloadJob {
  job_id: string;
  state: "running" | "done" | "failed" | "cancelled";
  stage: string;
  detail: string | null;
  counts: { completed?: number | null; total?: number | null };
  elapsed_s: number;
  result?: { model: string; status: "installed"; models?: LocalModelInfo[] };
  error?: string;
}

/** Start an explicit, curated model download through the local sidecar. */
export async function startOllamaModelDownload(model: string, jobId: string): Promise<string> {
  if (!API_BASE) throw new Error("Model downloads require the Golavo desktop app.");
  const res = await fetch(`${API_BASE}/api/v1/ai/ollama/downloads`, {
    method: "POST",
    headers: { ...apiHeaders(), "content-type": "application/json" },
    body: JSON.stringify({ model, job_id: jobId }),
  });
  if (!res.ok) {
    let detail = "The model download could not start.";
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
    } catch { /* keep the safe fallback */ }
    throw new Error(detail);
  }
  const body = (await res.json()) as { job_id?: string };
  if (!body.job_id) throw new Error("The model download started without a progress id.");
  return body.job_id;
}

export async function fetchOllamaDownloadJob(jobId: string): Promise<OllamaDownloadJob> {
  if (!API_BASE) throw new Error("Model downloads require the Golavo desktop app.");
  const res = await fetch(`${API_BASE}/api/v1/ai/jobs/${encodeURIComponent(jobId)}`, {
    headers: apiHeaders(),
  });
  if (!res.ok) throw new Error("The model download progress could not be read.");
  return (await res.json()) as OllamaDownloadJob;
}

export async function cancelOllamaModelDownload(jobId: string): Promise<void> {
  if (!API_BASE) return;
  const res = await fetch(`${API_BASE}/api/v1/ai/jobs/${encodeURIComponent(jobId)}/cancel`, {
    method: "POST",
    headers: apiHeaders(),
  });
  if (!res.ok) throw new Error("The model download could not be cancelled.");
}

function emptyNarrative(provider: AiProvider): NarrativeResponse {
  return {
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
}

const MOCK_AI_REASON =
  "AI Deep Read needs the local Golavo app connected to a model. It is not " +
  "available in this sample-data preview. The analysis above is complete without it.";

/** In mock mode only, and only when a test explicitly sets the golavo-ai-fixture
 *  flag, return a bundled sample narrative so the redesigned read is visually
 *  testable. Absent the flag (the default) this returns null and the caller
 *  falls back to the honest "unavailable" envelope — never a fabricated read. */
async function mockNarrative(
  subjectId: string,
  base: NarrativeResponse,
): Promise<NarrativeResponse | null> {
  let flag: string | null = null;
  try { flag = localStorage.getItem("golavo-ai-fixture"); } catch { /* ignore */ }
  if (!flag) return null;
  const fixture = await loadMockNarrative(subjectId);
  if (!fixture || typeof fixture !== "object") return null;
  return { ...base, ...(fixture as Partial<NarrativeResponse>) };
}

async function postNarrative(
  path: string,
  provider: AiProvider,
  opts: NarrativeOptions,
  subjectId: string,
): Promise<NarrativeResponse> {
  const base = emptyNarrative(provider);
  if (provider === "off") return base;
  if (!API_BASE) {
    const fixture = await mockNarrative(subjectId, base);
    if (fixture) return { ...fixture, status: fixture.status || "ok" };
    return { ...base, status: "unavailable", reason: MOCK_AI_REASON };
  }
  const headers: Record<string, string> = {
    accept: "application/json",
    "content-type": "application/json",
  };
  if (API_TOKEN) headers["x-golavo-token"] = API_TOKEN;
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      provider,
      ...(opts.refresh ? { refresh: true } : {}),
      ...(opts.allowBackground ? { allow_background: true } : {}),
      ...(opts.allowResearch ? { allow_research: true } : {}),
      ...(opts.depth ? { depth: opts.depth } : {}),
      ...(opts.model ? { model: opts.model } : {}),
      ...(opts.timeoutS ? { timeout_s: opts.timeoutS } : {}),
      // A tracked read runs as a server-side job. The start request returns
      // immediately; short polls collect the final result after Gemma finishes,
      // avoiding the WebView's much shorter long-request lifetime.
      ...(opts.jobId ? { job_id: opts.jobId, async_job: true } : {}),
    }),
  });
  if (res.status === 202) {
    const accepted = (await res.json()) as { job_id?: string };
    if (!accepted.job_id) throw new Error("AI job was accepted without an id");
    return waitForNarrativeResult(accepted.job_id, base);
  }
  if (!res.ok) {
    let detail = "";
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = `: ${body.detail}`;
      else if (body.detail && typeof body.detail === "object") {
        const message = (body.detail as { message?: unknown }).message;
        if (typeof message === "string") detail = `: ${message}`;
      }
    } catch { /* ignore */ }
    throw new Error(`AI narrative → HTTP ${res.status}${detail}`);
  }
  return { ...base, ...(await res.json()) } as NarrativeResponse;
}

/** Collect a slow local-model result through short requests. The model's own
 *  deep budget is 8 minutes; the wider collection deadline leaves room for
 *  evidence assembly/research and transient polling failures without creating
 *  another 300-second cutoff in the UI. */
export function narrativeJobWasLost(seenJob: boolean, consecutiveMissing: number): boolean {
  // A job that was visible and then disappears was lost with a sidecar restart.
  // Before the first successful poll, tolerate two 404s for an unusually slow
  // hand-off — the third is no longer a transient race.
  return seenJob || consecutiveMissing >= 3;
}

async function waitForNarrativeResult(
  jobId: string,
  base: NarrativeResponse,
): Promise<NarrativeResponse> {
  const deadline = Date.now() + 12 * 60 * 1000;
  const url = `${API_BASE}/api/v1/ai/jobs/${encodeURIComponent(jobId)}`;
  let seenJob = false;
  let consecutiveMissing = 0;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(url, { headers: apiHeaders() });
      if (res.status === 401) throw new Error("AI result could not be authorized");
      if (res.status === 404) {
        consecutiveMissing += 1;
        if (narrativeJobWasLost(seenJob, consecutiveMissing))
          throw new Error(
            "AI_JOB_TERMINAL:Deep analysis stopped because the local engine restarted. Try again.",
          );
      }
      if (res.ok) {
        seenJob = true;
        consecutiveMissing = 0;
        const job = (await res.json()) as {
          state?: "running" | "done" | "failed" | "cancelled";
          result?: Partial<NarrativeResponse>;
          error?: string;
        };
        if (job.state === "done") {
          if (!job.result) throw new Error("AI job finished without a result");
          return { ...base, ...job.result } as NarrativeResponse;
        }
        if (job.state === "failed")
          throw new Error(`AI_JOB_TERMINAL:${job.error || "AI generation failed before a safe result was produced"}`);
        if (job.state === "cancelled") throw new Error("AI_JOB_TERMINAL:AI generation was cancelled");
      }
      // A transient 5xx or network blip must not discard a Gemma result that is
      // still being produced server-side. A persistent/late 404 is different:
      // the process-local job vanished, so waiting 12 minutes cannot recover it.
    } catch (error) {
      if (error instanceof Error) {
        if (error.message.startsWith("AI_JOB_TERMINAL:"))
          throw new Error(error.message.replace("AI_JOB_TERMINAL:", ""));
        if (/authorized|finished without/.test(error.message)) throw error;
      }
    }
    await new Promise((resolve) => setTimeout(resolve, 1200));
  }
  throw new Error("Deep analysis did not finish within 12 minutes");
}

export async function fetchNarrative(
  id: string,
  provider: AiProvider,
  opts: NarrativeOptions = {},
): Promise<NarrativeResponse> {
  return postNarrative(`/api/v1/forecasts/${encodeURIComponent(id)}/narrative`, provider, opts, id);
}

/**
 * The cockpit's AI deep read: an optional, guard-validated synthesis of one
 * match's Commentator's Notebook + model council. Same honesty rules as the
 * forecast narrative — off by default, never faked offline, every number
 * verified against the whitelist server-side.
 */
export async function fetchMatchNarrative(
  matchId: string,
  provider: AiProvider,
  opts: NarrativeOptions = {},
): Promise<NarrativeResponse> {
  return postNarrative(`/api/v1/matches/${encodeURIComponent(matchId)}/narrative`, provider, opts, matchId);
}

/**
 * Opt-in fixture freshness (see the "keep fixtures up to date" setting).
 *
 * Hits the ONE network-reaching route, `/fixtures/check`, which reports upcoming
 * games present upstream but not yet in this build's index. Best-effort: any
 * failure (offline, 503, no backend) yields `null`, so this convenience never
 * disrupts the app. Callers should invoke it ONLY when the user enabled the
 * setting — the app must not reach the network otherwise.
 */
export async function checkNewFixtures(): Promise<FixturesCheckResponse | null> {
  if (!API_BASE) return null;
  try {
    const res = await fetch(`${API_BASE}/api/v1/fixtures/check`, { headers: apiHeaders() });
    if (!res.ok) return null;
    return (await res.json()) as FixturesCheckResponse;
  } catch {
    return null;
  }
}

// ---- Match directory --------------------------------------------------------
// Read-only search / detail / competitions / notebook over the engine's match
// index. In mock mode the SAME rows the engine would emit are bundled, and the
// filtering below is DISPLAY filtering only — it selects and paginates rows, it
// never mints or alters a number. Both live and mock results pass the contract
// guards, so drift surfaces loudly instead of rendering malformed data.

const DEFAULT_SEARCH_LIMIT = 50;

/** NFKD → strip diacritics → casefold, so "São"/"sao" and "München"/"munchen"
 *  match. Shared by every mock-mode field comparison. */
function normalizeText(s: string): string {
  return s
    .normalize("NFKD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase();
}

export interface MatchSearchOptions {
  competition?: string;
  status?: "played" | "upcoming";
  limit?: number;
  offset?: number;
}

/**
 * Search the match index. Live mode hits `/api/v1/matches/search`; a 503 (the
 * index is still being built) is surfaced as an `ApiError` with `status === 503`
 * so the UI can show a "still warming up" state distinctly from a hard failure.
 * Mock mode filters/paginates the bundled rows client-side with the same
 * diacritic-insensitive substring match a server would use.
 */
export async function searchMatches(
  q: string,
  opts: MatchSearchOptions = {},
): Promise<MatchSearchResponse> {
  const limit = opts.limit ?? DEFAULT_SEARCH_LIMIT;
  const offset = opts.offset ?? 0;
  if (!API_BASE) {
    const { schema_version, matches } = await loadMockMatches();
    const nq = normalizeText(q.trim());
    let rows = matches.slice();
    if (opts.competition) rows = rows.filter((m) => m.competition === opts.competition);
    if (opts.status === "played") rows = rows.filter((m) => m.is_complete);
    else if (opts.status === "upcoming") {
      // Match the server: kickoff is a 00:00 UTC day proxy, so "upcoming" is
      // measured from the start of today — a fixture stays listed on its match day.
      const today = new Date();
      today.setUTCHours(0, 0, 0, 0);
      rows = rows.filter(
        (m) => !m.is_complete && new Date(m.kickoff_utc).getTime() >= today.getTime(),
      );
    }
    // Tokenize like the server: every whitespace-separated term must appear in one
    // of the team names or the competition, so "argentina switzerland" resolves.
    const tokens = nq.split(/\s+/).filter(Boolean);
    if (tokens.length)
      rows = rows.filter((m) => {
        const fields = [
          normalizeText(m.home_team),
          normalizeText(m.away_team),
          normalizeText(m.competition),
        ];
        return tokens.every((tok) => fields.some((f) => f.includes(tok)));
      });
    // Newest kickoff first, stable on match_id — deterministic paging.
    rows.sort(
      (a, b) =>
        b.kickoff_utc.localeCompare(a.kickoff_utc) || a.match_id.localeCompare(b.match_id),
    );
    const total = rows.length;
    const page = rows.slice(offset, offset + limit);
    return assertMatchSearch(
      { schema_version, query: q, total, limit, offset, matches: page },
      "matches/search (mock)",
    );
  }
  const params = new URLSearchParams({ q, limit: String(limit), offset: String(offset) });
  if (opts.competition) params.set("competition", opts.competition);
  if (opts.status) params.set("status", opts.status);
  const path = `/api/v1/matches/search?${params.toString()}`;
  const res = await fetch(`${API_BASE}${path}`, { headers: apiHeaders() });
  if (res.status === 503) throw new ApiError("match index unavailable", 503);
  if (!res.ok) throw new Error(`GET ${path} → HTTP ${res.status}`);
  return assertMatchSearch(await res.json(), "matches/search");
}

/** Mock-mode seal eligibility, mirroring the server's typed verdict so the
 *  Generate-forecast flow is exercised offline. Internationals with a future
 *  kickoff are eligible; everything else gets the reason code the server would. */
function mockSealEligibility(match: MatchRow): SealEligibility {
  const base = {
    family: "dixon_coles",
    existing_artifact_ids: match.forecasts.map((f) => f.artifact_id),
  };
  if (match.is_complete)
    return { ...base, eligible: false, reason_code: "fixture_complete",
      detail: "this fixture already has a result" };
  if (match.source_kind !== "international")
    return { ...base, eligible: false, reason_code: "unsupported_competition",
      detail: "forward seals currently cover men's senior international fixtures only" };
  if (new Date(match.kickoff_utc).getTime() <= Date.now())
    return { ...base, eligible: false, reason_code: "kickoff_passed",
      detail: "the seal window closes at kickoff (date-only source: 00:00 UTC on match day)" };
  return { ...base, eligible: true, reason_code: "eligible",
    detail: "a local forecast can be sealed for this fixture" };
}

/** One match by id. A 404 (or a missing mock row) yields null, mirroring
 *  fetchForecast. */
export async function fetchMatch(matchId: string): Promise<MatchDetailResponse | null> {
  if (!API_BASE) {
    const { schema_version, matches } = await loadMockMatches();
    const match = matches.find((m) => m.match_id === matchId);
    if (!match) return null;
    return assertMatchDetail(
      {
        schema_version,
        match,
        linked_by: match.forecasts.length > 0 ? "match_id" : null,
        seal_eligibility: mockSealEligibility(match),
      },
      `matches/${matchId} (mock)`,
    );
  }
  try {
    const body = await getJson(`/api/v1/matches/${encodeURIComponent(matchId)}`);
    return assertMatchDetail(body, `matches/${matchId}`);
  } catch (err) {
    if (err instanceof Error && /HTTP 404/.test(err.message)) return null;
    throw err;
  }
}

function assertConditionsSnapshot(x: unknown, ctx: string): ConditionsSnapshot {
  const value = x as ConditionsSnapshot;
  if (!value || typeof value !== "object") throw new ContractError(`${ctx}: not an object`);
  if (value.schema_version !== "0.1.0")
    throw new ContractError(`${ctx}: unsupported conditions schema`);
  if (value.label !== "Context, not a model input.")
    throw new ContractError(`${ctx}: missing context-only label`);
  if (!value.match || (value.match.kickoff_precision !== "exact" && value.match.kickoff_precision !== "day"))
    throw new ContractError(`${ctx}: invalid match precision`);
  if (!Array.isArray(value.teams) || value.teams.length !== 2)
    throw new ContractError(`${ctx}: teams must contain home and away`);
  if (!Array.isArray(value.travel_map?.routes) || value.travel_map.routes.length > 2)
    throw new ContractError(`${ctx}: invalid travel routes`);
  for (const team of value.teams) {
    if (team.rest.days !== null) assertNonNegNumber(team.rest.days, ctx, `${team.side}.rest.days`);
    if (team.travel.distance_km !== null)
      assertNonNegNumber(team.travel.distance_km, ctx, `${team.side}.travel.distance_km`);
  }
  return value;
}

/** Display-only location/rest/travel context. Mock mode returns null rather than
 * inventing geography that is absent from the bundled match fixtures. */
export async function fetchMatchConditions(matchId: string): Promise<ConditionsSnapshot | null> {
  if (!API_BASE) return null;
  try {
    return assertConditionsSnapshot(
      await getJson(`/api/v1/matches/${encodeURIComponent(matchId)}/conditions`),
      `matches/${matchId}/conditions`,
    );
  } catch (error) {
    if (error instanceof Error && /HTTP 404/.test(error.message)) return null;
    throw error;
  }
}

function assertWorldMap(x: unknown): WorldMap {
  const value = x as WorldMap;
  if (!value || value.type !== "FeatureCollection" || value.source_id !== "natural-earth")
    throw new ContractError("maps/world: invalid Natural Earth collection");
  if (!Array.isArray(value.features)) throw new ContractError("maps/world: features missing");
  return value;
}

export async function fetchWorldMap(): Promise<WorldMap | null> {
  if (!API_BASE) return null;
  return assertWorldMap(await getJson("/api/v1/maps/world"));
}

/**
 * Seal one deterministic forecast for a fixture (POST /matches/{id}/seal).
 *
 * Live mode runs the engine server-side and returns the created (or already
 * existing) artifact. A typed failure — an ineligible fixture, a missing pack —
 * is surfaced as a SealApiError carrying the backend `reason_code` so the view
 * explains it honestly. Sample-data (mock) mode has no engine, so it refuses with
 * a `preview_only` SealApiError rather than fabricating a forecast.
 */
export async function sealMatch(matchId: string, family?: string): Promise<SealResult> {
  if (!API_BASE) {
    throw new SealApiError(
      "Sealing runs in the connected Golavo app; this sample-data preview has no engine to run.",
      0,
      "preview_only",
    );
  }
  const headers: Record<string, string> = {
    accept: "application/json",
    "content-type": "application/json",
  };
  if (API_TOKEN) headers["x-golavo-token"] = API_TOKEN;
  const res = await fetch(`${API_BASE}/api/v1/matches/${encodeURIComponent(matchId)}/seal`, {
    method: "POST",
    headers,
    body: JSON.stringify(family ? { family } : {}),
  });
  if (!res.ok) {
    let reason = "seal_rejected";
    let message = `seal failed (HTTP ${res.status})`;
    try {
      const err = (await res.json()) as { detail?: { reason_code?: string; message?: string } };
      if (err.detail?.reason_code) reason = err.detail.reason_code;
      if (err.detail?.message) message = err.detail.message;
    } catch {
      /* keep the generic defaults */
    }
    throw new SealApiError(message, res.status, reason);
  }
  // Guard the success body like every other response: a drifted 2xx that isn't a
  // well-formed SealResult must fail loudly, not navigate to #/forecast/undefined.
  let result: SealResult;
  try {
    result = (await res.json()) as SealResult;
  } catch {
    throw new SealApiError("the seal response was not valid JSON", res.status, "seal_rejected");
  }
  if (typeof result.artifact_id !== "string" || !result.artifact_id.startsWith("fa_"))
    throw new SealApiError(
      "the seal succeeded but returned no usable artifact id",
      res.status,
      "seal_rejected",
    );
  // A new seal changes the forecast list, the match's eligibility, and the
  // calibration record — drop cached reads so nothing serves the pre-seal view.
  clearApiCache();
  return result;
}

/** The distinct (competition, source_kind) groups with match counts — drives the
 *  competition filter and grouping. Derived from the bundled rows in mock mode. */
export async function fetchCompetitions(): Promise<CompetitionsResponse> {
  if (!API_BASE) {
    const { schema_version, matches } = await loadMockMatches();
    const grouped = new Map<
      string,
      { competition: string; source_kind: SourceKind; n_matches: number }
    >();
    for (const m of matches) {
      const key = `${m.source_kind} ${m.competition}`;
      const entry =
        grouped.get(key) ?? { competition: m.competition, source_kind: m.source_kind, n_matches: 0 };
      entry.n_matches += 1;
      grouped.set(key, entry);
    }
    const competitions = [...grouped.values()].sort(
      (a, b) =>
        a.competition.localeCompare(b.competition) || a.source_kind.localeCompare(b.source_kind),
    );
    return assertCompetitions({ schema_version, competitions }, "matches/competitions (mock)");
  }
  return assertCompetitions(await getJson("/api/v1/matches/competitions"), "matches/competitions");
}

/**
 * The read-only Commentator's Notebook for a match (by match_id). Reuses the
 * same CommentatorsNotebook the forecast-facts endpoint serves. A 404 or a match
 * without a bundled notebook yields an honest unavailable envelope rather than
 * an error. Never carries or changes a probability.
 */
export async function fetchMatchNotebook(matchId: string): Promise<MatchNotebookResponse> {
  const unavailable: MatchNotebookResponse = {
    available: false,
    computed: null,
    as_of_horizon: null,
    notebook: null,
  };
  if (!API_BASE) {
    const { matches } = await loadMockMatches();
    const match = matches.find((m) => m.match_id === matchId);
    if (!match) return unavailable;
    // A match's notebook is keyed by the sealed forecast that produced it; reuse
    // the same bundled-notebook lookup the /facts mock uses.
    for (const link of match.forecasts) {
      const env = await loadMockNotebook(link.artifact_id);
      if (env.available && env.notebook)
        return assertMatchNotebook(
          {
            available: true,
            computed: "on_demand",
            as_of_horizon: link.horizon,
            notebook: env.notebook,
          },
          `matches/${matchId}/notebook (mock)`,
        );
    }
    const env = await loadMockNotebook(matchId);
    if (env.available && env.notebook)
      return assertMatchNotebook(
        {
          available: true,
          computed: "on_demand",
          as_of_horizon: "T-24h",
          notebook: env.notebook,
        },
        `matches/${matchId}/notebook (mock)`,
      );
    return unavailable;
  }
  try {
    return assertMatchNotebook(
      await getJson(`/api/v1/matches/${encodeURIComponent(matchId)}/notebook`),
      `matches/${matchId}/notebook`,
    );
  } catch (err) {
    if (err instanceof Error && /HTTP 404/.test(err.message)) return unavailable;
    throw err;
  }
}

// ---- Match Cockpit: on-demand analysis (contract 0.3.0) ---------------------

function assertMatchAnalysis(x: unknown, ctx: string): MatchAnalysisResponse {
  const r = x as MatchAnalysisResponse;
  if (!r || typeof r !== "object") throw new ContractError(`${ctx}: not an object`);
  if (typeof r.available !== "boolean")
    throw new ContractError(`${ctx}: available is not a boolean`);
  if (r.available) {
    const a = r.analysis;
    if (!a || typeof a !== "object") throw new ContractError(`${ctx}: available but no analysis`);
    if (a.analysis_kind !== "replay" && a.analysis_kind !== "preview")
      throw new ContractError(`${ctx}: bad analysis_kind ${String(a.analysis_kind)}`);
    if (!Array.isArray(a.models)) throw new ContractError(`${ctx}: models is not an array`);
    // Every model that reports probabilities must have them sum to 1 — the same
    // honesty guard the artifact path uses.
    for (const m of a.models) {
      if (m.probs) {
        const sum = m.probs.home + m.probs.draw + m.probs.away;
        if (Math.abs(sum - 1) > 0.001)
          throw new ContractError(`${ctx}: ${m.family} probs sum to ${sum.toFixed(4)}`);
      }
    }
    // 0.4.0 additions — optional so an older backend degrades gracefully.
    if (a.team_form) {
      for (const [team, entries] of Object.entries(a.team_form)) {
        if (!Array.isArray(entries) || entries.length > 5)
          throw new ContractError(`${ctx}: team_form[${team}] is not a ≤5 array`);
        for (const e of entries) {
          if (e.result !== "W" && e.result !== "D" && e.result !== "L")
            throw new ContractError(`${ctx}: team_form[${team}] bad result ${String(e.result)}`);
        }
      }
    }
    if (a.team_style) {
      const { min, max } = a.team_style.clip;
      for (const [team, s] of Object.entries(a.team_style.teams)) {
        if (s.attack < min || s.attack > max || s.defence < min || s.defence > max)
          throw new ContractError(`${ctx}: team_style[${team}] multiplier out of clip band`);
      }
    }
    assertScoreMatrix(a.score_matrix, ctx);
  }
  return r;
}

/**
 * On-demand multi-model analysis for one match (Replay for a played fixture,
 * Preview for a scheduled one). Leak-safe and never sealed. In sample-data (mock)
 * mode there is no engine, so this returns an honest `available: false` envelope
 * rather than fabricating a council — mirroring how sealing refuses offline.
 */
export async function fetchMatchAnalysis(matchId: string): Promise<MatchAnalysisResponse> {
  if (!API_BASE) {
    return {
      available: false,
      reason:
        "Model analysis runs in the connected Golavo app; this sample-data preview has no " +
        "engine to fit the models. Open Golavo locally to see the council for this match.",
      analysis: null,
    };
  }
  try {
    return assertMatchAnalysis(
      await getJson(`/api/v1/matches/${encodeURIComponent(matchId)}/analysis`),
      `matches/${matchId}/analysis`,
    );
  } catch (err) {
    if (err instanceof Error && /HTTP 404/.test(err.message))
      return { available: false, reason: "match not found", analysis: null };
    throw err;
  }
}

/**
 * The Games-home rails: upcoming fixtures and recent results. Live mode hits
 * `/api/v1/matches/recent`; mock mode splits the bundled rows the same way the
 * server does (upcoming = scheduled from start-of-today; recent = completed,
 * newest first), so the home works offline and in the web bundle.
 */
export interface RecentMatchesOptions {
  competition?: string;
  sourceKind?: SourceKind;
}

export async function fetchRecentMatches(
  limit = 24,
  opts: RecentMatchesOptions = {},
): Promise<RecentMatchesResponse> {
  if (!API_BASE) {
    const { schema_version, matches } = await loadMockMatches();
    let rows = matches.slice();
    if (opts.competition) rows = rows.filter((m) => m.competition === opts.competition);
    if (opts.sourceKind) rows = rows.filter((m) => m.source_kind === opts.sourceKind);
    const today = new Date();
    today.setUTCHours(0, 0, 0, 0);
    const byKickoffDesc = (a: MatchRow, b: MatchRow) =>
      b.kickoff_utc.localeCompare(a.kickoff_utc) || a.match_id.localeCompare(b.match_id);
    const recent = rows.filter((m) => m.is_complete).sort(byKickoffDesc).slice(0, limit);
    const upcoming = rows
      .filter((m) => !m.is_complete && new Date(m.kickoff_utc).getTime() >= today.getTime())
      .sort((a, b) => a.kickoff_utc.localeCompare(b.kickoff_utc) || a.match_id.localeCompare(b.match_id))
      .slice(0, limit);
    return { schema_version, upcoming, recent };
  }
  const params = new URLSearchParams({ limit: String(limit) });
  if (opts.competition) params.set("competition", opts.competition);
  if (opts.sourceKind) params.set("source_kind", opts.sourceKind);
  const body = (await getJson(`/api/v1/matches/recent?${params.toString()}`)) as RecentMatchesResponse;
  if (!Array.isArray(body.recent) || !Array.isArray(body.upcoming))
    throw new ContractError("matches/recent: missing rails");
  body.recent.forEach((m, i) => assertMatchRow(m, `matches/recent.recent[${i}]`));
  body.upcoming.forEach((m, i) => assertMatchRow(m, `matches/recent.upcoming[${i}]`));
  return body;
}

/** UTC midnight (ms) of an ISO timestamp — used to compare kickoffs by day, so a
 *  real 21:45 kickoff and a 00:00 day-proxy on the same day are treated alike. */
function utcDayMs(iso: string): number {
  const d = new Date(iso);
  return Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate());
}

function competitionCounts(rows: MatchRow[]): CompetitionCount[] {
  const by = new Map<string, CompetitionCount>();
  for (const m of rows) {
    const key = `${m.competition}|${m.source_kind}`;
    const c = by.get(key);
    if (c) c.n_matches += 1;
    else by.set(key, { competition: m.competition, source_kind: m.source_kind, n_matches: 1 });
  }
  return Array.from(by.values()).sort(
    (a, b) => a.source_kind.localeCompare(b.source_kind) || a.competition.localeCompare(b.competition),
  );
}

const WINDOW_DAYS: Record<Exclude<MatchWindow, "upcoming">, number> = { week: 7, month: 30 };

/**
 * The Matchday home feed. Live mode hits `/api/v1/matches/window`; mock mode
 * mirrors the SAME anchor semantics over the bundled rows (week/month bound to
 * the freshest completed kickoff), so the home is deterministic offline and in
 * the web bundle regardless of the wall clock.
 */
export async function fetchMatchesWindow(
  window: MatchWindow,
  limit = 200,
): Promise<MatchesWindowResponse> {
  if (!API_BASE) {
    const { schema_version, matches } = await loadMockMatches();
    const completed = matches.filter((m) => m.is_complete);
    const latestMs = completed.length
      ? Math.max(...completed.map((m) => utcDayMs(m.kickoff_utc)))
      : null;
    const latest_result_utc = latestMs !== null ? new Date(latestMs).toISOString() : null;

    let sel: MatchRow[];
    let window_start_utc: string | null;
    let window_end_utc: string | null;
    if (window === "upcoming") {
      const today = new Date();
      const todayMs = Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate());
      sel = matches
        .filter((m) => !m.is_complete && new Date(m.kickoff_utc).getTime() >= todayMs)
        .sort((a, b) => a.kickoff_utc.localeCompare(b.kickoff_utc) || a.match_id.localeCompare(b.match_id));
      window_start_utc = new Date(todayMs).toISOString();
      window_end_utc = null;
    } else if (latestMs === null) {
      sel = [];
      window_start_utc = window_end_utc = null;
    } else {
      const days = WINDOW_DAYS[window];
      const startMs = latestMs - (days - 1) * 86_400_000;
      sel = completed
        .filter((m) => utcDayMs(m.kickoff_utc) >= startMs && utcDayMs(m.kickoff_utc) <= latestMs)
        .sort((a, b) => b.kickoff_utc.localeCompare(a.kickoff_utc) || a.match_id.localeCompare(b.match_id));
      window_start_utc = new Date(startMs).toISOString();
      window_end_utc = new Date(latestMs).toISOString();
    }
    return {
      schema_version,
      window,
      window_start_utc,
      window_end_utc,
      latest_result_utc,
      total: sel.length,
      matches: sel.slice(0, limit),
      competitions: competitionCounts(sel),
    };
  }
  const params = new URLSearchParams({ window, limit: String(limit) });
  const body = (await getJson(`/api/v1/matches/window?${params.toString()}`)) as MatchesWindowResponse;
  if (!Array.isArray(body.matches) || !Array.isArray(body.competitions))
    throw new ContractError("matches/window: missing matches/competitions");
  if (body.window !== window)
    throw new ContractError(`matches/window: echoed window ${body.window} != ${window}`);
  body.matches.forEach((m, i) => assertMatchRow(m, `matches/window.matches[${i}]`));
  return body;
}

// ---- User picks -------------------------------------------------------------

function assertPickResponse(value: unknown, ctx: string): PickResponse {
  const response = value as PickResponse;
  if (!response || typeof response !== "object" || response.schema_version !== "0.1.0")
    throw new ContractError(`${ctx}: invalid pick response`);
  if (response.pick && response.pick.record.match.match_id !== response.match_id)
    throw new ContractError(`${ctx}: pick match id mismatch`);
  return response;
}

function pickHeaders(): Record<string, string> {
  return { ...apiHeaders(), "content-type": "application/json" };
}

async function pickFailure(res: Response): Promise<PickApiError> {
  let reason = "pick_rejected";
  let message = `pick request failed (HTTP ${res.status})`;
  try {
    const body = (await res.json()) as { detail?: { reason_code?: string; message?: string } };
    reason = body.detail?.reason_code ?? reason;
    message = body.detail?.message ?? message;
  } catch {
    /* use the typed generic fallback */
  }
  return new PickApiError(message, res.status, reason);
}

function mockFailure(error: unknown): never {
  if (error instanceof MockPickError)
    throw new PickApiError(error.message, error.status, error.reasonCode);
  throw error;
}

function picksChanged(): void {
  clearApiCache();
  window.dispatchEvent(new CustomEvent("golavo-picks-changed"));
}

export async function fetchPick(matchId: string): Promise<PickResponse | null> {
  if (!API_BASE) return mockFetchPick(matchId);
  const path = `/api/v1/matches/${encodeURIComponent(matchId)}/pick`;
  try {
    return assertPickResponse(await getJson(path), `pick/${matchId}`);
  } catch (error) {
    if (error instanceof Error && /HTTP 404/.test(error.message)) return null;
    throw error;
  }
}

export async function savePick(
  matchId: string,
  homeGoals: number,
  awayGoals: number,
): Promise<PickResponse> {
  if (!API_BASE) {
    try {
      const response = await mockSavePick(matchId, homeGoals, awayGoals);
      picksChanged();
      return response;
    } catch (error) {
      return mockFailure(error);
    }
  }
  const res = await fetch(`${API_BASE}/api/v1/matches/${encodeURIComponent(matchId)}/pick`, {
    method: "PUT",
    headers: pickHeaders(),
    body: JSON.stringify({ home_goals: homeGoals, away_goals: awayGoals }),
  });
  if (!res.ok) throw await pickFailure(res);
  const response = assertPickResponse(await res.json(), `pick/${matchId}`);
  picksChanged();
  return response;
}

export async function deletePick(matchId: string): Promise<PickResponse | null> {
  if (!API_BASE) {
    try {
      const response = await mockDeletePick(matchId);
      picksChanged();
      return response;
    } catch (error) {
      return mockFailure(error);
    }
  }
  const res = await fetch(`${API_BASE}/api/v1/matches/${encodeURIComponent(matchId)}/pick`, {
    method: "DELETE",
    headers: apiHeaders(),
  });
  if (res.status === 404) return null;
  if (!res.ok) throw await pickFailure(res);
  const response = assertPickResponse(await res.json(), `pick/${matchId}`);
  picksChanged();
  return response;
}

export async function fetchPicks(options: {
  status?: string;
  season?: string;
  limit?: number;
  offset?: number;
} = {}): Promise<PicksListResponse> {
  const limit = options.limit ?? 500;
  const offset = options.offset ?? 0;
  if (!API_BASE) {
    const all = await mockFetchPicks(500, 0);
    const filtered = all.items.filter(
      (view) =>
        (!options.status || view.status === options.status) &&
        (!options.season || footballSeason(view.record.match.kickoff_utc) === options.season),
    );
    return { ...all, items: filtered.slice(offset, offset + limit), total: filtered.length, limit, offset };
  }
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (options.status) params.set("status", options.status);
  if (options.season) params.set("season", options.season);
  const response = (await getJson(`/api/v1/picks?${params}`)) as PicksListResponse;
  if (response.schema_version !== "0.1.0" || !Array.isArray(response.items))
    throw new ContractError("picks: invalid list response");
  return response;
}

export async function fetchPicksSummary(season?: string): Promise<PicksSummary> {
  if (!API_BASE) return mockFetchPicksSummary(season ?? null);
  const params = season ? `?season=${encodeURIComponent(season)}` : "";
  const response = (await getJson(`/api/v1/picks/summary${params}`)) as PicksSummary;
  if (response.schema_version !== "0.1.0" || !response.counts || !response.user)
    throw new ContractError("picks/summary: invalid response");
  return response;
}

function footballSeason(kickoff: string): string {
  const date = new Date(kickoff);
  const start = date.getUTCMonth() >= 6 ? date.getUTCFullYear() : date.getUTCFullYear() - 1;
  return `${start}-${String(start + 1).slice(-2)}`;
}
