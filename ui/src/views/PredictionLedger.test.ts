import { describe, expect, it } from "vitest";
import type { CalibrationChain, ReliabilityBin } from "../lib/contract";
import { pendingResolutionLabel, reliabilityReadiness } from "./PredictionLedger";

const chain: CalibrationChain = {
  sealed_artifact_id: "fa_test",
  match: {
    match_id: "m_test",
    home_team: "France",
    away_team: "Spain",
    competition: "FIFA World Cup",
    kickoff_utc: "2026-07-14T19:00:00Z",
    neutral_venue: true,
    city: "Arlington",
    country: "United States",
  },
  sealed_at_utc: "2026-07-13T05:56:16Z",
  horizon: "T-24h",
  family: "dixon_coles",
  abstained: false,
  probs: { home: 0.307, draw: 0.277, away: 0.416 },
  resolution: {
    status: "pending",
    artifact_id: null,
    resolved_at_utc: null,
    actual: null,
    metrics: null,
    void_reason: null,
  },
};

describe("pendingResolutionLabel", () => {
  it("separates upcoming, in-progress, and overdue result states", () => {
    expect(pendingResolutionLabel(chain, Date.parse("2026-07-14T18:00:00Z"))).toBe(
      "awaiting full time",
    );
    expect(pendingResolutionLabel(chain, Date.parse("2026-07-14T20:00:00Z"))).toBe(
      "match in progress",
    );
    expect(pendingResolutionLabel(chain, Date.parse("2026-07-14T22:00:00Z"))).toBe(
      "result check needed",
    );
  });

  it("surfaces the exact source settlement reason", () => {
    expect(pendingResolutionLabel(chain, Date.now(), "result_not_published")).toBe(
      "result not published",
    );
    expect(pendingResolutionLabel(chain, Date.now(), "source_conflict")).toBe(
      "source conflict",
    );
    expect(pendingResolutionLabel(chain, Date.now(), "scoring_refused")).toBe(
      "review needed",
    );
  });
});

const bin = (count: number): ReliabilityBin => ({
  lower: 0,
  upper: 0.1,
  count,
  mean_confidence: count ? 0.05 : null,
  accuracy: count ? 0.05 : null,
  wilson_low: count ? 0.01 : null,
  wilson_high: count ? 0.1 : null,
});

describe("reliabilityReadiness", () => {
  it("requires 100 scored seals and three bins with at least 20 observations", () => {
    expect(reliabilityReadiness(99, [bin(20), bin(20), bin(20)]).ready).toBe(false);
    expect(reliabilityReadiness(100, [bin(20), bin(20), bin(19)]).ready).toBe(false);
    expect(reliabilityReadiness(100, [bin(20), bin(21), bin(22)])).toEqual({
      ready: true,
      qualifyingBins: 3,
    });
  });
});
