import type { CommentatorsNotebook, NotebookFact } from "./contract";

export const PANEL_FACT_IDS = new Set([
  "ht_comeback_record",
  "ht_lead_conversion",
  "wc_pedigree",
  "wc_awards",
]);

export function isCount(value: unknown): value is number {
  return Number.isSafeInteger(value) && typeof value === "number" && value >= 0;
}

export interface HalfTimeTeamStory {
  team: string;
  deficits: number;
  comebackWins: number;
  comebackDraws: number;
  leads: number;
  leadsWon: number;
  leadsDrawn: number;
}

export interface HalfTimeStoryData {
  home: HalfTimeTeamStory;
  away: HalfTimeTeamStory;
  sourceIds: string[];
  consumedKeys: Set<string>;
}

function findFact(
  notebook: CommentatorsNotebook,
  id: string,
  subject: string,
): NotebookFact | null {
  return notebook.facts.find((fact) => fact.id === id && fact.subject === subject) ?? null;
}

function parseTeam(notebook: CommentatorsNotebook, team: string): {
  story: HalfTimeTeamStory;
  facts: NotebookFact[];
} | null {
  const comeback = findFact(notebook, "ht_comeback_record", team);
  const conversion = findFact(notebook, "ht_lead_conversion", team);
  if (!comeback || !conversion) return null;

  const deficits = comeback.values.ht_deficits;
  const comebackWins = comeback.values.comeback_wins;
  const comebackDraws = comeback.values.comeback_draws;
  const leads = conversion.values.ht_leads;
  const leadsWon = conversion.values.leads_won;
  const leadsDrawn = conversion.values.leads_drawn;
  if (
    !isCount(deficits) ||
    !isCount(comebackWins) ||
    !isCount(comebackDraws) ||
    !isCount(leads) ||
    !isCount(leadsWon) ||
    !isCount(leadsDrawn) ||
    deficits === 0 ||
    leads === 0 ||
    comebackWins + comebackDraws > deficits ||
    leadsWon + leadsDrawn > leads
  ) {
    return null;
  }
  return {
    story: { team, deficits, comebackWins, comebackDraws, leads, leadsWon, leadsDrawn },
    facts: [comeback, conversion],
  };
}

export function parseHalfTimeStory(
  notebook: CommentatorsNotebook | null,
  homeTeam: string,
  awayTeam: string,
): HalfTimeStoryData | null {
  if (!notebook) return null;
  const home = parseTeam(notebook, homeTeam);
  const away = parseTeam(notebook, awayTeam);
  if (!home || !away) return null;
  const facts = [...home.facts, ...away.facts];
  return {
    home: home.story,
    away: away.story,
    sourceIds: [...new Set(facts.flatMap((fact) => fact.source_ids))],
    consumedKeys: new Set(facts.map((fact) => `${fact.id}::${fact.subject}`)),
  };
}
