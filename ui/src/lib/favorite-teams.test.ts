import { beforeAll, beforeEach, describe, expect, it } from "vitest";
import {
  favoriteTeamsTransferJson,
  loadFavoriteTeams,
  parseFavoriteTeamsTransfer,
  saveFavoriteTeams,
} from "./favorite-teams";

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

  it("exports only canonical identities and round-trips the versioned file", () => {
    const text = favoriteTeamsTransferJson([{
      competitionId: "england-premier-league",
      leagueSlug: "premier-league",
      leagueName: "Premier League",
      team: "Arsenal",
    }]);
    expect(text).not.toContain("leagueSlug");
    expect(text).not.toContain("leagueName");
    expect(parseFavoriteTeamsTransfer(text).favorites).toEqual([{
      competitionId: "england-premier-league",
      team: "Arsenal",
    }]);
  });

  it("rejects imported metadata and duplicate exact identities", () => {
    expect(() => parseFavoriteTeamsTransfer(JSON.stringify({
      schema_version: "0.1.0",
      favorites: [{ competitionId: "england-premier-league", team: "Arsenal", leagueName: "Trust me" }],
    }))).toThrow("contain only an exact competitionId and team");
    expect(() => parseFavoriteTeamsTransfer(JSON.stringify({
      schema_version: "0.1.0",
      favorites: [
        { competitionId: "england-premier-league", team: "Arsenal" },
        { competitionId: "england-premier-league", team: "Arsenal" },
      ],
    }))).toThrow("duplicates an earlier club");
  });
});
