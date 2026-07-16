import { describe, expect, it } from "vitest";
import { inWords, kickoffRelative, largestRemainder, pctWhole, sealLeadTime, sinceYear, yearSpan } from "./format";

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

describe("kickoffRelative", () => {
  const now = new Date("2026-07-12T00:00:00Z");

  it("labels near-term fixtures in both directions", () => {
    expect(kickoffRelative("2026-07-15T00:00:00Z", now)).toBe("in 3 days");
    expect(kickoffRelative("2026-07-10T00:00:00Z", now)).toBe("2 days ago");
  });

  it("suppresses far-future and ancient dates (no absurd 'in 1282 days')", () => {
    expect(kickoffRelative("2030-01-11T00:00:00Z", now)).toBe("");
    expect(kickoffRelative("2012-01-01T00:00:00Z", now)).toBe("");
  });

  it("returns empty for an unparseable date", () => {
    expect(kickoffRelative("not-a-date", now)).toBe("");
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

describe("sealLeadTime", () => {
  const kickoff = "2026-07-20T18:00:00Z";

  it("uses immutable timestamps instead of the legacy horizon tag", () => {
    expect(sealLeadTime(kickoff, "2026-07-19T02:00:00Z")).toBe("1d 16h");
    expect(sealLeadTime(kickoff, "2026-07-20T01:00:00Z")).toBe("17h");
    expect(sealLeadTime(kickoff, "2026-07-20T17:35:00Z")).toBe("25m");
  });

  it("fails closed for invalid or post-kickoff seals", () => {
    expect(sealLeadTime("bad", "2026-07-20T17:35:00Z")).toBeNull();
    expect(sealLeadTime(kickoff, "2026-07-20T19:00:00Z")).toBeNull();
  });
});
