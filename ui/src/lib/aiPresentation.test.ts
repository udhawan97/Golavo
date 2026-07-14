import { describe, expect, it } from "vitest";
import type { NarrationClaim } from "./ai";
import { presentAiClaims } from "./aiPresentation";

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
