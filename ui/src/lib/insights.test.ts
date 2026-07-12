import { describe, expect, it } from "vitest";
import type { CommentatorsNotebook, FactLabel, NotebookFact } from "./contract";
import { topInsights } from "./insights";

let seq = 0;
function mk(over: Partial<NotebookFact> & { label: FactLabel }): NotebookFact {
  seq += 1;
  return {
    id: over.id ?? `fact_${seq}`,
    version: "1.0.0",
    scope: "team",
    subject: "Test",
    text: "A fact.",
    values: {},
    numbers: [],
    sample_n: 100,
    denominator: 100,
    base_rate: null,
    date_range: ["2000-01-01", "2026-01-01"],
    source_ids: ["sp_x"],
    min_sample: 3,
    specificity: 0.5,
    freshness: {
      as_of_utc: "2026-01-01T00:00:00Z",
      last_event_utc: "2026-01-01T00:00:00Z",
      age_days: 1,
      stale: false,
      staleness_days: null,
    },
    ...over,
  };
}

function notebook(facts: NotebookFact[]): CommentatorsNotebook {
  return {
    schema_version: "0.1.0",
    notebook_id: "nb_test",
    registry_version: "2026.01",
    as_of_utc: "2026-01-01T00:00:00Z",
    match: { home_team: "A", away_team: "B", competition: "C", neutral_venue: false },
    source_ids: ["sp_x"],
    family_size: 10,
    coincidence_cap: 3,
    facts,
    suppressed: [],
    generator: "test",
  };
}

describe("topInsights", () => {
  it("returns nothing for a null or empty notebook", () => {
    expect(topInsights(null)).toEqual([]);
    expect(topInsights(notebook([]))).toEqual([]);
  });

  it("ranks predictive before context regardless of specificity", () => {
    const context = mk({ id: "ctx", label: "context", specificity: 1.0 });
    const predictive = mk({ id: "pred", label: "predictive", specificity: 0.1 });
    const out = topInsights(notebook([context, predictive]));
    expect(out.map((f) => f.id)).toEqual(["pred", "ctx"]);
  });

  it("never includes coincidences", () => {
    const coincidence = mk({ id: "coin", label: "coincidence", specificity: 1.0 });
    const context = mk({ id: "ctx", label: "context", specificity: 0.2 });
    const out = topInsights(notebook([coincidence, context]));
    expect(out.map((f) => f.id)).toEqual(["ctx"]);
  });

  it("drops stale facts", () => {
    const fresh = mk({ id: "fresh", label: "context", specificity: 0.3 });
    const stale = mk({
      id: "stale",
      label: "context",
      specificity: 0.9,
      freshness: { as_of_utc: "x", last_event_utc: "x", age_days: 9999, stale: true, staleness_days: 9999 },
    });
    const out = topInsights(notebook([stale, fresh]));
    expect(out.map((f) => f.id)).toEqual(["fresh"]);
  });

  it("breaks specificity ties by sample size then id", () => {
    const a = mk({ id: "b_more", label: "context", specificity: 0.5, sample_n: 500 });
    const b = mk({ id: "a_less", label: "context", specificity: 0.5, sample_n: 50 });
    const out = topInsights(notebook([b, a]));
    expect(out.map((f) => f.id)).toEqual(["b_more", "a_less"]);
  });

  it("caps at the requested limit and is stable", () => {
    const facts = Array.from({ length: 6 }, (_, i) =>
      mk({ id: `p${i}`, label: "predictive", specificity: i / 10 }),
    );
    const a = topInsights(notebook(facts), 3);
    const b = topInsights(notebook(facts.slice().reverse()), 3);
    expect(a).toHaveLength(3);
    expect(a.map((f) => f.id)).toEqual(b.map((f) => f.id));
  });
});
