import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { CouncilModel } from "../lib/contract";
import { ExpertDetail } from "./ModelCouncil";

function model(
  family: CouncilModel["family"],
  role: CouncilModel["role"],
  probs: CouncilModel["probs"],
): CouncilModel {
  return {
    family,
    role,
    probs,
    method: role === "baseline" ? "base_rate" : "goals",
    abstained: false,
    expected_goals: null,
    score_matrix: null,
    params: null,
  };
}

describe("ModelCouncil expert detail", () => {
  it("presents the baseline and variants as separate, non-voting evidence artifacts", () => {
    const html = renderToStaticMarkup(createElement(ExpertDetail, {
      baseline: model("climatological", "baseline", { home: .49, draw: .23, away: .28 }),
      variants: [
        model("poisson_independent", "variant", { home: .31, draw: .30, away: .39 }),
        model("bivariate_poisson", "variant", { home: .31, draw: .30, away: .39 }),
      ],
      home: "England",
      away: "Argentina",
    }));

    expect(html).toContain("Baseline &amp; model-family disclosure");
    expect(html).toContain("Climatology baseline");
    expect(html).toContain("Not a voice");
    expect(html).toContain("Poisson (independent)");
    expect(html).toContain("Bivariate Poisson");
    expect(html).toContain("Disclosure only · zero additional votes");
    expect(html).toContain('aria-label="England 49%, Draw 23%, Argentina 28%"');
    expect(html).not.toContain("poisson_independent");
  });

  it("renders nothing when the reference models carry no probabilities", () => {
    const html = renderToStaticMarkup(createElement(ExpertDetail, {
      baseline: model("climatological", "baseline", null),
      variants: [model("poisson_independent", "variant", null)],
      home: "England",
      away: "Argentina",
    }));
    expect(html).toBe("");
  });
});
