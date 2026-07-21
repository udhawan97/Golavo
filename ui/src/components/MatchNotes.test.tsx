import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { NotebookFact } from "../lib/contract";
import type { GroupedFacts } from "../lib/factPairs";
import { StatForStat } from "./MatchNotes";

let seq = 0;
function mk(over: Partial<NotebookFact> = {}): NotebookFact {
  seq += 1;
  return {
    id: over.id ?? `fact_${seq}`,
    version: "1.0.0",
    label: "context",
    scope: "team",
    subject: "France",
    text: "France kept a clean sheet in 8 of 20 recent matches (40.0%).",
    values: {},
    numbers: [{ key: "n", value: 8, unit: "count", display: "8" }],
    sample_n: 20,
    denominator: 20,
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

const empty: GroupedFacts = { tournament: [], paired: [], solo: [], other: [] };

const render = (grouped: Partial<GroupedFacts>, expert = false) =>
  renderToStaticMarkup(
    <StatForStat grouped={{ ...empty, ...grouped }} home="France" away="Morocco" expert={expert} />,
  );

describe("StatForStat", () => {
  it("renders nothing when no facts survived", () => {
    expect(render({})).toBe("");
  });

  it("shows both teams' values on one row", () => {
    const html = render({
      paired: [{
        id: "clean_sheet_rate",
        title: "Clean sheets",
        explainer: "How often this team stopped the opposition from scoring recently.",
        home: { fact: mk({ subject: "France", base_rate: 0.4 }), absence: null },
        away: { fact: mk({ subject: "Morocco", base_rate: 0.6 }), absence: null },
        rail: true,
      }],
    });
    expect(html).toContain("Clean sheets");
    expect(html).toContain("40%");
    expect(html).toContain("60%");
    expect(html).toContain("France");
    expect(html).toContain("Morocco");
  });

  it("points at the section holding a promoted twin instead of implying absence", () => {
    const html = render({
      solo: [{
        id: "biggest_win",
        title: "Biggest win",
        explainer: "The widest winning scoreline in the available history.",
        home: {
          fact: null,
          absence: { kind: "elsewhere", section: "Quick briefing", anchor: "#mn-briefing-title" },
        },
        away: { fact: mk({ subject: "Morocco" }), absence: null },
        rail: false,
      }],
    });
    expect(html).toContain("Shown in Quick briefing");
    expect(html).toContain('href="#mn-briefing-title"');
    expect(html).not.toContain("—</");
  });

  it("puts a one-sided record in the team lane without an empty comparison cell", () => {
    const html = render({
      solo: [{
        id: "win_streak",
        title: "Winning streak",
        explainer: "Consecutive wins in the team’s current run.",
        home: { fact: mk({ subject: "France" }), absence: null },
        away: { fact: null, absence: { kind: "unqualified" } },
        rail: false,
      }],
    });
    expect(html).toContain("Team-specific records");
    expect(html).toContain("France team records");
    expect(html).toContain("Morocco team records");
    expect(html).toContain("No additional team-only records");
    expect(html).not.toContain("No qualifying sample");
  });

  it("keeps the tournament band out of the comparison table", () => {
    const html = render({
      tournament: [mk({
        id: "competition_debut_base_rate",
        scope: "competition",
        subject: "FIFA World Cup",
        base_rate: 0.26,
      })],
    });
    expect(html).toContain("Competition context");
    expect(html).toContain("Records about the competition as a whole");
    expect(html).toContain("First-year teams");
    expect(html).not.toContain("<table");
  });

  it("gives the casual reader the explainer and the expert the source proof", () => {
    const row = {
      id: "clean_sheet_rate",
      title: "Clean sheets",
      explainer: "How often this team stopped the opposition from scoring recently.",
      home: { fact: mk({ subject: "France", base_rate: 0.4 }), absence: null },
      away: { fact: mk({ subject: "Morocco", base_rate: 0.6 }), absence: null },
      rail: true,
    };
    const casual = render({ paired: [row] }, false);
    const expert = render({ paired: [row] }, true);
    expect(casual).toContain("How often this team stopped");
    expect(expert).not.toContain("How often this team stopped");
    // Expert surfaces a compact proof line per cell on top of the disclosure
    // both modes carry, so it gains audit context without gaining height.
    expect(casual.match(/mn-fact__proof/g)).toHaveLength(2);
    expect(expert.match(/mn-fact__proof/g)).toHaveLength(4);
    // The compact line drops the chips that would wrap a narrow cell; the full
    // strip stays reachable in the disclosure, so "minimum" appears only there.
    expect(casual.match(/minimum 3/g)).toHaveLength(2);
    expect(expert.match(/minimum 3/g)).toHaveLength(2);
  });

  it("draws a rail only for rates", () => {
    const rate = render({
      paired: [{
        id: "clean_sheet_rate",
        title: "Clean sheets",
        explainer: "x",
        home: { fact: mk({ subject: "France", base_rate: 0.4 }), absence: null },
        away: { fact: mk({ subject: "Morocco", base_rate: 0.6 }), absence: null },
        rail: true,
      }],
    });
    const count = render({
      paired: [{
        id: "wc_pedigree",
        title: "World Cup pedigree",
        explainer: "x",
        home: { fact: mk({ subject: "France" }), absence: null },
        away: { fact: mk({ subject: "Morocco" }), absence: null },
        rail: false,
      }],
    });
    expect(rate).toContain("mn-compare__rail");
    expect(count).not.toContain("mn-compare__rail");
  });
});
