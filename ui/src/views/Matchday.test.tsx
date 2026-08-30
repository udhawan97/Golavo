// @vitest-environment jsdom
import { act } from "react";
import type { ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { MatchRow, MatchesWindowResponse } from "../lib/contract";
import { CompetitionSection, Rail, WindowBody } from "./Matchday";

vi.mock("../components/FollowButton", () => ({ FollowButton: () => null }));

let container: HTMLDivElement;
let root: Root;

function match(index: number, competition = "English Premier League"): MatchRow {
  return {
    match_id: `m_${competition.replaceAll(" ", "_")}_${index}`,
    kickoff_utc: `2026-09-${String(index + 1).padStart(2, "0")}T15:00:00Z`,
    kickoff_precision: "exact",
    home_team: `Home ${index}`,
    away_team: `Away ${index}`,
    home_score: null,
    away_score: null,
    competition,
    country: "Example",
    city: null,
    neutral: false,
    is_complete: false,
    source_kind: "club",
    source_id: "test-current-source",
    forecasts: [],
  };
}

beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
});

function render(node: ReactNode) {
  act(() => root.render(node));
}

describe("Matchday progressive disclosure", () => {
  it("pages a long league rail instead of rendering every match at once", () => {
    render(<Rail title="Upcoming" matches={Array.from({ length: 13 }, (_, index) => match(index))} emptyNote="None" />);
    expect(container.querySelectorAll(".game-card")).toHaveLength(12);
    const more = [...container.querySelectorAll("button")].find((button) => button.textContent?.includes("Show 1 more"));
    expect(more).toBeDefined();
    act(() => more?.click());
    expect(container.querySelectorAll(".game-card")).toHaveLength(13);
    expect(container.textContent).not.toContain("Show 1 more");
  });

  it("expands an uncatalogued competition locally", () => {
    const matches = Array.from({ length: 5 }, (_, index) => match(index, "Regional League"));
    render(<CompetitionSection competition="Regional League" sourceKind="club" matches={matches} picks={new Map()} />);
    expect(container.querySelectorAll(".game-card")).toHaveLength(4);
    const more = [...container.querySelectorAll("button")].find((button) => button.textContent?.includes("Show all 5"));
    expect(more).toBeDefined();
    act(() => more?.click());
    expect(container.querySelectorAll(".game-card")).toHaveLength(5);
  });

  it("reveals competition groups in stable curated batches", () => {
    const competitions = [
      "English Premier League",
      "La Liga",
      "Bundesliga",
      "Serie A",
      "Ligue 1",
    ];
    const matches = competitions.map((competition, index) => match(index, competition));
    const data: MatchesWindowResponse = {
      schema_version: "0.2.0",
      window: "upcoming",
      window_start_utc: null,
      window_end_utc: null,
      latest_result_utc: null,
      total: matches.length,
      matches,
      competitions: competitions.map((competition) => ({
        competition,
        source_kind: "club",
        n_matches: 1,
      })),
    };
    render(<WindowBody window="upcoming" state={{ status: "ready", data }} picks={new Map()} />);
    expect(container.querySelectorAll("h2.rail__title")).toHaveLength(3);
    expect(container.querySelector("h2.rail__title")?.textContent).toBe("English Premier League");
    const more = [...container.querySelectorAll("button")].find((button) => button.textContent?.includes("Show 2 more competitions"));
    expect(more).toBeDefined();
    act(() => more?.click());
    expect(container.querySelectorAll("h2.rail__title")).toHaveLength(5);
  });
});
