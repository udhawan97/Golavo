// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { OutsideSignals } from "./OutsideSignals";
import {
  fetchOutsideSignals,
  fetchSportmonksStatus,
  SportmonksApiError,
} from "../lib/sportmonks";

vi.mock("../lib/sportmonks", () => ({
  fetchSportmonksStatus: vi.fn(),
  fetchOutsideSignals: vi.fn(),
  SportmonksApiError: class extends Error {
    constructor(
      message: string,
      readonly status: number,
      readonly reasonCode: string,
    ) {
      super(message);
    }
  },
}));

let container: HTMLDivElement;
let root: Root;

const status = {
  enabled: true,
  credential: { configured: true },
  provider: {
    docs_url: "https://docs.sportmonks.com/v3/",
    terms_url: "https://www.sportmonks.com/terms-of-service/",
  },
};

const response = {
  schema_version: "0.1.0",
  status: "available",
  label: "Outside signals — not a Golavo forecast.",
  provider: { source_id: "sportmonks-v3", name: "Sportmonks", docs_url: status.provider.docs_url, terms_url: status.provider.terms_url },
  identity: {
    golavo_match_id: "m_1",
    provider_fixture_id: 42,
    provider_home_team_id: 1,
    provider_away_team_id: 2,
    provider_home_team: "Home",
    provider_away_team: "Away",
    provider_league_id: 8,
    provider_league: "Premier League",
    provider_season_id: 202627,
    provider_season: "2026/2027",
    provider_kickoff_utc: "2026-08-20T18:00:00Z",
    match_method: "exact_competition_season_teams_and_kickoff",
  },
  prediction: {
    status: "available",
    prediction_id: 7,
    type_id: 237,
    label: "Full-time result",
    percent: { home: 45, draw: 30, away: 25 },
  },
  odds: {
    status: "available",
    market: "Match Winner",
    format: "decimal",
    bookmakers: [{
      bookmaker_id: 3,
      bookmaker_name: "Example Book",
      market_id: 1,
      market: "Match Winner",
      updated_at_utc: "2026-08-20T17:00:00Z",
      decimal: { home: 2.1, draw: 3.3, away: 3.8 },
    }],
  },
  player_lens: {
    status: "available",
    lineup_state: "confirmed",
    players: [{
      lineup_id: 10,
      player_id: 20,
      team_id: 1,
      name: "Ada Forward",
      jersey_number: 9,
      position_id: 27,
      participation: "starter",
      metrics: [{
        type_id: 52,
        developer_name: "GOALS",
        label: "Goals",
        group: "offensive",
        value: 1,
      }],
    }],
    coverage: { player_count: 1, players_with_metrics: 1, missing_stat_is_zero: false },
  },
  provenance: {
    fetched_at_utc: "2026-08-20T17:05:00Z",
    terms_acceptance_version: "sportmonks-terms-reviewed-2026-08-29",
    raw_response_sha256: {},
    raw_response_storage: "not_persisted",
    model_input: false,
  },
};

beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  vi.mocked(fetchSportmonksStatus).mockResolvedValue(status as never);
  vi.mocked(fetchOutsideSignals).mockResolvedValue(response as never);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
  vi.clearAllMocks();
});

async function renderPanel(matchId = "m_1", home = "Home", away = "Away") {
  await act(async () => {
    root.render(<OutsideSignals matchId={matchId} home={home} away={away} />);
  });
}

describe("OutsideSignals", () => {
  it("does not contact Sportmonks until the user clicks fetch", async () => {
    await renderPanel();
    expect(fetchSportmonksStatus).toHaveBeenCalledOnce();
    expect(fetchOutsideSignals).not.toHaveBeenCalled();
    expect(container.textContent).toContain("Fetch outside signals");

    const button = [...container.querySelectorAll("button")].find(
      (candidate) => candidate.textContent === "Fetch outside signals",
    );
    await act(async () => button?.click());

    expect(fetchOutsideSignals).toHaveBeenCalledOnce();
    expect(fetchOutsideSignals).toHaveBeenCalledWith("m_1");
    expect(container.textContent).toContain("45.0%");
    expect(container.textContent).toContain("Example Book");
    expect(container.textContent).toContain("Ada Forward");
    expect(container.textContent).toContain("Confirmed lineup");
    expect(container.textContent).toContain("No identity-safe lineup rows were supplied for this team");
    expect(container.textContent).toContain("Missing means unavailable");
    expect(container.textContent).toContain("Not a Golavo forecast");
    expect(container.textContent).toContain("raw response not stored");
  });

  it("does not render a provider panel while the connector is disabled", async () => {
    vi.mocked(fetchSportmonksStatus).mockResolvedValue({ ...status, enabled: false } as never);
    await renderPanel();
    expect(container.innerHTML).toBe("");
    expect(fetchOutsideSignals).not.toHaveBeenCalled();
  });

  it.each([401, 403])(
    "stops retrying and routes to settings on provider HTTP %s",
    async (statusCode) => {
    vi.mocked(fetchOutsideSignals).mockRejectedValue(
      new SportmonksApiError(
        "Sportmonks rejected the token or plan",
        statusCode,
        statusCode === 401 ? "credential_rejected" : "plan_missing",
      ),
    );
    await renderPanel();
    const button = [...container.querySelectorAll("button")].find(
      (candidate) => candidate.textContent === "Fetch outside signals",
    );
    await act(async () => button?.click());

    expect(container.textContent).toContain("Review the credential and plan");
    expect(container.querySelector('a[href="#/settings"]')).not.toBeNull();
    expect(container.textContent).not.toContain("Fetch outside signals");
    },
  );

  it("does not render a late response under a newly selected match", async () => {
    let resolveFirst: ((value: typeof response) => void) | null = null;
    vi.mocked(fetchOutsideSignals).mockImplementationOnce(() => new Promise((resolve) => {
      resolveFirst = resolve as (value: typeof response) => void;
    }) as never);
    await renderPanel();
    const button = [...container.querySelectorAll("button")].find(
      (candidate) => candidate.textContent === "Fetch outside signals",
    );
    act(() => button?.click());

    await renderPanel("m_2", "Second Home", "Second Away");
    await act(async () => resolveFirst?.(response));

    expect(container.textContent).not.toContain("Ada Forward");
    expect(container.textContent).toContain("Fetch outside signals");
    expect(container.textContent).toContain("Second Home, Second Away");
  });
});
