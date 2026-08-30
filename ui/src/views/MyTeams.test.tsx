// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MyTeams } from "./MyTeams";
import { fetchSeasonOutlook } from "../lib/api";
import type { SeasonOutlook } from "../lib/contract";

vi.mock("../lib/api", () => ({ fetchSeasonOutlook: vi.fn() }));
vi.mock("../lib/follow-context", () => ({ useFollows: () => ({ error: null }) }));
vi.mock("../components/FollowButton", () => ({
  FollowButton: ({ matchId }: { matchId: string }) => <button type="button">Follow {matchId}</button>,
}));
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
  vi.mocked(fetchSeasonOutlook).mockResolvedValue({
    schema_version: "0.3.0",
    status: "available",
    competition_id: "england-premier-league",
    season: "2026-27",
    scenario: null,
    seed: 42,
    iterations: 10_000,
    simulation_rule: "season-mc-2026.07.1",
    as_of_utc: "2026-08-29T00:00:00Z",
    provenance: { source_ids: ["openligadb-v2"], index_sha256: "a".repeat(64) },
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
    expect(container.textContent).toContain("Follow m_run_in");
    expect(container.textContent).toContain("Pick 2–1");
    expect(container.querySelector('a[href="#/match/m_run_in"]')).not.toBeNull();
    const importInput = container.querySelector<HTMLInputElement>('input[type="file"]');
    expect(importInput?.classList.contains("visually-hidden")).toBe(true);
    expect(importInput?.hasAttribute("hidden")).toBe(false);
    importInput?.focus();
    expect(document.activeElement).toBe(importInput);
  });

  it("resets replacement intent for every newly inspected import", async () => {
    await act(async () => root.render(<MyTeams />));
    const input = container.querySelector<HTMLInputElement>('input[type="file"]')!;
    const transfer = JSON.stringify({
      schema_version: "0.1.0",
      favorites: [{ competitionId: "england-premier-league", team: "Exact Club" }],
    });
    const select = async (name: string) => {
      const file = new File([transfer], name, { type: "application/json" });
      Object.defineProperty(file, "text", { value: vi.fn().mockResolvedValue(transfer) });
      Object.defineProperty(input, "files", { configurable: true, value: [file] });
      await act(async () => input.dispatchEvent(new Event("change", { bubbles: true })));
    };
    await select("first.json");
    const replace = container.querySelector<HTMLInputElement>('input[type="checkbox"]')!;
    await act(async () => replace.click());
    expect(replace.checked).toBe(true);

    await select("second.json");

    expect(container.querySelector<HTMLInputElement>('input[type="checkbox"]')?.checked).toBe(false);
  });

  it("rejects an oversized import before reading its contents", async () => {
    await act(async () => root.render(<MyTeams />));
    const input = container.querySelector<HTMLInputElement>('input[type="file"]')!;
    const file = new File(["x".repeat(64 * 1024 + 1)], "oversized.json");
    const read = vi.fn();
    Object.defineProperty(file, "text", { value: read });
    Object.defineProperty(input, "files", { configurable: true, value: [file] });

    await act(async () => input.dispatchEvent(new Event("change", { bubbles: true })));

    expect(read).not.toHaveBeenCalled();
    expect(container.querySelector('[role="alert"]')?.textContent).toContain("larger than 64 KiB");
  });

  it("keeps the newest import preview and its replacement intent when an older read finishes late", async () => {
    await act(async () => root.render(<MyTeams />));
    const input = container.querySelector<HTMLInputElement>('input[type="file"]')!;
    const transfer = JSON.stringify({
      schema_version: "0.1.0",
      favorites: [{ competitionId: "england-premier-league", team: "Exact Club" }],
    });
    let resolveFirstText: ((value: string) => void) | null = null;
    const first = new File([transfer], "first.json", { type: "application/json" });
    Object.defineProperty(first, "text", {
      value: vi.fn(() => new Promise<string>((resolve) => { resolveFirstText = resolve; })),
    });
    const second = new File([transfer], "second.json", { type: "application/json" });
    Object.defineProperty(second, "text", { value: vi.fn().mockResolvedValue(transfer) });

    Object.defineProperty(input, "files", { configurable: true, value: [first] });
    await act(async () => input.dispatchEvent(new Event("change", { bubbles: true })));
    Object.defineProperty(input, "files", { configurable: true, value: [second] });
    await act(async () => input.dispatchEvent(new Event("change", { bubbles: true })));
    expect(container.textContent).toContain("Import preview · second.json");
    const replace = container.querySelector<HTMLInputElement>('input[type="checkbox"]')!;
    await act(async () => replace.click());
    expect(replace.checked).toBe(true);

    await act(async () => resolveFirstText?.(transfer));

    expect(container.textContent).toContain("Import preview · second.json");
    expect(container.textContent).not.toContain("Import preview · first.json");
    expect(container.querySelector<HTMLInputElement>('input[type="checkbox"]')?.checked).toBe(true);
  });

  it("labels below-floor club projections as model priors", async () => {
    const original = vi.mocked(fetchSeasonOutlook).getMockImplementation()!;
    vi.mocked(fetchSeasonOutlook).mockImplementation(async (id) => {
      const value = await original(id) as unknown as SeasonOutlook;
      return {
        ...value,
        voices: value.voices.map((item) => ({
          ...item,
          teams: item.teams.map((team) => ({
            ...team,
            history_coverage: {
              matches: 0,
              model_floor: 30,
              status: "below_model_floor" as const,
            },
          })),
        })),
      };
    });

    await act(async () => root.render(<MyTeams />));

    expect(container.textContent).toContain("model’s prior filling an evidence gap");
  });
});
