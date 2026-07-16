import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { ForecastArtifact } from "../lib/contract";
import { VerdictPanel } from "./ForecastDetail";

const artifact = {
  status: "sealed",
  match: {
    home_team: "France",
    away_team: "Spain",
    kickoff_utc: "2026-07-14T19:00:00Z",
  },
  forecast: {
    sealed_at_utc: "2026-07-13T19:00:00Z",
    horizon: "T-60m",
    probs: { home: 0.5, draw: 0.25, away: 0.25 },
    expected_goals: null,
    score_matrix: null,
  },
  model: {
    model_id: "test-model",
    family: "elo_ordlogit",
    version: "test",
    seed: 1,
    code_git_sha: "a".repeat(40),
    params_hash: "b".repeat(64),
  },
  provenance: {
    deterministic: true,
    generator: "test",
    payload_sha256: "c".repeat(64),
  },
} as unknown as ForecastArtifact;

describe("ForecastDetail seal metadata", () => {
  it("derives lead time from timestamps and keeps the horizon as an audit tag", () => {
    const html = renderToStaticMarkup(createElement(VerdictPanel, {
      artifact,
      showBar: false,
      dim: false,
    }));

    expect(html).toContain("1d before recorded kickoff");
    expect(html).toContain("Legacy horizon tag");
    expect(html).toContain("T−60m");
    expect(html).not.toContain("T−60m before kickoff");
  });
});
