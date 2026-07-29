/**
 * The scope list the ratings page offers.
 *
 * Every club option is sent to /api/v1/ratings/club/{id}, which refuses a
 * competition whose teams are not clubs with a 400. So an international
 * competition leaking into this list is not a cosmetic slip — it is a menu
 * entry that can only ever error.
 */
import { describe, expect, it } from "vitest";
import { RATING_SCOPES } from "./Ratings";
import { LEAGUES } from "../lib/leagues";

describe("RATING_SCOPES", () => {
  it("offers the single national-team pool first", () => {
    expect(RATING_SCOPES[0]).toEqual({
      id: "internationals",
      name: "Internationals",
      club: false,
    });
  });

  it("marks every other scope as a club competition", () => {
    expect(RATING_SCOPES.slice(1).every((scope) => scope.club)).toBe(true);
  });

  it("never offers an international competition as a club scope", () => {
    const internationalIds = new Set(
      LEAGUES.filter((league) => league.sourceKind === "international")
        .map((league) => league.competitionId)
        .filter(Boolean),
    );
    const clubIds = RATING_SCOPES.filter((scope) => scope.club).map((scope) => scope.id);
    expect(clubIds.filter((id) => internationalIds.has(id))).toEqual([]);
  });

  it("covers the five domestic leagues and the three UEFA club competitions", () => {
    const clubIds = RATING_SCOPES.filter((scope) => scope.club).map((scope) => scope.id);
    expect(clubIds).toEqual([
      "england-premier-league",
      "spain-la-liga",
      "germany-bundesliga",
      "italy-serie-a",
      "france-ligue-1",
      "uefa-champions-league",
      "uefa-europa-league",
      "uefa-conference-league",
    ]);
  });
});
