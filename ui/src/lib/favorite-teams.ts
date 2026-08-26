export interface FavoriteTeam {
  competitionId: string;
  leagueSlug: string;
  leagueName: string;
  team: string;
}

const KEY = "golavo.favorite-teams.v1";

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
