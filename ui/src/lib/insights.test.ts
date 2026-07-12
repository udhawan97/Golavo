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

  it("leads with the fact closest to this fixture (scope), not the most specific one", () => {
    // A broad head-to-head still beats a razor-specific team fact.
    const h2h = mk({ id: "h2h", scope: "head_to_head", label: "context", specificity: 0.1 });
    const team = mk({ id: "team", scope: "team", label: "predictive", specificity: 0.9 });
    const comp = mk({ id: "comp", scope: "competition", label: "predictive", specificity: 1.0 });
    const out = topInsights(notebook([comp, team, h2h]));
    expect(out.map((f) => f.id)).toEqual(["h2h", "team", "comp"]);
  });

  it("within a scope, prefers higher specificity, then predictive over context", () => {
    const a = mk({ id: "spec_hi", scope: "team", label: "context", specificity: 0.9 });
    const b = mk({ id: "spec_lo_pred", scope: "team", label: "predictive", specificity: 0.4 });
    const c = mk({ id: "spec_lo_ctx", scope: "team", label: "context", specificity: 0.4 });
    const out = topInsights(notebook([c, b, a]));
    expect(out.map((f) => f.id)).toEqual(["spec_hi", "spec_lo_pred", "spec_lo_ctx"]);
  });

  it("never includes coincidences", () => {
    const coincidence = mk({ id: "coin", scope: "head_to_head", label: "coincidence", specificity: 1.0 });
    const context = mk({ id: "ctx", scope: "team", label: "context", specificity: 0.2 });
    const out = topInsights(notebook([coincidence, context]));
    expect(out.map((f) => f.id)).toEqual(["ctx"]);
  });

  it("drops stale facts", () => {
    const fresh = mk({ id: "fresh", scope: "team", label: "context", specificity: 0.3 });
    const stale = mk({
      id: "stale",
      scope: "head_to_head",
      label: "context",
      specificity: 0.9,
      freshness: { as_of_utc: "x", last_event_utc: "x", age_days: 9999, stale: true, staleness_days: 9999 },
    });
    const out = topInsights(notebook([stale, fresh]));
    expect(out.map((f) => f.id)).toEqual(["fresh"]);
  });

  it("breaks full ties by sample size then id", () => {
    const a = mk({ id: "b_more", scope: "team", label: "context", specificity: 0.5, sample_n: 500 });
    const b = mk({ id: "a_less", scope: "team", label: "context", specificity: 0.5, sample_n: 50 });
    const out = topInsights(notebook([b, a]));
    expect(out.map((f) => f.id)).toEqual(["b_more", "a_less"]);
  });

  it("caps at the requested limit and is stable", () => {
    const facts = Array.from({ length: 6 }, (_, i) =>
      mk({ id: `p${i}`, scope: "team", label: "predictive", specificity: i / 10 }),
    );
    const a = topInsights(notebook(facts), 3);
    const b = topInsights(notebook(facts.slice().reverse()), 3);
    expect(a).toHaveLength(3);
    expect(a.map((f) => f.id)).toEqual(b.map((f) => f.id));
  });
});
