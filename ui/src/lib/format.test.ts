import { describe, expect, it } from "vitest";
import { inWords, largestRemainder, pctWhole, sinceYear, yearSpan } from "./format";

describe("pctWhole", () => {
  it("rounds to a whole percent", () => {
    expect(pctWhole(0.45)).toBe("45%");
    expect(pctWhole(0.279)).toBe("28%");
    expect(pctWhole(0)).toBe("0%");
    expect(pctWhole(1)).toBe("100%");
  });
});

describe("largestRemainder", () => {
  it("keeps a 1X2 split summing to 100", () => {
    const out = largestRemainder([0.45, 0.271, 0.279]);
    expect(out.reduce((a, b) => a + b, 0)).toBe(100);
    expect(out).toEqual([45, 27, 28]);
  });

  it("resolves a three-way tie to exactly 100", () => {
    const out = largestRemainder([1 / 3, 1 / 3, 1 / 3]);
    expect(out.reduce((a, b) => a + b, 0)).toBe(100);
  });

  it("never leaves a gap or overshoot on awkward inputs", () => {
    for (const trip of [
      [0.5, 0.25, 0.25],
      [0.4, 0.3, 0.3],
      [0.334, 0.333, 0.333],
      [0.9, 0.05, 0.05],
    ]) {
      expect(largestRemainder(trip).reduce((a, b) => a + b, 0)).toBe(100);
    }
  });
});

describe("inWords", () => {
  it("gives a clean small-denominator frequency", () => {
    expect(inWords(0.5)).toBe("about 1 in 2");
    expect(inWords(0.6)).toBe("about 3 in 5");
    expect(inWords(0.36)).toBe("about 1 in 3");
    expect(inWords(0.25)).toBe("about 1 in 4");
  });

  it("handles the degenerate ends without a nonsensical fraction", () => {
    expect(inWords(1)).toBe("a near certainty");
    expect(inWords(0)).toBe("very unlikely");
  });
});

describe("sinceYear / yearSpan", () => {
  it("reads the start year", () => {
    expect(sinceYear(["1930-07-18", "2026-07-06"])).toBe("since 1930");
    expect(sinceYear(["", ""])).toBe("");
  });

  it("compacts a date range to a year span", () => {
    expect(yearSpan(["1930-07-18", "2026-07-06"])).toBe("1930–2026");
    expect(yearSpan(["2024-01-01", "2024-12-31"])).toBe("2024");
    expect(yearSpan(["bad", "2026-01-01"])).toBe("");
  });
});
