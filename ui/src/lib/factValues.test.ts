import { describe, expect, it } from "vitest";
import type { CommentatorsNotebook, NotebookFact } from "./contract";
import { isCount, parseHalfTimeStory, parseWorldCupPedigree } from "./factValues";

function fact(id: string, subject: string, values: Record<string, unknown>): NotebookFact {
  return { id, subject, values } as NotebookFact;
}

function notebook(facts: NotebookFact[]): CommentatorsNotebook {
  return { facts } as CommentatorsNotebook;
}

describe("half-time fact parsing", () => {
  it("accepts non-negative safe integer counts", () => {
    expect(isCount(0)).toBe(true);
    expect(isCount(3)).toBe(true);
    expect(isCount(-1)).toBe(false);
    expect(isCount(1.5)).toBe(false);
    expect(isCount("3")).toBe(false);
  });

  it("returns a complete two-team story and consumed keys", () => {
    const facts = [
      fact("ht_comeback_record", "Home", { ht_deficits: 10, comeback_wins: 3, comeback_draws: 2 }),
      fact("ht_lead_conversion", "Home", { ht_leads: 8, leads_won: 6, leads_drawn: 1 }),
      fact("ht_comeback_record", "Away", { ht_deficits: 11, comeback_wins: 2, comeback_draws: 3 }),
      fact("ht_lead_conversion", "Away", { ht_leads: 9, leads_won: 5, leads_drawn: 2 }),
    ];
    for (const item of facts) item.source_ids = ["pack"];
    const parsed = parseHalfTimeStory(notebook(facts), "Home", "Away");
    expect(parsed?.home.comebackWins).toBe(3);
    expect(parsed?.consumedKeys).toContain("ht_lead_conversion::Away");
  });

  it("fails closed on missing, malformed, or impossible values", () => {
    const malformed = notebook([
      fact("ht_comeback_record", "Home", { ht_deficits: 2, comeback_wins: 2, comeback_draws: 1 }),
      fact("ht_lead_conversion", "Home", { ht_leads: 8, leads_won: 6, leads_drawn: 1 }),
      fact("ht_comeback_record", "Away", { ht_deficits: 11, comeback_wins: 2, comeback_draws: 3 }),
      fact("ht_lead_conversion", "Away", { ht_leads: "9", leads_won: 5, leads_drawn: 2 }),
    ]);
    expect(parseHalfTimeStory(malformed, "Home", "Away")).toBeNull();
    expect(parseHalfTimeStory(notebook([]), "Home", "Away")).toBeNull();
  });
});

describe("World Cup fact parsing", () => {
  it("accepts pedigree with optional awards and preserves a partial team state", () => {
    const facts = [
      fact("wc_pedigree", "France", {
        titles: 2,
        title_years: [1998, 2018],
        finals: 4,
        appearances: 16,
        best_recent: { position: 1, year: 2018 },
      }),
      fact("wc_awards", "France", {
        awards: [{ award: "Golden Ball", player: "Example Player", year: 2006 }],
      }),
      fact("wc_pedigree", "Morocco", {
        titles: 0,
        title_years: [],
        finals: 0,
        appearances: 6,
        best_recent: { position: 4, year: 2022 },
      }),
    ];
    for (const item of facts) {
      item.source_ids = ["fjelstul-worldcup"];
      item.date_range = ["1930-07-30", "2022-12-18"];
    }
    const parsed = parseWorldCupPedigree(notebook(facts), "France", "Morocco");
    expect(parsed?.home?.awards).toHaveLength(1);
    expect(parsed?.away?.awards).toEqual([]);
    expect(parsed?.consumedKeys).not.toContain("wc_awards::Morocco");
  });

  it("fails closed on impossible title counts", () => {
    const broken = fact("wc_pedigree", "France", {
      titles: 3,
      title_years: [1998, 2018],
      finals: 2,
      appearances: 16,
      best_recent: null,
    });
    broken.source_ids = ["fjelstul-worldcup"];
    broken.date_range = ["1930-07-30", "2022-12-18"];
    expect(parseWorldCupPedigree(notebook([broken]), "France", "Morocco")).toBeNull();
  });
});
