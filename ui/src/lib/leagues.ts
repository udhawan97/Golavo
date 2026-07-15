/**
 * Curated league metadata + competition ordering.
 *
 * The bundled index has no league-priority column (only per-competition match
 * counts, which measure volume, not importance — 18k friendlies would lead).
 * So "the big five + UEFA club competitions + major internationals first" is a
 * CURATED list, kept here as
 * the single source of truth for both the Leagues hub and the Matchday home.
 *
 * The competition strings are the exact values in the frozen index (verified),
 * so ranking can match on them directly.
 */
import type { MatchRow, SourceKind } from "./contract";

export interface League {
  slug: string;
  name: string;
  /** The index `competition` string (club competitions), or omitted for internationals. */
  competition?: string;
  /** Stable backend identity for capability and analytics routes. */
  competitionId?: string;
  sourceKind?: SourceKind;
  note: string;
}

/** Bundled club competitions + internationals — used by the Leagues hub and
 *  the Matchday home's quick-browse chips. */
export const LEAGUES: League[] = [
  { slug: "internationals", name: "Internationals", sourceKind: "international",
    note: "Men’s senior internationals — the one surface that refreshes on demand." },
  { slug: "premier-league", name: "Premier League", competition: "English Premier League",
    competitionId: "england-premier-league",
    note: "England · bundled 2010–11 onward (historical)." },
  { slug: "la-liga", name: "La Liga", competition: "La Liga", competitionId: "spain-la-liga",
    note: "Spain · bundled 2012–13 onward (historical)." },
  { slug: "bundesliga", name: "Bundesliga", competition: "Bundesliga",
    competitionId: "germany-bundesliga",
    note: "Germany · bundled 2010–11 onward (historical)." },
  { slug: "serie-a", name: "Serie A", competition: "Serie A", competitionId: "italy-serie-a",
    note: "Italy · bundled 2013–14 onward (historical)." },
  { slug: "ligue-1", name: "Ligue 1", competition: "Ligue 1",
    competitionId: "france-ligue-1",
    note: "France · bundled 2014–15 onward (historical)." },
  { slug: "champions-league", name: "Champions League", competition: "UEFA Champions League",
    competitionId: "uefa-champions-league",
    note: "UEFA · main-competition results from 2020–21 through 2025–26." },
  { slug: "europa-league", name: "Europa League", competition: "UEFA Europa League",
    competitionId: "uefa-europa-league",
    note: "UEFA · main-competition results from 2020–21 through 2024–25." },
  { slug: "conference-league", name: "Conference League", competition: "UEFA Conference League",
    competitionId: "uefa-conference-league",
    note: "UEFA · main-competition results from 2021–22 through 2024–25." },
];

/** The bundled club competitions, in curated order (index strings). */
export const TOP_CLUB_COMPETITIONS: readonly string[] = [
  "English Premier League", "La Liga", "Bundesliga", "Serie A", "Ligue 1",
  "UEFA Champions League", "UEFA Europa League", "UEFA Conference League",
];

/** Major international competitions, in curated order (exact index strings).
 *  Qualifiers rank just after their finals; "Friendly" is deliberately absent so
 *  it falls to the bottom tier. */
export const MAJOR_INTERNATIONAL_COMPETITIONS: readonly string[] = [
  "FIFA World Cup",
  "UEFA Euro",
  "Copa América",
  "African Cup of Nations",
  "AFC Asian Cup",
  "Gold Cup",
  "UEFA Nations League",
  "CONCACAF Nations League",
  "FIFA World Cup qualification",
  "UEFA Euro qualification",
  "African Cup of Nations qualification",
  "AFC Asian Cup qualification",
];

/** Slug for a curated league by its competition string, for "All {name} ›" links. */
export function leagueSlugFor(competition: string, sourceKind: SourceKind): string | null {
  if (sourceKind === "international") return "internationals";
  return LEAGUES.find((l) => l.competition === competition)?.slug ?? null;
}

// Tier bands leave room between them so future insertions don't reorder.
const TIER_TOP_CLUB = 0;
const TIER_MAJOR_INTL = 1000;
const TIER_OTHER = 2000;
const TIER_FRIENDLY = 9000; // 18k friendlies must never lead a results feed

/**
 * A sort key for a competition — lower ranks first. Bundled club competitions, then
 * major internationals (both in curated order), then everything else, with
 * "Friendly" pinned dead last. Ties within the "other" tier are broken
 * alphabetically by the caller.
 */
export function competitionRank(competition: string, _sourceKind: SourceKind): number {
  const club = TOP_CLUB_COMPETITIONS.indexOf(competition);
  if (club >= 0) return TIER_TOP_CLUB + club;
  const intl = MAJOR_INTERNATIONAL_COMPETITIONS.indexOf(competition);
  if (intl >= 0) return TIER_MAJOR_INTL + intl;
  if (competition === "Friendly") return TIER_FRIENDLY;
  return TIER_OTHER;
}

export interface CompetitionGroup {
  competition: string;
  sourceKind: SourceKind;
  matches: MatchRow[];
}

/**
 * Group matches by competition and order the groups by curated priority. Within
 * a group, match order is preserved (the API already sorts newest-first). Groups
 * of equal rank are ordered alphabetically for stability.
 */
export function groupMatchesByCompetition(matches: MatchRow[]): CompetitionGroup[] {
  const byComp = new Map<string, CompetitionGroup>();
  for (const m of matches) {
    const competition = m.competition ?? "Other";
    const sourceKind = (m.source_kind ?? "club") as SourceKind;
    const key = `${competition}|${sourceKind}`;
    let group = byComp.get(key);
    if (!group) {
      group = { competition, sourceKind, matches: [] };
      byComp.set(key, group);
    }
    group.matches.push(m);
  }
  return Array.from(byComp.values()).sort((a, b) => {
    const ra = competitionRank(a.competition, a.sourceKind);
    const rb = competitionRank(b.competition, b.sourceKind);
    if (ra !== rb) return ra - rb;
    return a.competition.localeCompare(b.competition);
  });
}
