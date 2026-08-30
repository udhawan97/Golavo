import { API_BASE, apiHeaders } from "./api";

export type SportmonksCapability =
  | "external_prediction"
  | "external_odds"
  | "player_lens"
  | "transfer_desk";

export interface SportmonksStatus {
  schema_version: "0.1.0";
  enabled: boolean;
  capabilities: SportmonksCapability[];
  terms_accepted_at_utc: string | null;
  terms_acceptance_version: string | null;
  connector_supported: boolean;
  request_policy: "foreground_click_only";
  storage_policy: "derived_response_memory_only";
  provider: {
    source_id: "sportmonks-v3";
    name: string;
    docs_url: string;
    terms_url: string;
    privacy_url: string;
    pricing_url: string;
    terms_reviewed_date: string;
    terms_content_sha256: string;
    terms_acceptance_version: string;
  };
  credential: {
    configured: boolean;
    source: "environment" | "keychain" | "none";
    writable: boolean;
    environment_variable: "SPORTMONKS_API_TOKEN";
  };
  usage: {
    display: true;
    model_input: false;
    forecast_sealing: false;
    forecast_settlement: false;
    calibration: false;
    scoring: false;
    ai_evidence: false;
    exports: false;
  };
}

export interface UnavailableSignal {
  status: "unavailable" | "disabled";
  reason_code: string;
  message: string;
  retryable: boolean;
}

export interface OutsideSignals {
  schema_version: "0.1.0";
  status: "available" | "partial" | "unavailable";
  label: "Outside signals — not a Golavo forecast.";
  provider: {
    source_id: "sportmonks-v3";
    name: string;
    docs_url: string;
    terms_url: string;
  };
  identity: {
    golavo_match_id: string;
    provider_fixture_id: number;
    provider_home_team_id: number;
    provider_away_team_id: number;
    provider_home_team: string;
    provider_away_team: string;
    provider_league_id: number | null;
    provider_league: string | null;
    provider_season_id: number | null;
    provider_season: string | null;
    provider_kickoff_utc: string | null;
    match_method:
      | "exact_normalized_teams_and_kickoff"
      | "exact_competition_season_teams_and_kickoff"
      | "exact_competition_season_teams_and_calendar_date";
  };
  prediction:
    | UnavailableSignal
    | {
        status: "available";
        prediction_id: number;
        type_id: number;
        label: string;
        percent: { home: number; draw: number; away: number };
      };
  odds:
    | UnavailableSignal
    | {
        status: "available";
        market: "Match Winner";
        format: "decimal";
        bookmakers: Array<{
          bookmaker_id: number;
          bookmaker_name: string;
          market_id: 1;
          market: string;
          updated_at_utc: string | null;
          decimal: { home: number; draw: number; away: number };
        }>;
      };
  player_lens:
    | UnavailableSignal
    | {
        status: "available";
        lineup_state: "confirmed" | "predicted" | "unverified";
        players: Array<{
          lineup_id: number;
          player_id: number;
          team_id: number;
          name: string;
          jersey_number: number | null;
          position_id: number | null;
          participation: "starter" | "substitute";
          metrics: Array<{
            type_id: number;
            developer_name: string;
            label: string;
            group: string | null;
            unit: "count" | "percent" | "minutes" | "boolean" | "provider_score";
            value: number | boolean;
          }>;
        }>;
        coverage: {
          player_count: number;
          players_with_metrics: number;
          missing_stat_is_zero: false;
        };
      };
  provenance: {
    fetched_at_utc: string;
    terms_acceptance_version: string;
    raw_response_sha256: Record<string, string | string[] | null>;
    raw_response_storage: "not_persisted";
    model_input: false;
  };
}

export interface TransferDeskResponse {
  schema_version: "0.1.0";
  status: "available" | "partial";
  label: "Provider transfer records — not Golavo model evidence.";
  provider: {
    source_id: "sportmonks-v3";
    name: string;
    docs_url: string;
    terms_url: string;
  };
  identity: {
    golavo_match_id: string;
    golavo_team: string;
    golavo_side: "home" | "away";
    provider_fixture_id: number;
    provider_team_id: number;
    provider_team: string;
    provider_league_id: number | null;
    provider_season_id: number | null;
    match_method: OutsideSignals["identity"]["match_method"];
  };
  transfers: Array<{
    transfer_id: number;
    direction: "arrival" | "departure";
    date: string;
    completed: boolean;
    player: { id: number; name: string };
    type: { id: number; name: string };
    from_team: { id: number; name: string };
    to_team: { id: number; name: string };
    position: { id: number; name: string } | null;
    provider_reported_amount: string | null;
    amount_label: "Provider-reported amount — currency unspecified";
    payment_breakdown: {
      status: "unavailable";
      reason_code: "provider_fields_not_reported";
      currency: null;
      installments: null;
      add_ons: null;
      sell_on_terms: null;
      agent_or_intermediary_fees: null;
      training_rewards: null;
      conditional_consideration: null;
    };
  }>;
  coverage: {
    window_start: string;
    window_end: string;
    window_days: 365;
    pages_fetched: number;
    page_limit: 4;
    rows_per_page_limit: 50;
    truncated: boolean;
  };
  provenance: {
    fetched_at_utc: string;
    terms_acceptance_version: string;
    raw_response_sha256: {
      fixture_pages: string[];
      transfer_pages: string[];
    };
    raw_response_storage: "not_persisted";
  };
  usage: {
    display: true;
    model_input: false;
    forecast_sealing: false;
    forecast_settlement: false;
    calibration: false;
    scoring: false;
    ai_evidence: false;
    exports: false;
  };
}

export class SportmonksApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly reasonCode: string,
  ) {
    super(message);
    this.name = "SportmonksApiError";
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  if (!API_BASE)
    throw new SportmonksApiError(
      "Sportmonks is available only in the installed Golavo app.",
      0,
      "desktop_required",
    );
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...apiHeaders(),
      ...(init.body ? { "content-type": "application/json" } : {}),
      ...init.headers,
    },
  });
  if (!response.ok) {
    let message = `Sportmonks request failed (HTTP ${response.status})`;
    let reasonCode = "sportmonks_request_failed";
    try {
      const body = (await response.json()) as {
        detail?: string | { message?: string; reason_code?: string };
      };
      if (typeof body.detail === "string") message = body.detail;
      else if (body.detail) {
        if (body.detail.message) message = body.detail.message;
        if (body.detail.reason_code) reasonCode = body.detail.reason_code;
      }
    } catch {
      /* retain the bounded generic message */
    }
    throw new SportmonksApiError(message, response.status, reasonCode);
  }
  return (await response.json()) as T;
}

export function fetchSportmonksStatus(): Promise<SportmonksStatus> {
  return request<SportmonksStatus>("/api/v1/providers/sportmonks/settings");
}

export function configureSportmonks(input: {
  enabled?: boolean;
  capabilities?: SportmonksCapability[];
  accept_terms?: boolean;
}): Promise<SportmonksStatus> {
  return request<SportmonksStatus>("/api/v1/providers/sportmonks/settings", {
    method: "PUT",
    body: JSON.stringify(input),
  });
}

export function saveSportmonksCredential(apiToken: string): Promise<SportmonksStatus> {
  return request<SportmonksStatus>("/api/v1/providers/sportmonks/credential", {
    method: "PUT",
    body: JSON.stringify({ api_token: apiToken }),
  });
}

export function deleteSportmonksCredential(): Promise<SportmonksStatus> {
  return request<SportmonksStatus>("/api/v1/providers/sportmonks/credential", {
    method: "DELETE",
  });
}

export const SPORTMONKS_RESET_EVENT = "golavo:sportmonks-reset";
const activeSportmonksRequests = new Set<AbortController>();

export function resetSportmonksClientState(): void {
  for (const controller of activeSportmonksRequests) controller.abort();
  activeSportmonksRequests.clear();
  if (typeof window !== "undefined") window.dispatchEvent(new Event(SPORTMONKS_RESET_EVENT));
}

export function fetchOutsideSignals(
  matchId: string,
  externalSignal?: AbortSignal,
): Promise<OutsideSignals> {
  // Deliberately bypasses api.ts's GET cache. A click is one fresh provider
  // capture; opening a match never starts this request.
  const controller = new AbortController();
  const abort = () => controller.abort();
  if (externalSignal?.aborted) abort();
  else externalSignal?.addEventListener("abort", abort, { once: true });
  activeSportmonksRequests.add(controller);
  return request<OutsideSignals>(
    `/api/v1/matches/${encodeURIComponent(matchId)}/outside-signals`,
    { cache: "no-store", signal: controller.signal },
  ).finally(() => {
    externalSignal?.removeEventListener("abort", abort);
    activeSportmonksRequests.delete(controller);
  });
}

export function fetchTeamTransfers(
  matchId: string,
  side: "home" | "away",
  externalSignal?: AbortSignal,
): Promise<TransferDeskResponse> {
  // Like outside signals, this is a bounded foreground capture with no shared
  // GET cache and no request on route mount.
  const controller = new AbortController();
  const abort = () => controller.abort();
  if (externalSignal?.aborted) abort();
  else externalSignal?.addEventListener("abort", abort, { once: true });
  activeSportmonksRequests.add(controller);
  return request<TransferDeskResponse>(
    `/api/v1/matches/${encodeURIComponent(matchId)}/transfers/${side}`,
    { cache: "no-store", signal: controller.signal },
  ).finally(() => {
    externalSignal?.removeEventListener("abort", abort);
    activeSportmonksRequests.delete(controller);
  });
}
