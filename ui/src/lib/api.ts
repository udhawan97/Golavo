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
  CompetitionsResponse,
  EvalSummary,
  ForecastArtifact,
  MatchDetailResponse,
  MatchNotebookResponse,
  MatchRow,
  MatchSearchResponse,
  NotebookResponse,
  SealEligibility,
  SealResult,
  SourceKind,
} from "./contract";
import type { AiProvider, NarrativeResponse } from "./ai";
import {
  loadMockCalibration,
  loadMockEval,
  loadMockForecast,
  loadMockForecasts,
  loadMockMatches,
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
    const res = await fetch(`${API_BASE}/health`, { headers });
    return res.ok;
  } catch {
    return false;
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
function apiHeaders(): Record<string, string> {
  const headers: Record<string, string> = { accept: "application/json" };
  if (API_TOKEN) headers["x-golavo-token"] = API_TOKEN;
  return headers;
}

async function getJson(path: string): Promise<unknown> {
  const res = await fetch(`${API_BASE}${path}`, { headers: apiHeaders() });
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
    else if (opts.status === "upcoming") rows = rows.filter((m) => !m.is_complete);
    if (nq)
      rows = rows.filter(
        (m) =>
          normalizeText(m.home_team).includes(nq) ||
          normalizeText(m.away_team).includes(nq) ||
          normalizeText(m.competition).includes(nq),
      );
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
