import { describe, expect, it } from "vitest";
import type { CommentatorsNotebook, NotebookFact } from "./contract";
import { isCount, parseHalfTimeStory } from "./factValues";

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
