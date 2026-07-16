export const CORRECTION_SCHEMA_VERSION = "0.1.0" as const;

export type CorrectionType =
  | "missing_fixture"
  | "kickoff_time"
  | "team_alias"
  | "venue"
  | "final_score";
export type CorrectionState =
  | "draft"
  | "evidence_attached"
  | "validated_candidate"
  | "conflict"
  | "accepted_local"
  | "exported"
  | "submitted"
  | "withdrawn"
  | "superseded";
export type VerificationLevel = "none" | "structural_only" | "snapshot_verified";

export interface CorrectionSource {
  source_id: string;
  name: string;
  license: string;
  license_url: string | null;
  attribution: string | null;
  license_namespace: string;
  allowed_types: CorrectionType[];
  redistributable_export: boolean;
  contribution_url: string;
}

export interface CorrectionCapabilities {
  schema_version: typeof CORRECTION_SCHEMA_VERSION;
  supported: boolean;
  write_enabled: boolean;
  central_service: false;
  accounts: false;
  telemetry: false;
  network_evidence_fetch: false;
  automatic_submission: false;
  authoritative_override: false;
  max_evidence_bytes: 65536;
  max_evidence_items: 10;
  namespaces: string[];
  sources: CorrectionSource[];
  current_index_fingerprint: string | null;
}

export interface CorrectionEvidence {
  evidence_id: string;
  source_url: string;
  hostname: string;
  source_id: string;
  license_namespace: string;
  source_revision: string | null;
  raw_sha256: string;
  raw_bytes: number;
  sanitized_text: string;
  sanitized_sha256: string;
  untrusted: true;
  snapshot_verified: boolean;
  captured_at_utc: string;
  redacted: boolean;
}

export interface CorrectionProposal {
  schema_version: typeof CORRECTION_SCHEMA_VERSION;
  proposal_id: string;
  license_namespace: string;
  correction_type: CorrectionType;
  state: CorrectionState;
  verification_level: VerificationLevel;
  target: {
    kind: "match" | "team" | "venue" | "fixture_candidate";
    match_id: string | null;
    entity_id: string | null;
    upstream_record_key: string | null;
    base_generation_id: string | null;
    index_fingerprint: string | null;
  };
  original: Record<string, unknown> | null;
  proposed: Record<string, unknown>;
  source_id: string | null;
  evidence: CorrectionEvidence[];
  validation: {
    reason_codes: string[];
    conflicts: Array<Record<string, unknown>>;
  };
  local_visibility: "queue_only" | "local_annotation";
  head_event_id: string;
  created_at_utc: string;
  updated_at_utc: string;
}

export interface CorrectionList {
  schema_version: typeof CORRECTION_SCHEMA_VERSION;
  items: CorrectionProposal[];
  total: number;
  limit: number;
  offset: number;
}

export interface CorrectionExportReceipt {
  export_id: string;
  proposal_id: string;
  proposal_head_event_id: string;
  relative_path: string;
  sha256: string;
  bytes: number;
}

type RuntimeConfig = { apiBase?: string; token?: string };
const runtime: RuntimeConfig =
  typeof window === "undefined" ? {} : (window.__GOLAVO_RUNTIME__ ?? {});
const base = runtime.apiBase ?? (import.meta.env.VITE_GOLAVO_API as string | undefined);

export class CorrectionApiError extends Error {
  readonly status: number;
  readonly reasonCode: string;

  constructor(message: string, status: number, reasonCode: string) {
    super(message);
    this.name = "CorrectionApiError";
    this.status = status;
    this.reasonCode = reasonCode;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  if (!base) throw new CorrectionApiError("Corrections require the installed Golavo app.", 0, "desktop_required");
  const headers = new Headers(init.headers);
  headers.set("accept", "application/json");
  if (init.body) headers.set("content-type", "application/json");
  if (runtime.token) headers.set("x-golavo-token", runtime.token);
  const response = await fetch(`${base.replace(/\/+$/, "")}${path}`, { ...init, headers });
  if (!response.ok) {
    let message = `Correction request failed (HTTP ${response.status}).`;
    let reasonCode = "correction_request_failed";
    try {
      const body = (await response.json()) as {
        detail?: string | { reason_code?: string; message?: string };
      };
      if (typeof body.detail === "string") message = body.detail;
      else if (body.detail) {
        message = body.detail.message ?? message;
        reasonCode = body.detail.reason_code ?? reasonCode;
      }
    } catch {
      // Preserve the honest generic status when the sidecar returned no JSON.
    }
    throw new CorrectionApiError(message, response.status, reasonCode);
  }
  return (await response.json()) as T;
}

export function fetchCorrectionCapabilities(): Promise<CorrectionCapabilities> {
  return request("/api/v1/corrections/capabilities");
}

export function fetchCorrections(): Promise<CorrectionList> {
  return request("/api/v1/corrections?limit=100");
}

export function fetchCorrection(proposalId: string): Promise<CorrectionProposal> {
  return request(`/api/v1/corrections/${encodeURIComponent(proposalId)}`);
}

export function createCorrection(input: {
  correction_type: CorrectionType;
  source_id: string;
  target: { match_id?: string };
  proposed: Record<string, unknown>;
}): Promise<CorrectionProposal> {
  return request("/api/v1/corrections", { method: "POST", body: JSON.stringify(input) });
}

export function attachCorrectionEvidence(
  proposalId: string,
  input: { source_url: string; captured_text: string; source_revision?: string },
): Promise<CorrectionProposal> {
  return request(`/api/v1/corrections/${encodeURIComponent(proposalId)}/evidence`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function validateCorrection(proposalId: string): Promise<CorrectionProposal> {
  return request(`/api/v1/corrections/${encodeURIComponent(proposalId)}/validate`, {
    method: "POST",
  });
}

export function acceptLocalCorrection(proposal: CorrectionProposal): Promise<CorrectionProposal> {
  return request(`/api/v1/corrections/${encodeURIComponent(proposal.proposal_id)}/accept-local`, {
    method: "POST",
    body: JSON.stringify({
      confirm: "local_annotation_only",
      expected_head_event_id: proposal.head_event_id,
    }),
  });
}

export function exportCorrection(proposal: CorrectionProposal): Promise<CorrectionExportReceipt> {
  return request(`/api/v1/corrections/${encodeURIComponent(proposal.proposal_id)}/exports`, {
    method: "POST",
    body: JSON.stringify({
      confirm: "reviewed_for_public_export",
      expected_head_event_id: proposal.head_event_id,
    }),
  });
}

export function markCorrectionSubmitted(proposal: CorrectionProposal): Promise<CorrectionProposal> {
  return request(`/api/v1/corrections/${encodeURIComponent(proposal.proposal_id)}/mark-submitted`, {
    method: "POST",
    body: JSON.stringify({
      confirm: "submitted_externally",
      expected_head_event_id: proposal.head_event_id,
    }),
  });
}

export function redactCorrectionEvidence(
  proposal: CorrectionProposal,
  evidenceId: string,
): Promise<CorrectionProposal> {
  return request(
    `/api/v1/corrections/${encodeURIComponent(proposal.proposal_id)}/evidence/${encodeURIComponent(evidenceId)}/redact`,
    {
      method: "POST",
      body: JSON.stringify({
        confirm: "redact_local_evidence",
        expected_head_event_id: proposal.head_event_id,
      }),
    },
  );
}

export function purgeCorrections(): Promise<{ removed: boolean }> {
  return request("/api/v1/corrections", {
    method: "DELETE",
    body: JSON.stringify({ confirm: "remove_all_local_corrections" }),
  });
}

export function saveCorrectionExport(exportId: string): Promise<string | null> {
  if (typeof window === "undefined" || !window.__TAURI__) {
    throw new CorrectionApiError(
      "The native save dialog is available in the installed Golavo app.",
      0,
      "desktop_required",
    );
  }
  return window.__TAURI__.core.invoke<string | null>("save_correction_export", {
    exportId,
  });
}
