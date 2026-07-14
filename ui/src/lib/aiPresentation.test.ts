import { describe, expect, it } from "vitest";
import type { NarrationClaim } from "./ai";
import { presentAiClaims, presentVerdictText } from "./aiPresentation";

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
