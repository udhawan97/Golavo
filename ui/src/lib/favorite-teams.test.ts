import { beforeAll, beforeEach, describe, expect, it } from "vitest";
import { loadFavoriteTeams, saveFavoriteTeams } from "./favorite-teams";

beforeAll(() => {
  const values = new Map<string, string>();
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: {
      clear: () => values.clear(),
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value),
      removeItem: (key: string) => values.delete(key),
    },
  });
});

describe("favorite team identities", () => {
  beforeEach(() => localStorage.clear());

  it("round-trips exact competition and team identities locally", () => {
    const favorites = [{
      competitionId: "england-premier-league",
      leagueSlug: "premier-league",
      leagueName: "Premier League",
      team: "Liverpool FC",
    }];
    saveFavoriteTeams(favorites);
    expect(loadFavoriteTeams()).toEqual(favorites);
  });

  it("rejects malformed stored identities rather than guessing", () => {
    localStorage.setItem("golavo.favorite-teams.v1", JSON.stringify([
      { competitionId: "england-premier-league", team: "Liverpool FC" },
    ]));
    expect(loadFavoriteTeams()).toEqual([]);
  });
});
