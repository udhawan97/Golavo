/** A team dossier is always addressed by its competition-scoped exact identity. */
export function teamDossierHref(competitionId: string, team: string): string {
  return `#/team/${encodeURIComponent(competitionId)}/${encodeURIComponent(team)}`;
}

function safeDecode(segment: string): string {
  try {
    return decodeURIComponent(segment);
  } catch {
    return segment;
  }
}

/** Parse the exact route shape used by App without letting malformed escapes unmount it. */
export function parseTeamDossierPath(
  path: string,
): { competitionId: string; team: string } | null {
  const match = path.match(/^\/team\/([^/]+)\/(.+)$/);
  if (!match) return null;
  return { competitionId: safeDecode(match[1]), team: safeDecode(match[2]) };
}
