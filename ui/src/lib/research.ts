import { API_BASE, apiHeaders, clearApiCache } from "./api";

export interface ResearchSourceCapability {
  source_id: string;
  name: string;
  license: string;
  license_url: string;
  attribution: string;
  roles: string[];
  hosts: string[];
  license_namespace: string;
  permitted_fact_types: string[];
  ai_fallback: boolean;
  terms_url: string;
}

export interface ResearchCapabilities {
  schema_version: "0.1.0";
  supported: boolean;
  write_enabled: boolean;
  enabled: boolean;
  foreground_only: true;
  automatic_fetch: false;
  built_in_general_search: false;
  cloud_ai_extraction: false;
  authoritative_output: false;
  max_pages_per_run: 4;
  max_raw_bytes_per_page: 524288;
  searxng_supported: false;
  current_index_fingerprint: string | null;
  sources: ResearchSourceCapability[];
}

export interface ResearchSettings {
  schema_version: "0.1.0";
  enabled: boolean;
  retention_days: number;
  searxng_enabled: boolean;
  searxng_url: string | null;
}

export interface DiscoveryItem {
  provider: "wikipedia" | "wikidata";
  title: string;
  description?: string;
  url: string;
  source_id: string;
  permitted: true;
  license_namespace: string;
}

export interface ResearchCandidate {
  candidate_id: string;
  run_id: string;
  authority: "untrusted_candidate";
  state: "review_required" | "queued_as_draft" | "rejected" | "conflict" | "stale";
  correction_type: "team_alias" | "venue";
  target: { match_id: string; index_fingerprint: string; entity_id: string | null };
  proposed: Record<string, unknown>;
  source: {
    source_id: string;
    canonical_url: string;
    retrieved_at_utc: string;
    revision_id: string | null;
    license: string;
    license_url: string;
    attribution: string;
    modifications: "normalized plaintext excerpt";
    license_namespace: string;
  };
  evidence: {
    capture_id: string;
    raw_sha256: string;
    canonical_text_sha256: string;
    exact_quote: string;
  };
  extractor: { kind: "deterministic" | "local_ai"; id: string; model: string | null };
  queued_proposal_id: string | null;
}

export interface ResearchRun {
  schema_version: "0.1.0";
  run_id: string;
  match_id: string;
  index_fingerprint: string;
  state: "planned" | "fetching" | "captured" | "extracting" | "candidates_ready" | "partial" | "cancelled" | "offline" | "failed";
  selected_urls: string[];
  allow_local_ai: boolean;
  counts: { selected: number; captured: number; candidates: number; failed: number };
  reason_codes: string[];
  candidates?: ResearchCandidate[];
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  if (!API_BASE) throw new Error("Match research requires the installed local engine.");
  const headers = { ...apiHeaders(), ...(init?.body ? { "content-type": "application/json" } : {}) };
  const response = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!response.ok) {
    let message = `Research request failed (HTTP ${response.status}).`;
    try {
      const payload = (await response.json()) as { detail?: string | { message?: string } };
      if (typeof payload.detail === "string") message = payload.detail;
      else if (payload.detail?.message) message = payload.detail.message;
    } catch { /* keep generic message */ }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export function fetchResearchCapabilities(): Promise<ResearchCapabilities> {
  return request("/api/v1/research/capabilities");
}

export function fetchResearchSettings(): Promise<ResearchSettings> {
  return request("/api/v1/research/settings");
}

export async function saveResearchSettings(value: ResearchSettings): Promise<ResearchSettings> {
  const result = await request<ResearchSettings>("/api/v1/research/settings", {
    method: "PUT",
    body: JSON.stringify(value),
  });
  clearApiCache();
  return result;
}

export async function discoverResearchSources(query: string, signal?: AbortSignal): Promise<DiscoveryItem[]> {
  const result = await request<{ items: DiscoveryItem[] }>("/api/v1/research/discoveries", {
    method: "POST",
    signal,
    body: JSON.stringify({ provider: "wikimedia", query, confirm: "discover_sources" }),
  });
  return result.items;
}

export function createResearchRun(input: {
  matchId: string;
  indexFingerprint: string;
  selectedUrls: string[];
  localAi?: { provider: "ollama" | "llama_server"; model?: string };
}): Promise<ResearchRun> {
  return request("/api/v1/research/runs", {
    method: "POST",
    body: JSON.stringify({
      match_id: input.matchId,
      expected_index_fingerprint: input.indexFingerprint,
      selected_urls: input.selectedUrls,
      allow_local_ai: Boolean(input.localAi),
      local_ai: input.localAi,
      confirm: "fetch_selected_sources",
    }),
  });
}

export function fetchResearchRun(runId: string): Promise<ResearchRun> {
  return request(`/api/v1/research/runs/${encodeURIComponent(runId)}`);
}

export async function fetchResearchRuns(matchId: string, limit = 10): Promise<ResearchRun[]> {
  const params = new URLSearchParams({ match_id: matchId, limit: String(limit) });
  const result = await request<{ items: ResearchRun[] }>(`/api/v1/research/runs?${params}`);
  return result.items;
}

export function cancelResearchRun(runId: string): Promise<{ cancelled: boolean; run: ResearchRun }> {
  return request(`/api/v1/research/runs/${encodeURIComponent(runId)}/cancel`, { method: "POST" });
}

export function queueResearchCandidate(candidate: ResearchCandidate): Promise<unknown> {
  return request(`/api/v1/research/candidates/${encodeURIComponent(candidate.candidate_id)}/queue`, {
    method: "POST",
    body: JSON.stringify({
      expected_candidate_sha256: candidate.candidate_id.slice(3),
      expected_index_fingerprint: candidate.target.index_fingerprint,
      confirm: "add_to_correction_queue",
    }),
  });
}

export function clearResearchHistory(): Promise<{ removed: boolean; settings_preserved: boolean }> {
  return request("/api/v1/research/history", {
    method: "DELETE",
    body: JSON.stringify({ confirm: "remove_local_research_history" }),
  });
}
