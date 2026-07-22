import { describe, expect, it } from "vitest";
import type { MatchAnalysis, MatchDetailResponse } from "./contract";
import { forecastReadinessItems } from "./forecastReadiness";

describe("forecast readiness", () => {
  it("keeps missing live evidence as a boundary, never a confidence claim", () => {
    const detail = {
      match: { kickoff_precision: "day" },
      seal_eligibility: { eligible: false, detail: "kickoff is day precision" },
    } as unknown as MatchDetailResponse;
    const analysis = {
      uncertainty: "medium",
      explanation: { history_support: { level: "moderate" } },
    } as unknown as MatchAnalysis;
    const items = forecastReadinessItems(detail, analysis, "a".repeat(64));

    expect(items.find((item) => item.label === "Fixture timing")?.state).toBe("limited");
    expect(items.find((item) => item.label === "Known evidence boundary")).toEqual({
      label: "Known evidence boundary",
      state: "boundary",
      detail: "No verified lineups, injuries, or observed xG are claimed",
    });
  });
});
