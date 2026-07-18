import { API_BASE, apiHeaders } from "./api";

export type OpenLigaDBShortcut = "bl1" | "bl2" | "bl3" | "dfb";
export type OpenLigaDBRefreshPolicy = "manual" | "while_open";

export interface OpenLigaDBErrorDetail {
  code: string;
  message: string;
  retryable: boolean;
}

export interface OpenLigaDBJob {
  schema_version: "0.1.0";
  job_id: string;
  state: "queued" | "running" | "done" | "failed" | "cancelled";
  stage: "queued" | "downloading" | "validating" | "building" | "activating" | "done";
  trigger: "manual" | "launch" | "periodic";
  created_at_utc: string;
  updated_at_utc: string;
  cancel_requested: boolean;
  progress: Record<string, unknown>;
  result: Record<string, unknown> | null;
  error: OpenLigaDBErrorDetail | null;
  deduplicated?: boolean;
}

export interface OpenLigaDBCapability {
  shortcut: OpenLigaDBShortcut;
  season: string;
  state: "available" | "absent" | "conflict";
  reason: string | null;
  league_id?: number;
  league_name?: string;
  group_count?: number;
}

export interface OpenLigaDBStatus {
  schema_version: "0.1.0";
  source_id: "openligadb";
  overlay_supported: boolean;
  enabled: boolean;
  refresh_policy: OpenLigaDBRefreshPolicy;
  selected_competitions: OpenLigaDBShortcut[];
  health: "disabled" | "unavailable" | "stale" | "refreshing" | "ready" | "backoff" | "conflict";
  display_only: true;
  license: {
    id: "ODbL-1.0";
    url: string;
    attribution: string;
    accepted_at_utc: string | null;
  };
  usage: {
    display: true;
    model_training: false;
    forecast_sealing: false;
    forecast_settlement: false;
    calibration: false;
    exports: false;
  };
  active_generation: {
    generation_id: string;
    created_at_utc: string;
    activated_at_utc: string | null;
    season: string;
    content_revision: string;
    database_sha256: string;
    rollback_available: boolean;
    using_previous_generation: boolean;
  } | null;
  capabilities: OpenLigaDBCapability[];
  last_checked_at_utc: string | null;
  last_activated_at_utc: string | null;
  next_check_after_utc: string | null;
  last_error: OpenLigaDBErrorDetail | null;
  job: OpenLigaDBJob | null;
  storage_bytes: number;
}

export interface OpenLigaDBMatch {
  source_match_id: number;
  shortcut: OpenLigaDBShortcut;
  season: string;
  group_name: string;
  kickoff_utc: string;
  home_source_team_id: number;
  away_source_team_id: number;
  home_team_name: string;
  away_team_name: string;
  is_finished: boolean;
  final_home_goals: number | null;
  final_away_goals: number | null;
  source_last_updated: string | null;
  state: "community_unverified";
  core_relation: "not_compared";
  provenance: {
    source_id: "openligadb";
    license: "ODbL-1.0";
    raw_sha256: string;
    endpoint: string;
    captured_at_utc: string;
  };
}

export interface OpenLigaDBMatchesResponse {
  schema_version: "0.1.0";
  source_id: "openligadb";
  license: "ODbL-1.0";
  attribution: string;
  display_only: true;
  identity_policy: string;
  conflict_policy: string;
  matches: OpenLigaDBMatch[];
}

const DISABLED_STATUS: OpenLigaDBStatus = {
  schema_version: "0.1.0",
  source_id: "openligadb",
  overlay_supported: false,
  enabled: false,
  refresh_policy: "manual",
  selected_competitions: ["bl1", "bl2", "bl3", "dfb"],
  health: "disabled",
  display_only: true,
  license: {
    id: "ODbL-1.0",
    url: "https://www.openligadb.de/lizenz",
    attribution: "Datenquelle: OpenLigaDB (www.openligadb.de) — Open Database License (ODbL) v1.0.",
    accepted_at_utc: null,
  },
  usage: {
    display: true,
    model_training: false,
    forecast_sealing: false,
    forecast_settlement: false,
    calibration: false,
    exports: false,
  },
  active_generation: null,
  capabilities: [],
  last_checked_at_utc: null,
  last_activated_at_utc: null,
  next_check_after_utc: null,
  last_error: null,
  job: null,
  storage_bytes: 0,
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  if (!API_BASE) throw new Error("OpenLigaDB is available only in the installed Golavo app.");
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...apiHeaders(),
      ...(init?.body ? { "content-type": "application/json" } : {}),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    let message = `OpenLigaDB request failed (HTTP ${response.status})`;
    try {
      const body = (await response.json()) as { detail?: string | { message?: string } };
      if (typeof body.detail === "string") message = body.detail;
      else if (body.detail?.message) message = body.detail.message;
    } catch {
      /* retain the bounded generic message */
    }
    throw new Error(message);
  }
  return (await response.json()) as T;
}

export async function fetchOpenLigaDBStatus(): Promise<OpenLigaDBStatus> {
  if (!API_BASE) return DISABLED_STATUS;
  return request<OpenLigaDBStatus>("/api/v1/overlays/openligadb/status");
}

export async function configureOpenLigaDB(input: {
  enabled?: boolean;
  refresh_policy?: OpenLigaDBRefreshPolicy;
  selected_competitions?: OpenLigaDBShortcut[];
  accept_odbl?: boolean;
}): Promise<OpenLigaDBStatus> {
  return request<OpenLigaDBStatus>("/api/v1/overlays/openligadb/settings", {
    method: "PUT",
    body: JSON.stringify(input),
  });
}

export async function startOpenLigaDBRefresh(
  trigger: "manual" | "launch" | "periodic",
): Promise<OpenLigaDBJob> {
  return request<OpenLigaDBJob>("/api/v1/overlays/openligadb/refresh", {
    method: "POST",
    body: JSON.stringify({ trigger }),
  });
}

export function fetchOpenLigaDBJob(jobId: string): Promise<OpenLigaDBJob> {
  return request<OpenLigaDBJob>(`/api/v1/overlays/openligadb/refresh/${encodeURIComponent(jobId)}`);
}

export function cancelOpenLigaDBJob(jobId: string): Promise<OpenLigaDBJob> {
  return request<OpenLigaDBJob>(
    `/api/v1/overlays/openligadb/refresh/${encodeURIComponent(jobId)}/cancel`,
    { method: "POST" },
  );
}

export function rollbackOpenLigaDB(): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>("/api/v1/overlays/openligadb/rollback", {
    method: "POST",
  });
}

export function deleteOpenLigaDB(): Promise<{ deleted: boolean }> {
  return request<{ deleted: boolean }>("/api/v1/overlays/openligadb", { method: "DELETE" });
}

export async function fetchOpenLigaDBMatches(limit = 12): Promise<OpenLigaDBMatchesResponse> {
  return request<OpenLigaDBMatchesResponse>(
    `/api/v1/overlays/openligadb/matches?limit=${encodeURIComponent(String(limit))}`,
  );
}
