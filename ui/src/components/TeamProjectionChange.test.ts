// @vitest-environment jsdom
import { act, createElement, StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { SeasonOutlook } from "../lib/contract";
import {
  compareTeamProjectionSnapshots,
  TeamProjectionChange,
  teamProjectionSnapshot,
} from "./TeamProjectionChange";

const outlook = {
  status: "available", scenario: null, competition_id: "england-premier-league",
  season: "2026-27", simulation_rule: "season-mc-2026.07.1", seed: 7,
  iterations: 10_000, as_of_utc: "2026-08-29T00:00:00Z",
  provenance: { source_ids: ["openfootball"], index_sha256: "a".repeat(64) },
} as unknown as SeasonOutlook;
const voice = {
  voice_id: "elo_ordlogit" as const, label: "Ratings", role: "voice" as const,
  scoreline_method: "outcome", totals: { title: 1, top_four: 4, relegation: 3 },
  teams: [{
    team: "Arsenal", title: .2, top_four: .7, relegation: .01, expected_points: 74,
    display_percent: { title: 20, top_four: 70, relegation: 1 },
    history_coverage: { matches: 100, model_floor: 30, status: "ok" as const },
  }],
};

function memoryStorage(): Storage {
  const values = new Map<string, string>();
  return {
    get length() { return values.size; },
    clear: () => values.clear(),
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => { values.set(key, String(value)); },
    removeItem: (key) => { values.delete(key); },
    key: (index) => [...values.keys()][index] ?? null,
  };
}

describe("team projection comparisons", () => {
  beforeEach(() => {
    Object.defineProperty(window, "localStorage", { value: memoryStorage(), configurable: true });
    vi.stubGlobal("localStorage", window.localStorage);
  });
  afterEach(() => {
    localStorage.clear();
    vi.unstubAllGlobals();
  });
  it("compares only a changed index with an identical simulation identity", () => {
    const previous = teamProjectionSnapshot(outlook, voice, voice.teams[0])!;
    const current = {
      ...previous, indexSha256: "b".repeat(64), expectedPoints: 75.5,
      title: .25, topFour: .68,
    };
    const delta = compareTeamProjectionSnapshots(previous, current);
    expect(delta?.expectedPoints).toBeCloseTo(1.5);
    expect(delta?.title).toBeCloseTo(.05);
    expect(delta?.topFour).toBeCloseTo(-.02);
    expect(delta?.relegation).toBeCloseTo(0);
  });

  it("withholds comparisons after season or simulation identity drift", () => {
    const previous = teamProjectionSnapshot(outlook, voice, voice.teams[0])!;
    expect(compareTeamProjectionSnapshots(previous, {
      ...previous, season: "2027-28", indexSha256: "b".repeat(64),
    })).toBeNull();
    expect(compareTeamProjectionSnapshots(previous, {
      ...previous, iterations: 20_000, indexSha256: "b".repeat(64),
    })).toBeNull();
  });

  it("keeps a changed-index notice through StrictMode effect replay", async () => {
    const previous = teamProjectionSnapshot(outlook, voice, voice.teams[0])!;
    localStorage.setItem(
      "golavo:team-projection:england-premier-league:Arsenal",
      JSON.stringify(previous),
    );
    const changedOutlook = {
      ...outlook,
      provenance: { ...outlook.provenance, index_sha256: "b".repeat(64) },
    };
    const changedProjection = { ...voice.teams[0], expected_points: 75 };

    const container = document.createElement("div");
    document.body.appendChild(container);
    const root = createRoot(container);
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
    await act(async () => root.render(createElement(
      StrictMode,
      null,
      createElement(TeamProjectionChange, {
        outlook: changedOutlook,
        voice,
        projection: changedProjection,
      }),
    )));

    expect(container.textContent).toContain("Local projection change");
    act(() => root.unmount());
    container.remove();
  });

  it("replaces valid JSON with malformed snapshot fields without rendering a delta", async () => {
    const key = "golavo:team-projection:england-premier-league:Arsenal";
    localStorage.setItem(key, JSON.stringify({
      ...teamProjectionSnapshot(outlook, voice, voice.teams[0]),
      indexSha256: 7,
      title: "0.2",
    }));
    const changedOutlook = {
      ...outlook,
      provenance: { ...outlook.provenance, index_sha256: "b".repeat(64) },
    };
    const container = document.createElement("div");
    document.body.appendChild(container);
    const root = createRoot(container);
    await act(async () => root.render(createElement(TeamProjectionChange, {
      outlook: changedOutlook,
      voice,
      projection: voice.teams[0],
    })));

    expect(container.textContent).not.toContain("Local projection change");
    expect(JSON.parse(localStorage.getItem(key)!).indexSha256).toBe("b".repeat(64));
    act(() => root.unmount());
    container.remove();
  });
});
