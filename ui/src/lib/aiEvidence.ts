/**
 * Evidence index for the AI read — the render-side model that replaces the
 * per-claim citation chip wall with one deduplicated, numbered legend.
 *
 * Pure functions only (unit-tested): the UI never invents a source; every
 * legend entry resolves to a source the backend envelope actually sent.
 */
import type { AiNarration, NarrationClaim, SourceRef } from "./ai";

export interface EvidenceEntry {
  /** 1-based footnote number, assigned in first-citation order. */
  index: number;
  source: SourceRef;
  /** How many claims/scenarios (and the verdict) cite this source. */
  citedBy: number;
}

export interface EvidenceIndex {
  ordered: EvidenceEntry[];
  /** Footnote number for a source id, or null when the envelope lacks it. */
  indexOf: (sourceId: string) => number | null;
}

/** Walk the narration in reading order (verdict → claims → scenarios), assign
 *  each distinct cited source a stable footnote number, and count citations.
 *  Source ids the envelope doesn't know are skipped — never fabricated. */
export function buildEvidenceIndex(
  narration: Pick<AiNarration, "claims" | "scenarios"> & { verdict?: NarrationClaim | null },
  sources: SourceRef[],
): EvidenceIndex {
  const byId = new Map(sources.map((s) => [s.source_id, s]));
  const entries = new Map<string, EvidenceEntry>();
  const items: NarrationClaim[] = [
    ...(narration.verdict ? [narration.verdict] : []),
    ...narration.claims,
    ...narration.scenarios,
  ];
  for (const item of items) {
    // Dedupe within one claim too — citing the same source twice is one vote.
    for (const sid of new Set(item.source_ids)) {
      const source = byId.get(sid);
      if (!source) continue;
      const existing = entries.get(sid);
      if (existing) existing.citedBy += 1;
      else entries.set(sid, { index: entries.size + 1, source, citedBy: 1 });
    }
  }
  const ordered = [...entries.values()];
  return {
    ordered,
    indexOf: (sourceId: string) => entries.get(sourceId)?.index ?? null,
  };
}

/** One plain-language line describing what kind of evidence a source is. */
export function sourceKindLine(kind: SourceRef["kind"]): string {
  switch (kind) {
    case "engine":
      return "deterministic engine — verified numbers";
    case "web":
      return "web source — not engine-verified";
    default:
      return "vendored data pack";
  }
}

/** Display label for a web link: the hostname without "www.", falling back to
 *  the raw string when it isn't a parseable URL. */
export function hostnameOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}
