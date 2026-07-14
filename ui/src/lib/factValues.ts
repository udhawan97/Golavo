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

export interface WorldCupAward {
  award: string;
  player: string;
  year: number;
}

export interface WorldCupTeamPedigree {
  team: string;
  titles: number;
  titleYears: number[];
  finals: number;
  appearances: number;
  bestRecent: { position: 1 | 2 | 3 | 4; year: number } | null;
  awards: WorldCupAward[];
  sourceIds: string[];
}

export interface WorldCupPedigreeData {
  homeTeam: string;
  awayTeam: string;
  home: WorldCupTeamPedigree | null;
  away: WorldCupTeamPedigree | null;
  dateRange: [string, string];
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

function isYear(value: unknown): value is number {
  return isCount(value) && value >= 1930 && value <= 2100;
}

function parseAwards(value: unknown): WorldCupAward[] | null {
  if (!Array.isArray(value)) return null;
  const awards: WorldCupAward[] = [];
  for (const item of value) {
    if (!item || typeof item !== "object") return null;
    const row = item as Record<string, unknown>;
    if (
      typeof row.award !== "string" ||
      row.award.trim() === "" ||
      typeof row.player !== "string" ||
      row.player.trim() === "" ||
      !isYear(row.year)
    ) {
      return null;
    }
    awards.push({ award: row.award, player: row.player, year: row.year });
  }
  return awards;
}

function parsePedigreeTeam(
  notebook: CommentatorsNotebook,
  team: string,
): { data: WorldCupTeamPedigree; facts: NotebookFact[] } | null {
  const pedigree = findFact(notebook, "wc_pedigree", team);
  if (!pedigree) return null;
  const { titles, title_years: titleYears, finals, appearances, best_recent: best } =
    pedigree.values;
  if (
    !isCount(titles) ||
    !isCount(finals) ||
    !isCount(appearances) ||
    appearances === 0 ||
    titles > finals ||
    finals > appearances ||
    !Array.isArray(titleYears) ||
    titleYears.length !== titles ||
    !titleYears.every(isYear) ||
    new Set(titleYears).size !== titleYears.length
  ) {
    return null;
  }
  let bestRecent: WorldCupTeamPedigree["bestRecent"] = null;
  if (best !== null) {
    if (!best || typeof best !== "object") return null;
    const row = best as Record<string, unknown>;
    if (![1, 2, 3, 4].includes(row.position as number) || !isYear(row.year)) return null;
    bestRecent = { position: row.position as 1 | 2 | 3 | 4, year: row.year };
  }

  const awardsFact = findFact(notebook, "wc_awards", team);
  const awards = awardsFact ? parseAwards(awardsFact.values.awards) : [];
  if (awards === null) return null;
  const facts = awardsFact ? [pedigree, awardsFact] : [pedigree];
  return {
    data: {
      team,
      titles,
      titleYears: [...titleYears].sort((a, b) => a - b),
      finals,
      appearances,
      bestRecent,
      awards,
      sourceIds: [...new Set(facts.flatMap((fact) => fact.source_ids))],
    },
    facts,
  };
}

export function parseWorldCupPedigree(
  notebook: CommentatorsNotebook | null,
  homeTeam: string,
  awayTeam: string,
): WorldCupPedigreeData | null {
  if (!notebook) return null;
  const home = parsePedigreeTeam(notebook, homeTeam);
  const away = parsePedigreeTeam(notebook, awayTeam);
  if (!home && !away) return null;
  const facts = [...(home?.facts ?? []), ...(away?.facts ?? [])];
  const firstPedigree = facts.find((fact) => fact.id === "wc_pedigree");
  if (!firstPedigree) return null;
  return {
    homeTeam,
    awayTeam,
    home: home?.data ?? null,
    away: away?.data ?? null,
    dateRange: firstPedigree.date_range,
    consumedKeys: new Set(facts.map((fact) => `${fact.id}::${fact.subject}`)),
  };
}
