import { describe, expect, it } from "vitest";
import { diffAnalysisGenerations } from "./analysisDiff";

describe("verified-generation analysis diff", () => {
  it("compares only matching voices and sorts the largest movement first", () => {
    const changes = diffAnalysisGenerations(
      { indexSha256: "a", voices: { elo: { home: 0.4, draw: 0.3, away: 0.3 } } },
      { indexSha256: "b", voices: { elo: { home: 0.45, draw: 0.29, away: 0.26 } } },
    );
    expect(changes.map((change) => [change.outcome, change.percentagePoints])).toEqual([
      ["home", 5], ["away", -4], ["draw", -1],
    ]);
  });

  it("emits no movement inside the same verified generation", () => {
    const snapshot = { indexSha256: "same", voices: {} };
    expect(diffAnalysisGenerations(snapshot, snapshot)).toEqual([]);
  });
});
