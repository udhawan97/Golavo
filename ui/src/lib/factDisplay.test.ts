import { describe, expect, it } from "vitest";
import { FACT_CATEGORY, FACT_DISPLAY } from "./contract";

describe("fact display metadata", () => {
  it("gives every registered fact category a plain-language title and explainer", () => {
    for (const id of Object.keys(FACT_CATEGORY)) {
      expect(FACT_DISPLAY[id]?.title, `${id} title`).toBeTruthy();
      expect(FACT_DISPLAY[id]?.explainer, `${id} explainer`).toBeTruthy();
    }
  });

  it("keeps signature-stat language understandable without football jargon", () => {
    expect(FACT_DISPLAY.both_teams_scored_rate.explainer).toContain("each side found the net");
    expect(FACT_DISPLAY.clean_sheet_rate.explainer).toContain("stopped the opposition from scoring");
    expect(FACT_DISPLAY.scoring_trend.explainer).toContain("goals per game");
  });
});
