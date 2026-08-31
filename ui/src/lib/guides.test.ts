import { describe, expect, it } from "vitest";
import { guideForPath } from "./guides";

describe("guideForPath", () => {
  it.each([
    ["/", "Matchday guide"],
    ["/matches", "Search guide"],
    ["/match/m_1", "Match cockpit guide"],
    ["/forecast/f_1", "Forecast record guide"],
    ["/leagues", "Competition guide"],
    ["/league/premier-league", "Competition guide"],
    ["/season", "My Season guide"],
    ["/teams", "My Teams guide"],
    ["/team/england-premier-league/Exact%20Club", "Team dossier guide"],
    ["/transfers", "Transfer Desk guide"],
    ["/lab/track-record", "Model Lab guide"],
    ["/trust", "Trust Center guide"],
    ["/settings", "Control-room guide"],
  ])("maps %s to its contextual guide", (path, eyebrow) => {
    const guide = guideForPath(path);
    expect(guide.eyebrow).toBe(eyebrow);
    expect(guide.steps).toHaveLength(3);
    expect(guide.links.length).toBeGreaterThan(0);
  });

  it("falls back safely for an unknown route", () => {
    expect(guideForPath("/not-found").eyebrow).toBe("Matchday guide");
  });
});
