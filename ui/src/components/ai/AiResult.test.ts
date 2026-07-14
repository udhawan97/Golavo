import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { NarrativeResponse } from "../../lib/ai";
import { Result } from "./AiResult";

const response: NarrativeResponse = {
  status: "ok",
  provider: "ollama",
  model: "local-test",
  prompt_version: "test",
  bundle_hash: "test",
  cached: false,
  reason: null,
  notes: [],
  sources: [{
    source_id: "engine:match_analysis",
    kind: "engine",
    title: "Match analysis",
    url: "",
  }],
  numbers: [],
  narration: {
    schema_version: "0.3.0",
    verdict: {
      text: "away",
      source_ids: ["engine:match_analysis"],
      number_refs: [],
    },
    claims: [],
    scenarios: [],
    candidate_facts: [],
  },
};

describe("AI verdict presentation", () => {
  it("shows the actual team name when a local model returns the bare away token", () => {
    const html = renderToStaticMarkup(createElement(Result, {
      data: response,
      isMatch: true,
      depth: "fast",
      context: { homeTeam: "France", awayTeam: "Spain", uncertainty: "low" },
      onRefresh: () => undefined,
      onRetry: () => undefined,
    }));

    expect(html).toContain("Spain");
    expect(html).not.toContain(">away<");
    expect(html).toContain('aria-label="Evidence 1: Match analysis"');
  });

  it("shows the engine winner even when Gemma writes a comparison instead", () => {
    const comparison: NarrativeResponse = {
      ...response,
      narration: response.narration ? {
        ...response.narration,
        verdict: {
          ...response.narration.verdict!,
          text: "England's clean-sheet rate contrasts with Argentina's.",
        },
      } : null,
    };
    const html = renderToStaticMarkup(createElement(Result, {
      data: comparison,
      isMatch: true,
      depth: "deep",
      context: {
        homeTeam: "England",
        awayTeam: "Argentina",
        uncertainty: "low",
        leadingOutcome: "home",
      },
      onRefresh: () => undefined,
      onRetry: () => undefined,
    }));

    expect(html).toContain('aria-label="Engine pick: England"');
    expect(html).toContain("Engine pick");
    expect(html).toContain("<strong>England</strong>");
    expect(html).toContain("England&#x27;s clean-sheet rate contrasts with Argentina&#x27;s.");
  });

  it("falls back to the deterministic winner when deep analysis omits its verdict", () => {
    const withoutVerdict: NarrativeResponse = {
      ...response,
      narration: response.narration ? { ...response.narration, verdict: null } : null,
    };
    const html = renderToStaticMarkup(createElement(Result, {
      data: withoutVerdict,
      isMatch: true,
      depth: "deep",
      context: {
        homeTeam: "England",
        awayTeam: "Argentina",
        uncertainty: "low",
        leadingOutcome: "home",
      },
      onRefresh: () => undefined,
      onRetry: () => undefined,
    }));

    expect(html).toContain("Engine verdict · deterministic");
    expect(html).toContain("England");
    expect(html).not.toContain(">home<");
  });
});
