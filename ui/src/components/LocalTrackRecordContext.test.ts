import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { CalibrationSummary, ForecastArtifact } from "../lib/contract";
import { LocalTrackRecordContext } from "./LocalTrackRecordContext";

const artifact = {
  match: { competition: "English Premier League" },
  model: { family: "elo_ordlogit" },
} as ForecastArtifact;
const slice = {
  n_scored: 31, metrics_status: "available", metrics: { log_loss: 1, brier: .6, prob_assigned_to_outcome: .5 },
  reliability_status: "held_back", reliability_bins: [],
  thresholds: { metrics_min_scored: 30, reliability_min_scored: 100, reliability_min_bin: 20, reliability_min_bins: 3 },
  caveat: "Descriptive local slice; not a model comparison.",
};

describe("LocalTrackRecordContext", () => {
  it("renders competition and family slices independently", () => {
    const calibration = {
      generated_from: "real local seals",
      slices: [
        { ...slice, dimension: "competition", key: "English Premier League" },
        { ...slice, dimension: "model_family", key: "elo_ordlogit" },
      ],
  } as unknown as CalibrationSummary;
    const html = renderToStaticMarkup(createElement(LocalTrackRecordContext, { artifact, calibration }));
    expect(html).toContain("English Premier League");
    expect(html).toContain("Elo ratings");
    expect(html).toContain("31 scored seals");
    expect(html).toContain("do not change this forecast");
  });

  it("does not turn an absent slice into a zero-count claim", () => {
    const html = renderToStaticMarkup(createElement(LocalTrackRecordContext, {
      artifact,
      calibration: { generated_from: "real local seals", slices: [] } as unknown as CalibrationSummary,
    }));
    expect(html).toContain("No matching scored-seal slice exists yet");
    expect(html).not.toContain("0 scored seals");
  });
});
