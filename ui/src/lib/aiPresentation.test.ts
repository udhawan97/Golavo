import { describe, expect, it } from "vitest";
import type { NarrationClaim } from "./ai";
import {
  leadingOutcomeFromProbs,
  presentAiClaims,
  presentOutcome,
  presentVerdictText,
} from "./aiPresentation";

const claim = (text: string): NarrationClaim => ({ text, source_ids: [], number_refs: [] });

describe("presentAiClaims", () => {
  it("keeps an empty response honestly empty", () => {
    expect(presentAiClaims([])).toEqual({ story: null, signals: [], notes: [] });
  });

  it("uses the original order without rewriting or duplicating claims", () => {
    const claims = ["story", "one", "two", "three", "four", "five"].map(claim);
    const result = presentAiClaims(claims);

    expect(result.story).toBe(claims[0]);
    expect(result.signals).toEqual(claims.slice(1, 4));
    expect(result.notes).toEqual(claims.slice(4));
    expect([result.story, ...result.signals, ...result.notes]).toEqual(claims);
  });
});

describe("presentVerdictText", () => {
  it("uses the actual team name for bare engine outcome tokens", () => {
    expect(presentVerdictText("home", "France", "Spain")).toBe("France");
    expect(presentVerdictText("away", "France", "Spain")).toBe("Spain");
    expect(presentVerdictText("Away win", "France", "Spain")).toBe("Spain");
  });

  it("labels draws plainly and leaves authored verdict prose intact", () => {
    expect(presentVerdictText("a draw", "France", "Spain")).toBe("Draw");
    expect(presentVerdictText("Spain are the likelier side", "France", "Spain"))
      .toBe("Spain are the likelier side");
  });
});

describe("deterministic outcome fallback", () => {
  it("turns engine outcomes into fixture labels", () => {
    expect(presentOutcome("home", "England", "Argentina")).toBe("England");
    expect(presentOutcome("away", "England", "Argentina")).toBe("Argentina");
    expect(presentOutcome("draw", "England", "Argentina")).toBe("Draw");
  });

  it("uses only the largest sealed probability and respects abstention", () => {
    expect(leadingOutcomeFromProbs({ home: 0.51, draw: 0.27, away: 0.22 })).toBe("home");
    expect(leadingOutcomeFromProbs({ home: 0.24, draw: 0.31, away: 0.45 })).toBe("away");
    expect(leadingOutcomeFromProbs(null)).toBeNull();
  });
});
