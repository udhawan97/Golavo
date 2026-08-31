import { describe, expect, it } from "vitest";
import { parseTeamDossierPath, teamDossierHref } from "./team-route";

describe("teamDossierHref", () => {
  it("keeps the competition and exact team identity as separate encoded segments", () => {
    const href = teamDossierHref("england-premier-league", "Brighton & Hove/Albion");
    expect(href).toBe("#/team/england-premier-league/Brighton%20%26%20Hove%2FAlbion");

    expect(parseTeamDossierPath(href.slice(1))).toEqual({
      competitionId: "england-premier-league",
      team: "Brighton & Hove/Albion",
    });
  });

  it("round-trips Unicode and percent signs through the parser used by App", () => {
    const href = teamDossierHref("deutschland-bundesliga", "1. FC Köln 100%");
    expect(parseTeamDossierPath(href.slice(1))).toEqual({
      competitionId: "deutschland-bundesliga",
      team: "1. FC Köln 100%",
    });
  });

  it("keeps malformed escapes inert instead of throwing during routing", () => {
    expect(parseTeamDossierPath("/team/england-premier-league/%")).toEqual({
      competitionId: "england-premier-league",
      team: "%",
    });
    expect(parseTeamDossierPath("/team/missing-team")).toBeNull();
  });
});
