import { describe, expect, it } from "vitest";
import type { MatchRow } from "../lib/contract";
import { seasonOutlookCompetitionId } from "./CurrentSeasonMatchContext";
import { projectionCoverageCaveat } from "./SeasonOutlook";
import type { SeasonOutlookTeam } from "../lib/contract";

function match(competition: string, sourceKind: MatchRow["source_kind"] = "club"): MatchRow {
  return { competition, source_kind: sourceKind } as MatchRow;
}

describe("seasonOutlookCompetitionId", () => {
  it("maps every supported top-five domestic league", () => {
    expect(seasonOutlookCompetitionId(match("English Premier League"))).toBe("england-premier-league");
    expect(seasonOutlookCompetitionId(match("La Liga"))).toBe("spain-la-liga");
    expect(seasonOutlookCompetitionId(match("Bundesliga"))).toBe("germany-bundesliga");
    expect(seasonOutlookCompetitionId(match("Serie A"))).toBe("italy-serie-a");
    expect(seasonOutlookCompetitionId(match("Ligue 1"))).toBe("france-ligue-1");
  });

  it("does not claim unsupported or international competitions", () => {
    expect(seasonOutlookCompetitionId(match("UEFA Champions League"))).toBeNull();
    expect(seasonOutlookCompetitionId(match("English Premier League", "international"))).toBeNull();
  });

  it("carries the model-prior caveat into thin-history match context", () => {
    const projection = {
      history_coverage: { matches: 0, model_floor: 30, status: "below_model_floor" },
    } as SeasonOutlookTeam;
    expect(projectionCoverageCaveat(projection)).toContain("model’s prior");
    expect(projectionCoverageCaveat({
      ...projection,
      history_coverage: { matches: 40, model_floor: 30, status: "ok" },
    })).toBeNull();
  });
});
