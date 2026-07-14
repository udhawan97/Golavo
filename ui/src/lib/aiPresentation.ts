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

export function presentAiClaims(claims: NarrationClaim[]): AiPresentation {
  return {
    story: claims[0] ?? null,
    signals: claims.slice(1, 4),
    notes: claims.slice(4),
  };
}
