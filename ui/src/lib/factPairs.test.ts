import { describe, expect, it } from "vitest";
import type { NotebookFact } from "./contract";
import { buildElsewhere, factKey, groupFacts, type Absence } from "./factPairs";

let seq = 0;
function mk(over: Partial<NotebookFact> = {}): NotebookFact {
  seq += 1;
  return {
    id: over.id ?? `fact_${seq}`,
    version: "1.0.0",
    label: "context",
    scope: "team",
    subject: "France",
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

const group = (cards: NotebookFact[], elsewhere: ReadonlyMap<string, Absence> = new Map()) =>
  groupFacts({ cards, home: "France", away: "Morocco", elsewhere });

describe("groupFacts", () => {
  it("pairs a stat both teams qualify for into one row", () => {
    const result = group([
      mk({ id: "clean_sheet_rate", subject: "France", base_rate: 0.4 }),
      mk({ id: "clean_sheet_rate", subject: "Morocco", base_rate: 0.6 }),
    ]);
    expect(result.paired).toHaveLength(1);
    expect(result.solo).toHaveLength(0);
    expect(result.paired[0].home.fact?.base_rate).toBe(0.4);
    expect(result.paired[0].away.fact?.base_rate).toBe(0.6);
    expect(result.paired[0].title).toBe("Clean sheets");
  });

  it("puts a stat only one team qualifies for in solo, with the other side absent", () => {
    const result = group([mk({ id: "win_streak", subject: "France" })]);
    expect(result.paired).toHaveLength(0);
    expect(result.solo).toHaveLength(1);
    expect(result.solo[0].home.fact).not.toBeNull();
    expect(result.solo[0].away.fact).toBeNull();
  });

  it("says a missing twin was promoted elsewhere rather than implying it does not exist", () => {
    const elsewhere = new Map<string, Absence>([
      ["biggest_win::France", { kind: "elsewhere", section: "Quick briefing", anchor: "#mn-briefing-title" }],
    ]);
    const result = group([mk({ id: "biggest_win", subject: "Morocco" })], elsewhere);
    expect(result.solo[0].home.absence).toEqual({
      kind: "elsewhere",
      section: "Quick briefing",
      anchor: "#mn-briefing-title",
    });
  });

  it("says a missing twin was suppressed when it appears nowhere", () => {
    const result = group([mk({ id: "win_streak", subject: "France" })]);
    expect(result.solo[0].away.absence).toEqual({ kind: "unqualified" });
  });

  it("lifts competition facts out of the comparison entirely", () => {
    const result = group([
      mk({ id: "home_advantage_base_rate", scope: "competition", subject: "FIFA World Cup", base_rate: 0.61 }),
      mk({ id: "clean_sheet_rate", subject: "France", base_rate: 0.4 }),
      mk({ id: "clean_sheet_rate", subject: "Morocco", base_rate: 0.6 }),
    ]);
    expect(result.tournament).toHaveLength(1);
    expect(result.paired).toHaveLength(1);
    expect(result.solo).toHaveLength(0);
  });

  it("never drops a fact whose subject matches neither team", () => {
    const result = group([mk({ id: "head_to_head_goals", scope: "head_to_head", subject: "France v Morocco" })]);
    expect(result.other).toHaveLength(1);
    expect(result.paired).toHaveLength(0);
    expect(result.solo).toHaveLength(0);
  });

  it("allows a rail only when both sides are rates", () => {
    const rates = group([
      mk({ id: "clean_sheet_rate", subject: "France", base_rate: 0.4 }),
      mk({ id: "clean_sheet_rate", subject: "Morocco", base_rate: 0.6 }),
    ]);
    const counts = group([
      mk({ id: "wc_pedigree", subject: "France", base_rate: null }),
      mk({ id: "wc_pedigree", subject: "Morocco", base_rate: null }),
    ]);
    expect(rates.paired[0].rail).toBe(true);
    expect(counts.paired[0].rail).toBe(false);
  });

  it("leads with the widest gap and puts rate rows before count rows", () => {
    const result = group([
      mk({ id: "clean_sheet_rate", subject: "France", base_rate: 0.4 }),
      mk({ id: "clean_sheet_rate", subject: "Morocco", base_rate: 0.45 }),
      mk({ id: "tournament_record", subject: "France", base_rate: 0.56 }),
      mk({ id: "tournament_record", subject: "Morocco", base_rate: 0.29 }),
      mk({ id: "wc_pedigree", subject: "France", base_rate: null }),
      mk({ id: "wc_pedigree", subject: "Morocco", base_rate: null }),
    ]);
    expect(result.paired.map((row) => row.id)).toEqual([
      "tournament_record",
      "clean_sheet_rate",
      "wc_pedigree",
    ]);
  });

  it("orders identically on repeated runs", () => {
    const cards = [
      mk({ id: "b_stat", subject: "France", base_rate: 0.5, sample_n: 10 }),
      mk({ id: "b_stat", subject: "Morocco", base_rate: 0.4, sample_n: 10 }),
      mk({ id: "a_stat", subject: "France", base_rate: 0.5, sample_n: 10 }),
      mk({ id: "a_stat", subject: "Morocco", base_rate: 0.4, sample_n: 10 }),
    ];
    const first = group(cards).paired.map((row) => row.id);
    const second = group([...cards].reverse()).paired.map((row) => row.id);
    expect(first).toEqual(second);
    expect(first).toEqual(["a_stat", "b_stat"]);
  });

  it("falls back gracefully for an unregistered template id", () => {
    const result = group([mk({ id: "future_template", subject: "France" })]);
    expect(result.solo[0].title).toBe("Match record");
  });
});

describe("buildElsewhere", () => {
  const empty = {
    headlines: [],
    hero: null,
    scorers: [],
    h2h: null,
    timing: [],
    penalties: [],
    omitted: new Set<string>(),
  };

  it("labels and anchors each promoting section", () => {
    const map = buildElsewhere({
      ...empty,
      headlines: [mk({ id: "biggest_win", subject: "France" })],
      hero: mk({ id: "home_advantage_base_rate", subject: "FIFA World Cup" }),
      timing: [mk({ id: "goal_timing_profile", subject: "Morocco" })],
    });
    expect(map.get("biggest_win::France")).toEqual({
      kind: "elsewhere", section: "Quick briefing", anchor: "#mn-briefing-title",
    });
    expect(map.get("home_advantage_base_rate::FIFA World Cup")).toEqual({
      kind: "elsewhere", section: "Cover story", anchor: "#mn-cover-title",
    });
    expect(map.get("goal_timing_profile::Morocco")).toEqual({
      kind: "elsewhere", section: "Scoring clock", anchor: "#mn-timing-title",
    });
  });

  it("marks a fact consumed by another panel with no anchor it cannot resolve", () => {
    const map = buildElsewhere({ ...empty, omitted: new Set(["ht_lead_conversion::France"]) });
    expect(map.get("ht_lead_conversion::France")).toEqual({
      kind: "elsewhere", section: "this programme", anchor: null,
    });
  });

  it("prefers the named section over the generic one", () => {
    const map = buildElsewhere({
      ...empty,
      headlines: [mk({ id: "biggest_win", subject: "France" })],
      omitted: new Set(["biggest_win::France"]),
    });
    expect(map.get("biggest_win::France")).toEqual({
      kind: "elsewhere", section: "Quick briefing", anchor: "#mn-briefing-title",
    });
  });
});

describe("factKey", () => {
  it("separates the same stat held by two subjects", () => {
    expect(factKey({ id: "biggest_win", subject: "France" })).toBe("biggest_win::France");
    expect(factKey({ id: "biggest_win", subject: "Morocco" })).not.toBe(
      factKey({ id: "biggest_win", subject: "France" }),
    );
  });
});
