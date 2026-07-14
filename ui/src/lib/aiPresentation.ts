import type { NarrationClaim } from "./ai";
import type { Outcome, Probs } from "./contract";

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

/** Turn a deterministic engine outcome into reader-facing fixture copy. */
export function presentOutcome(outcome: Outcome, homeTeam: string, awayTeam: string): string {
  if (outcome === "home") return homeTeam;
  if (outcome === "away") return awayTeam;
  return "Draw";
}

/** Pick the largest sealed probability without introducing an AI judgement. */
export function leadingOutcomeFromProbs(probs: Probs | null): Outcome | null {
  if (!probs) return null;
  const ranked: Array<[Outcome, number]> = [
    ["home", probs.home],
    ["draw", probs.draw],
    ["away", probs.away],
  ];
  ranked.sort((left, right) => right[1] - left[1]);
  return ranked[0][0];
}

export function presentAiClaims(claims: NarrationClaim[]): AiPresentation {
  return {
    story: claims[0] ?? null,
    signals: claims.slice(1, 4),
    notes: claims.slice(4),
  };
}
