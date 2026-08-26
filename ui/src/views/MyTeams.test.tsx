// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MyTeams } from "./MyTeams";
import { fetchFollows, fetchSeasonOutlook } from "../lib/api";

vi.mock("../lib/api", () => ({ fetchFollows: vi.fn(), fetchSeasonOutlook: vi.fn() }));
vi.mock("../lib/picks", () => ({
  usePicks: () => ({
    byMatch: new Map([["m_run_in", {
      record: { user_pick: { home_goals: 2, away_goals: 1 } },
    }]]),
  }),
}));

let container: HTMLDivElement;
let root: Root;

function memoryStorage(): Storage {
  const values = new Map<string, string>();
  return {
    get length() { return values.size; },
    clear: () => values.clear(),
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => { values.set(key, String(value)); },
    removeItem: (key) => values.delete(key),
    key: (index) => [...values.keys()][index] ?? null,
  };
}

beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  Object.defineProperty(window, "localStorage", { value: memoryStorage(), configurable: true });
  vi.stubGlobal("localStorage", window.localStorage);
  localStorage.clear();
  localStorage.setItem("golavo.favorite-teams.v1", JSON.stringify([{
    competitionId: "england-premier-league",
    leagueSlug: "premier-league",
    leagueName: "Premier League",
    team: "Exact Club",
  }]));
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  vi.mocked(fetchFollows).mockResolvedValue({
    schema_version: "0.1.0", total: 1, unread_event_count: 0,
    items: [{ canonical_match_id: "m_run_in" }],
  } as never);
  vi.mocked(fetchSeasonOutlook).mockResolvedValue({
    schema_version: "0.3.0",
    status: "available",
    competition_id: "england-premier-league",
    current_table: [{
      position: 2, team: "Exact Club", played: 30, won: 18, drawn: 6, lost: 6,
      goals_for: 55, goals_against: 30, goal_difference: 25, points_adjustment: 0, points: 60,
    }],
    voices: [{
      voice_id: "elo_ordlogit", label: "Ratings", role: "voice", scoreline_method: "outcome",
      teams: [{
        team: "Exact Club", title: 0.2, top_four: 0.8, relegation: 0,
        expected_points: 74.2, display_percent: { title: 20, top_four: 80, relegation: 0 },
        history_coverage: { matches: 100, model_floor: 30, status: "ok" },
      }], totals: { title: 1, top_four: 4, relegation: 3 },
    }],
    remaining_fixtures: [{
      match_id: "m_run_in", kickoff_utc: "2026-09-01T18:30:00Z",
      home_team: "Exact Club", away_team: "Rival",
      importance: {
        voice_id: "elo_ordlogit", status: "ok", score: 0.05,
        coverage: { home_wins: 100, draws: 100, away_wins: 100 },
        clubs: [{
          team: "Exact Club", side: "home", score: 0.05,
          swings: { title: 0.05, top_four: 0.02, relegation: 0 },
        }, {
          team: "Rival", side: "away", score: 0.03,
          swings: { title: 0.01, top_four: 0.03, relegation: 0 },
        }],
      },
    }],
  } as never);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

describe("MyTeams", () => {
  it("composes importance, run-in, follow state, and the existing pick", async () => {
    await act(async () => root.render(<MyTeams />));
    expect(container.textContent).toContain("Projected 74.2 pts");
    expect(container.textContent).toContain("5pp title swing");
    expect(container.textContent).toContain("Followed");
    expect(container.textContent).toContain("Pick 2–1");
    expect(container.querySelector('a[href="#/match/m_run_in"]')).not.toBeNull();
  });

  it("loads every follow page before labeling run-in matches", async () => {
    vi.mocked(fetchFollows)
      .mockResolvedValueOnce({
        schema_version: "0.1.0", total: 201, unread_event_count: 0,
        items: Array.from({ length: 200 }, (_, index) => ({
          canonical_match_id: `earlier_${index}`,
        })),
      } as never)
      .mockResolvedValueOnce({
        schema_version: "0.1.0", total: 201, unread_event_count: 0,
        items: [{ canonical_match_id: "m_run_in" }],
      } as never);

    await act(async () => root.render(<MyTeams />));

    expect(fetchFollows).toHaveBeenNthCalledWith(1, "active", 0, 200, 0);
    expect(fetchFollows).toHaveBeenNthCalledWith(2, "active", 0, 200, 200);
    expect(container.textContent).toContain("Followed");
  });
});
