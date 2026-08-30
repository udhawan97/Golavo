// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fetchRecentMatches } from "../lib/api";
import { fetchSportmonksStatus, fetchTeamTransfers } from "../lib/sportmonks";
import { buildTransferClubOptions, Transfers } from "./Transfers";

vi.mock("../lib/api", () => ({ fetchRecentMatches: vi.fn() }));
vi.mock("../lib/sportmonks", () => ({
  fetchSportmonksStatus: vi.fn(),
  fetchTeamTransfers: vi.fn(),
  SPORTMONKS_RESET_EVENT: "golavo:sportmonks-reset",
  SportmonksApiError: class extends Error {
    constructor(message: string, readonly status: number, readonly reasonCode: string) {
      super(message);
    }
  },
}));

const match = {
  match_id: "m-club",
  kickoff_utc: "2026-09-01T18:00:00Z",
  kickoff_precision: "exact",
  home_team: "Alpha FC",
  away_team: "Beta FC",
  home_score: null,
  away_score: null,
  competition: "English Premier League",
  country: "England",
  city: "London",
  neutral: false,
  is_complete: false,
  source_kind: "club",
  source_id: "openfootball-england",
  forecasts: [],
};

const directory = { schema_version: "0.2.0", upcoming: [match], recent: [] };
const status = {
  enabled: true,
  capabilities: ["external_prediction", "transfer_desk"],
  terms_acceptance_version: "terms-current",
  connector_supported: true,
  credential: { configured: true },
  provider: {
    terms_acceptance_version: "terms-current",
    docs_url: "https://docs.sportmonks.com/v3/",
  },
};
const response = {
  schema_version: "0.1.0",
  status: "available",
  label: "Provider transfer records — not Golavo model evidence.",
  provider: {
    source_id: "sportmonks-v3",
    name: "Sportmonks",
    docs_url: "https://docs.sportmonks.com/v3/",
    terms_url: "https://www.sportmonks.com/terms-of-service/",
  },
  identity: {
    golavo_match_id: "m-club",
    golavo_team: "Alpha FC",
    golavo_side: "home",
    provider_fixture_id: 42,
    provider_team_id: 14,
    provider_team: "Alpha FC",
    provider_league_id: 8,
    provider_season_id: 202627,
    match_method: "exact_competition_season_teams_and_kickoff",
  },
  transfers: [{
    transfer_id: 31,
    direction: "arrival",
    date: "2026-08-01",
    completed: true,
    player: { id: 6031, name: "Ada Forward" },
    type: { id: 220, name: "Transfer" },
    from_team: { id: 7, name: "Gamma FC" },
    to_team: { id: 14, name: "Alpha FC" },
    position: { id: 27, name: "Forward" },
    provider_reported_amount: "€42m",
    amount_label: "Provider-reported amount — currency unspecified",
    payment_breakdown: {
      status: "unavailable",
      reason_code: "provider_fields_not_reported",
      currency: null,
      installments: null,
      add_ons: null,
      sell_on_terms: null,
      agent_or_intermediary_fees: null,
      training_rewards: null,
      conditional_consideration: null,
    },
  }],
  coverage: {
    window_start: "2025-08-30",
    window_end: "2026-08-30",
    window_days: 365,
    pages_fetched: 1,
    page_limit: 4,
    rows_per_page_limit: 50,
    truncated: false,
  },
  provenance: {
    fetched_at_utc: "2026-08-30T12:00:00Z",
    terms_acceptance_version: "terms-current",
    raw_response_sha256: { fixture_pages: ["a".repeat(64)], transfer_pages: ["e".repeat(64)] },
    raw_response_storage: "not_persisted",
  },
  usage: {
    display: true,
    model_input: false,
    forecast_sealing: false,
    forecast_settlement: false,
    calibration: false,
    scoring: false,
    ai_evidence: false,
    exports: false,
  },
};

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  vi.mocked(fetchRecentMatches).mockResolvedValue(directory as never);
  vi.mocked(fetchSportmonksStatus).mockResolvedValue(status as never);
  vi.mocked(fetchTeamTransfers).mockResolvedValue(response as never);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
  vi.clearAllMocks();
});

describe("Transfer Desk", () => {
  it("builds one stable club choice per exact local identity", () => {
    const options = buildTransferClubOptions({
      ...directory,
      recent: [{ ...match, match_id: "m-older", is_complete: true, home_score: 2, away_score: 1 }],
    } as never);
    expect(options.map(({ team, matchId, side }) => ({ team, matchId, side }))).toEqual([
      { team: "Alpha FC", matchId: "m-club", side: "home" },
      { team: "Beta FC", matchId: "m-club", side: "away" },
    ]);
  });

  it("waits for an explicit click and never invents payment components", async () => {
    await act(async () => { root.render(<Transfers />); });
    expect(fetchTeamTransfers).not.toHaveBeenCalled();
    expect(container.textContent).toContain("No provider request has been made yet");

    const select = container.querySelector("select");
    if (!select) throw new Error("missing club selector");
    await act(async () => {
      select.value = "English Premier League::Alpha FC";
      select.dispatchEvent(new Event("change", { bubbles: true }));
    });
    const button = [...container.querySelectorAll("button")].find(
      (candidate) => candidate.textContent === "Fetch transfer window",
    );
    await act(async () => button?.click());

    expect(fetchTeamTransfers).toHaveBeenCalledWith("m-club", "home", expect.any(AbortSignal));
    expect(container.textContent).toContain("Ada Forward");
    expect(container.textContent).toContain("€42m");
    expect(container.textContent).toContain("currency unspecified");
    expect(container.textContent).toContain("Payment structure · not reported");
    expect(container.textContent).not.toContain("installment estimate");
    expect(container.textContent).toContain("raw responses not stored");
  });
});
