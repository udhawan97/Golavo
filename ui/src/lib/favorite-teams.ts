export interface FavoriteTeam {
  competitionId: string;
  leagueSlug: string;
  leagueName: string;
  team: string;
}

const KEY = "golavo.favorite-teams.v1";
export const FAVORITE_TEAMS_TRANSFER_VERSION = "0.1.0" as const;
export const FAVORITE_TEAMS_TRANSFER_MAX = 50;
export const FAVORITE_TEAMS_TRANSFER_MAX_BYTES = 64 * 1024;

export interface FavoriteTeamIdentity {
  competitionId: string;
  team: string;
}

export interface FavoriteTeamsTransfer {
  schema_version: typeof FAVORITE_TEAMS_TRANSFER_VERSION;
  favorites: FavoriteTeamIdentity[];
}

function exactKeys(value: Record<string, unknown>, expected: string[]): boolean {
  const keys = Object.keys(value).sort();
  return keys.length === expected.length
    && keys.every((key, index) => key === [...expected].sort()[index]);
}

export function loadFavoriteTeams(): FavoriteTeam[] {
  try {
    const value = JSON.parse(localStorage.getItem(KEY) ?? "[]") as unknown;
    if (!Array.isArray(value)) return [];
    return value.filter((item): item is FavoriteTeam => {
      const row = item as Partial<FavoriteTeam>;
      return [row.competitionId, row.leagueSlug, row.leagueName, row.team]
        .every((field) => typeof field === "string" && field.length > 0);
    });
  } catch {
    return [];
  }
}

export function saveFavoriteTeams(value: FavoriteTeam[]): void {
  localStorage.setItem(KEY, JSON.stringify(value));
}

export function favoriteTeamsTransferJson(value: FavoriteTeam[]): string {
  const favorites = value.map(({ competitionId, team }) => ({ competitionId, team }));
  if (favorites.length > FAVORITE_TEAMS_TRANSFER_MAX)
    throw new Error(`My Teams export is limited to ${FAVORITE_TEAMS_TRANSFER_MAX} clubs`);
  return JSON.stringify({
    schema_version: FAVORITE_TEAMS_TRANSFER_VERSION,
    favorites,
  } satisfies FavoriteTeamsTransfer, null, 2) + "\n";
}

/** Parse only canonical identities. Display names and routes are deliberately
 * absent: import derives them from the current trusted league catalog. */
export function parseFavoriteTeamsTransfer(text: string): FavoriteTeamsTransfer {
  if (new TextEncoder().encode(text).length > FAVORITE_TEAMS_TRANSFER_MAX_BYTES)
    throw new Error("My Teams file is larger than 64 KiB");
  let value: unknown;
  try { value = JSON.parse(text); }
  catch { throw new Error("My Teams file is not valid JSON"); }
  if (!value || typeof value !== "object" || Array.isArray(value))
    throw new Error("My Teams file must be an object");
  const record = value as Record<string, unknown>;
  if (!exactKeys(record, ["schema_version", "favorites"])
    || record.schema_version !== FAVORITE_TEAMS_TRANSFER_VERSION
    || !Array.isArray(record.favorites))
    throw new Error("My Teams file has an unsupported shape or version");
  if (record.favorites.length > FAVORITE_TEAMS_TRANSFER_MAX)
    throw new Error(`My Teams file is limited to ${FAVORITE_TEAMS_TRANSFER_MAX} clubs`);
  const seen = new Set<string>();
  const favorites = record.favorites.map((item, index): FavoriteTeamIdentity => {
    if (!item || typeof item !== "object" || Array.isArray(item))
      throw new Error(`My Teams row ${index + 1} is invalid`);
    const row = item as Record<string, unknown>;
    if (!exactKeys(row, ["competitionId", "team"])
      || typeof row.competitionId !== "string"
      || typeof row.team !== "string"
      || !row.competitionId.trim()
      || !row.team.trim())
      throw new Error(`My Teams row ${index + 1} must contain only an exact competitionId and team`);
    const identity = `${row.competitionId}\u0000${row.team}`;
    if (seen.has(identity)) throw new Error(`My Teams row ${index + 1} duplicates an earlier club`);
    seen.add(identity);
    return { competitionId: row.competitionId, team: row.team };
  });
  return { schema_version: FAVORITE_TEAMS_TRANSFER_VERSION, favorites };
}
