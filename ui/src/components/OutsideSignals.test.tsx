// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { OutsideSignals } from "./OutsideSignals";
import {
  fetchOutsideSignals,
  fetchSportmonksStatus,
  SPORTMONKS_RESET_EVENT,
  SportmonksApiError,
} from "../lib/sportmonks";

vi.mock("../lib/sportmonks", () => ({
  fetchSportmonksStatus: vi.fn(),
  fetchOutsideSignals: vi.fn(),
  SPORTMONKS_RESET_EVENT: "golavo:sportmonks-reset",
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
  capabilities: ["external_prediction", "external_odds", "player_lens"],
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
    provider_home_team: "Provider Home FC",
    provider_away_team: "Provider Away FC",
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
        unit: "count",
        value: 1,
      }, {
        type_id: 82,
        developer_name: "SUCCESSFUL_PASSES_PERCENTAGE",
        label: "Successful passes",
        group: "passing",
        unit: "percent",
        value: 76.5,
      }, {
        type_id: 119,
        developer_name: "MINUTES_PLAYED",
        label: "Minutes played",
        group: null,
        unit: "minutes",
        value: 90,
      }, {
        type_id: 40,
        developer_name: "CAPTAIN",
        label: "Captain",
        group: null,
        unit: "boolean",
        value: true,
      }, {
        type_id: 118,
        developer_name: "RATING",
        label: "Provider rating",
        group: null,
        unit: "provider_score",
        value: 7.4,
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
  it("uses final-stat wording for a completed fixture", async () => {
    await act(async () => {
      root.render(<OutsideSignals matchId="m_1" home="Home" away="Away" complete />);
    });
    expect(container.textContent).toContain("Fetch final player stats & outside signals");
    expect(fetchOutsideSignals).not.toHaveBeenCalled();
  });

  it.each([
    [["player_lens"], "Fetch final player stats"],
    [["external_prediction"], "Fetch outside signals"],
    [["external_prediction", "player_lens"], "Fetch final player stats & outside signals"],
  ])("derives completed-match actions from enabled capabilities", async (capabilities, expected) => {
    vi.mocked(fetchSportmonksStatus).mockResolvedValue({ ...status, capabilities } as never);
    await act(async () => {
      root.render(<OutsideSignals matchId="m_1" home="Home" away="Away" complete />);
    });
    const button = [...container.querySelectorAll("button")].find(
      (candidate) => candidate.textContent?.startsWith("Fetch"),
    );
    expect(button?.textContent).toBe(expected);
  });

  it("does not contact Sportmonks until the user clicks fetch", async () => {
    await renderPanel();
    expect(fetchSportmonksStatus).toHaveBeenCalledOnce();
    expect(fetchOutsideSignals).not.toHaveBeenCalled();
    expect(container.textContent).toContain("Fetch outside signals & player data");

    const button = [...container.querySelectorAll("button")].find(
      (candidate) => candidate.textContent === "Fetch outside signals & player data",
    );
    await act(async () => button?.click());

    expect(fetchOutsideSignals).toHaveBeenCalledOnce();
    expect(fetchOutsideSignals).toHaveBeenCalledWith("m_1", expect.any(AbortSignal));
    expect(container.textContent).toContain("45.0%");
    expect(container.textContent).toContain("Example Book");
    expect(container.textContent).toContain("Ada Forward");
    expect(container.textContent).toContain("Confirmed lineup");
    expect(container.textContent).toContain("No identity-safe lineup rows were supplied for this team");
    expect(container.textContent).toContain("Missing means unavailable");
    expect(container.textContent).toContain("Not a Golavo forecast");
    expect(container.textContent).toContain("raw response not stored");
    expect(container.textContent).toContain("Open dossier");
    expect(container.textContent).not.toContain("Selected-match dossier");

    const player = [...container.querySelectorAll("button")].find(
      (candidate) => candidate.textContent?.includes("Ada Forward"),
    );
    expect(player?.hasAttribute("aria-controls")).toBe(false);
    await act(async () => player?.click());

    expect(fetchOutsideSignals).toHaveBeenCalledOnce();
    expect(player?.getAttribute("aria-expanded")).toBe("true");
    expect(player?.getAttribute("aria-controls")).toBe("player-match-dossier-20");
    expect(document.activeElement).toBe(container.querySelector(".player-dossier"));
    expect(container.textContent).toContain("Selected-match dossier · exact provider identity");
    expect(container.textContent).toContain("Player ID20");
    expect(container.textContent).toContain("Lineup ID10");
    expect(container.textContent).toContain("Team ID1");
    expect(container.textContent).toContain("Fixture ID42");
    expect(container.textContent).toContain("Position ID27");
    expect(container.textContent).toContain("Provider Home FC · Starter");
    expect(container.textContent).toContain("Type 52");
    expect(container.textContent).toContain("Type 82");
    expect(container.textContent).toContain("1 count");
    expect(container.textContent).toContain("76.5%");
    expect(container.textContent).toContain("90 min");
    expect(container.textContent).toContain("Yes");
    expect(container.textContent).toContain("7.4 provider score");
    expect(container.textContent).toContain("This fixture only");
    expect(container.textContent).toContain("not a career profile, current-form series, player ranking, or Golavo assessment");
    expect(container.textContent).toContain("cannot enter a model, forecast, seal, settlement, score, calibration, AI read, or export");
  });

  it("focuses a dossier opened from the start of a full two-team roster", async () => {
    const players = Array.from({ length: 24 }, (_, index) => ({
      ...response.player_lens.players[0],
      lineup_id: 100 + index,
      player_id: 200 + index,
      team_id: index < 12 ? 1 : 2,
      name: `Roster Player ${index + 1}`,
      jersey_number: index + 1,
      metrics: index === 0 ? [] : response.player_lens.players[0].metrics,
    }));
    vi.mocked(fetchOutsideSignals).mockResolvedValue({
      ...response,
      player_lens: {
        ...response.player_lens,
        players,
        coverage: { player_count: 24, players_with_metrics: 23, missing_stat_is_zero: false },
      },
    } as never);
    await renderPanel();
    const fetchButton = [...container.querySelectorAll("button")].find(
      (candidate) => candidate.textContent === "Fetch outside signals & player data",
    );
    await act(async () => fetchButton?.click());
    const firstPlayer = [...container.querySelectorAll("button")].find(
      (candidate) => candidate.textContent?.includes("Roster Player 1"),
    );

    await act(async () => firstPlayer?.click());

    const dossier = container.querySelector<HTMLElement>(".player-dossier");
    expect(document.activeElement).toBe(dossier);
    expect(dossier?.textContent).toContain("No match statistics were supplied for this player");
    expect(dossier?.textContent).toContain("Their absence is not a zero");
  });

  it("closes a selected-match dossier without discarding the fetched roster", async () => {
    await renderPanel();
    const fetchButton = [...container.querySelectorAll("button")].find(
      (candidate) => candidate.textContent === "Fetch outside signals & player data",
    );
    await act(async () => fetchButton?.click());
    const player = [...container.querySelectorAll("button")].find(
      (candidate) => candidate.textContent?.includes("Ada Forward"),
    );
    await act(async () => player?.click());
    expect(container.textContent).toContain("Selected-match dossier");

    const close = [...container.querySelectorAll("button")].find(
      (candidate) => candidate.textContent === "Close dossier",
    );
    act(() => close?.focus());
    await act(async () => close?.click());

    expect(container.textContent).not.toContain("Selected-match dossier");
    expect(container.textContent).toContain("Ada Forward");
    expect(fetchOutsideSignals).toHaveBeenCalledOnce();
    expect(document.activeElement).toBe(player);
  });

  it("clears the selected dossier on a same-timestamp foreground refresh", async () => {
    await renderPanel();
    const fetchButton = [...container.querySelectorAll("button")].find(
      (candidate) => candidate.textContent === "Fetch outside signals & player data",
    );
    await act(async () => fetchButton?.click());
    const player = [...container.querySelectorAll("button")].find(
      (candidate) => candidate.textContent?.includes("Ada Forward"),
    );
    await act(async () => player?.click());
    expect(container.textContent).toContain("Selected-match dossier");

    const refresh = [...container.querySelectorAll("button")].find(
      (candidate) => candidate.textContent === "Refresh outside signals & player data",
    );
    await act(async () => refresh?.click());

    expect(fetchOutsideSignals).toHaveBeenCalledTimes(2);
    expect(container.textContent).not.toContain("Selected-match dossier");
    expect(container.textContent).toContain("Open dossier");
  });

  it("clears prior provider evidence when a foreground refresh fails", async () => {
    await renderPanel();
    const fetchButton = [...container.querySelectorAll("button")].find(
      (candidate) => candidate.textContent === "Fetch outside signals & player data",
    );
    await act(async () => fetchButton?.click());
    expect(container.textContent).toContain("45.0%");
    expect(container.textContent).toContain("Ada Forward");

    vi.mocked(fetchOutsideSignals).mockRejectedValueOnce(new Error("provider transport failed"));
    const refresh = [...container.querySelectorAll("button")].find(
      (candidate) => candidate.textContent === "Refresh outside signals & player data",
    );
    await act(async () => refresh?.click());

    expect(fetchOutsideSignals).toHaveBeenCalledTimes(2);
    expect(container.textContent).not.toContain("45.0%");
    expect(container.textContent).not.toContain("Ada Forward");
    expect(container.textContent).toContain("Outside signals unavailable: provider transport failed");
    expect(container.textContent).toContain("Fetch outside signals & player data");
  });

  it("clears an open dossier when navigation selects a different match", async () => {
    await renderPanel();
    const fetchButton = [...container.querySelectorAll("button")].find(
      (candidate) => candidate.textContent === "Fetch outside signals & player data",
    );
    await act(async () => fetchButton?.click());
    const player = [...container.querySelectorAll("button")].find(
      (candidate) => candidate.textContent?.includes("Ada Forward"),
    );
    await act(async () => player?.click());
    expect(container.textContent).toContain("Selected-match dossier");

    await renderPanel("m_2", "Second Home", "Second Away");

    expect(container.textContent).not.toContain("Selected-match dossier");
    expect(container.textContent).not.toContain("Ada Forward");
    expect(container.textContent).toContain("Second Home, Second Away");
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
      (candidate) => candidate.textContent === "Fetch outside signals & player data",
    );
    await act(async () => button?.click());

    expect(container.textContent).toContain("Review the credential and plan");
    expect(container.querySelector('a[href="#/settings"]')).not.toBeNull();
    expect(container.textContent).not.toContain("Fetch outside signals & player data");
    },
  );

  it("does not render a late response under a newly selected match", async () => {
    let resolveFirst: ((value: typeof response) => void) | null = null;
    vi.mocked(fetchOutsideSignals).mockImplementationOnce(() => new Promise((resolve) => {
      resolveFirst = resolve as (value: typeof response) => void;
    }) as never);
    await renderPanel();
    const button = [...container.querySelectorAll("button")].find(
      (candidate) => candidate.textContent === "Fetch outside signals & player data",
    );
    act(() => button?.click());
    const signal = vi.mocked(fetchOutsideSignals).mock.calls[0][1];
    expect(signal?.aborted).toBe(false);

    await renderPanel("m_2", "Second Home", "Second Away");
    expect(signal?.aborted).toBe(true);
    await act(async () => resolveFirst?.(response));

    expect(container.textContent).not.toContain("Ada Forward");
    expect(container.textContent).toContain("Fetch outside signals & player data");
    expect(container.textContent).toContain("Second Home, Second Away");
  });

  it("clears in-memory provider state when the connector is reset", async () => {
    await renderPanel();
    const button = [...container.querySelectorAll("button")].find(
      (candidate) => candidate.textContent === "Fetch outside signals & player data",
    );
    await act(async () => button?.click());
    expect(container.textContent).toContain("Ada Forward");
    const player = [...container.querySelectorAll("button")].find(
      (candidate) => candidate.textContent?.includes("Ada Forward"),
    );
    await act(async () => player?.click());
    expect(container.textContent).toContain("Selected-match dossier");

    act(() => window.dispatchEvent(new Event(SPORTMONKS_RESET_EVENT)));

    expect(container.innerHTML).toBe("");
  });
});
