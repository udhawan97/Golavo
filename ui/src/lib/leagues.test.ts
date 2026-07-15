import { describe, expect, it } from "vitest";
import type { MatchRow } from "./contract";
import { LEAGUES, competitionRank, groupMatchesByCompetition, leagueSlugFor } from "./leagues";

describe("league analytics identities", () => {
  it("gives every bundled club competition a stable backend competition id", () => {
    const clubs = LEAGUES.filter((league) => league.competition);
    expect(clubs).toHaveLength(8);
    expect(clubs.every((league) => league.competitionId?.includes("-"))).toBe(true);
    expect(new Set(clubs.map((league) => league.competitionId)).size).toBe(8);
  });
});

describe("competitionRank", () => {
  it("orders top-5 club leagues in their curated order", () => {
    expect(competitionRank("English Premier League", "club")).toBeLessThan(
      competitionRank("La Liga", "club"),
    );
    expect(competitionRank("La Liga", "club")).toBeLessThan(
      competitionRank("Ligue 1", "club"),
    );
  });

  it("ranks major internationals after the big-five clubs", () => {
    expect(competitionRank("Ligue 1", "club")).toBeLessThan(
      competitionRank("FIFA World Cup", "international"),
    );
  });

  it("ranks the World Cup ahead of an unlisted competition", () => {
    expect(competitionRank("FIFA World Cup", "international")).toBeLessThan(
      competitionRank("Some Regional Cup", "international"),
    );
  });

  it("pins Friendly dead last", () => {
    const friendly = competitionRank("Friendly", "international");
    expect(friendly).toBeGreaterThan(competitionRank("Some Regional Cup", "club"));
    expect(friendly).toBeGreaterThan(competitionRank("AFC Asian Cup qualification", "international"));
  });
});

describe("leagueSlugFor", () => {
  it("maps a big-five competition to its slug", () => {
    expect(leagueSlugFor("English Premier League", "club")).toBe("premier-league");
    expect(leagueSlugFor("Bundesliga", "club")).toBe("bundesliga");
    expect(leagueSlugFor("UEFA Champions League", "club")).toBe("champions-league");
  });
  it("maps any international to the internationals hub", () => {
    expect(leagueSlugFor("FIFA World Cup", "international")).toBe("internationals");
  });
  it("returns null for an unknown club competition", () => {
    expect(leagueSlugFor("Championship", "club")).toBeNull();
  });
});

function row(id: string, competition: string, source_kind: "club" | "international"): MatchRow {
  return {
    match_id: id, kickoff_utc: "2024-06-10T00:00:00Z", home_team: "H", away_team: "A",
    home_score: 1, away_score: 0, competition, country: "C", city: "C",
    neutral: false, is_complete: true, source_kind, source_id: "s", forecasts: [],
  } as MatchRow;
}

describe("groupMatchesByCompetition", () => {
  it("groups by competition and orders by curated priority", () => {
    const groups = groupMatchesByCompetition([
      row("1", "Friendly", "international"),
      row("2", "English Premier League", "club"),
      row("3", "FIFA World Cup", "international"),
      row("4", "La Liga", "club"),
    ]);
    expect(groups.map((g) => g.competition)).toEqual([
      "English Premier League", "La Liga", "FIFA World Cup", "Friendly",
    ]);
  });

  it("keeps every match and preserves within-group order", () => {
    const groups = groupMatchesByCompetition([
      row("a", "La Liga", "club"),
      row("b", "La Liga", "club"),
    ]);
    expect(groups).toHaveLength(1);
    expect(groups[0].matches.map((m) => m.match_id)).toEqual(["a", "b"]);
  });

  it("breaks equal-rank ties alphabetically", () => {
    const groups = groupMatchesByCompetition([
      row("1", "Zeta Cup", "club"),
      row("2", "Alpha Cup", "club"),
    ]);
    expect(groups.map((g) => g.competition)).toEqual(["Alpha Cup", "Zeta Cup"]);
  });
});
