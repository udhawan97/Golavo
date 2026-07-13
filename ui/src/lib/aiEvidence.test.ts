import { describe, expect, it } from "vitest";
import { buildEvidenceIndex, hostnameOf, sourceKindLine } from "./aiEvidence";
import type { NarrationClaim, SourceRef } from "./ai";

const sources: SourceRef[] = [
  { source_id: "engine", kind: "engine", title: "Engine", url: "" },
  { source_id: "results", kind: "snapshot", title: "Results pack", url: "https://example.org/results" },
  { source_id: "web_1", kind: "web", title: "Wikipedia", url: "https://en.wikipedia.org/wiki/X" },
];

function claim(text: string, sids: string[]): NarrationClaim {
  return { text, source_ids: sids, number_refs: [] };
}

describe("buildEvidenceIndex", () => {
  it("dedupes sources and numbers them in first-citation order", () => {
    const idx = buildEvidenceIndex(
      {
        verdict: claim("v", ["engine"]),
        claims: [claim("a", ["engine", "results"]), claim("b", ["results"])],
        scenarios: [claim("c", ["web_1"])],
      },
      sources,
    );
    expect(idx.ordered.map((e) => e.source.source_id)).toEqual(["engine", "results", "web_1"]);
    expect(idx.indexOf("engine")).toBe(1);
    expect(idx.indexOf("results")).toBe(2);
    expect(idx.indexOf("web_1")).toBe(3);
  });

  it("counts how many claims cite each source", () => {
    const idx = buildEvidenceIndex(
      {
        verdict: null,
        claims: [claim("a", ["engine", "results"]), claim("b", ["results"])],
        scenarios: [],
      },
      sources,
    );
    const byId = Object.fromEntries(idx.ordered.map((e) => [e.source.source_id, e.citedBy]));
    expect(byId.engine).toBe(1);
    expect(byId.results).toBe(2);
  });

  it("counts a source cited twice in one claim only once", () => {
    const idx = buildEvidenceIndex(
      { verdict: null, claims: [claim("a", ["engine", "engine"])], scenarios: [] },
      sources,
    );
    expect(idx.ordered).toHaveLength(1);
    expect(idx.ordered[0].citedBy).toBe(1);
  });

  it("skips source ids the envelope does not know", () => {
    const idx = buildEvidenceIndex(
      { verdict: null, claims: [claim("a", ["ghost", "engine"])], scenarios: [] },
      sources,
    );
    expect(idx.ordered.map((e) => e.source.source_id)).toEqual(["engine"]);
    expect(idx.indexOf("ghost")).toBeNull();
  });
});

describe("hostnameOf", () => {
  it("strips www. and returns the host", () => {
    expect(hostnameOf("https://www.example.com/a/b")).toBe("example.com");
    expect(hostnameOf("https://en.wikipedia.org/wiki/X")).toBe("en.wikipedia.org");
  });
  it("falls back to the raw string for an unparseable url", () => {
    expect(hostnameOf("not a url")).toBe("not a url");
  });
});

describe("sourceKindLine", () => {
  it("labels web sources as not engine-verified", () => {
    expect(sourceKindLine("web")).toMatch(/not engine-verified/);
    expect(sourceKindLine("engine")).toMatch(/engine/);
    expect(sourceKindLine("snapshot")).toMatch(/pack/);
  });
});
