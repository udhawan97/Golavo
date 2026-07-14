import type { NarrationClaim } from "./ai";

/**
 * A deterministic reading order for the AI response. The server owns every
 * word; this helper only places the existing ordered claims into progressively
 * deeper UI shelves. It never infers meaning from prose or manufactures copy.
 */
export interface AiPresentation {
  story: NarrationClaim | null;
  signals: NarrationClaim[];
  notes: NarrationClaim[];
}

/** Replace bare engine outcome tokens with the fixture labels already visible
 * in the cockpit. Local models sometimes return `home` or `away` verbatim;
 * those are implementation terms, not useful verdict copy for a reader. */
export function presentVerdictText(text: string, homeTeam: string, awayTeam: string): string {
  const outcome = text.trim().toLocaleLowerCase();
  if (outcome === "home" || outcome === "home win" || outcome === "the home side") {
    return homeTeam;
  }
  if (outcome === "away" || outcome === "away win" || outcome === "the away side") {
    return awayTeam;
  }
  if (outcome === "draw" || outcome === "a draw") return "Draw";
  return text;
}

export function presentAiClaims(claims: NarrationClaim[]): AiPresentation {
  return {
    story: claims[0] ?? null,
    signals: claims.slice(1, 4),
    notes: claims.slice(4),
  };
}
