import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { CurrentSeasonPulse } from "../lib/contract";
import { CurrentSeasonPulsePanel } from "./Leagues";

describe("CurrentSeasonPulsePanel", () => {
  it("opens each form row through its competition-scoped exact team identity", () => {
    const pulse = {
      status: "available",
      reason: null,
      season: "2026-27",
      teams: [{
        team: "Brighton & Hove/Albion",
        played: 3,
        won: 2,
        drawn: 1,
        lost: 0,
        goals_for: 7,
        goals_against: 2,
        clean_sheets: 2,
        both_teams_scored: 1,
        recent_form: ["W", "W", "D"],
        points_per_game: 2.33,
        goals_for_per_match: 2.33,
        goals_against_per_match: 0.67,
      }],
    } satisfies CurrentSeasonPulse;

    const html = renderToStaticMarkup(
      <CurrentSeasonPulsePanel
        pulse={pulse}
        competitionId="england-premier-league"
      />,
    );

    expect(html).toContain(
      'href="#/team/england-premier-league/Brighton%20%26%20Hove%2FAlbion"',
    );
  });
});
