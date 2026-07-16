import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { ResearchCandidate } from "../lib/research";
import {
  CandidateCard,
  MAX_RESEARCH_PAGES,
  RESEARCH_POLL_FAILURE_LIMIT,
  claimResearchCreation,
  nextResearchPollFailure,
  researchSelectionState,
} from "./MatchResearch";

const candidate: ResearchCandidate = {
  candidate_id: `cf_${"a".repeat(64)}`,
  run_id: `rr_${"b".repeat(32)}`,
  authority: "untrusted_candidate",
  state: "review_required",
  correction_type: "team_alias",
  target: { match_id: "match-1", index_fingerprint: "f".repeat(64), entity_id: "Q142" },
  proposed: { alias: "Les Bleus" },
  source: {
    source_id: "wikidata",
    canonical_url: "https://www.wikidata.org/wiki/Q142",
    retrieved_at_utc: "2026-07-16T00:00:00Z",
    revision_id: "123",
    license: "CC0-1.0",
    license_url: "https://creativecommons.org/publicdomain/zero/1.0/",
    attribution: "Wikidata contributors",
    modifications: "normalized plaintext excerpt",
    license_namespace: "enrichment-cc0",
  },
  evidence: {
    capture_id: `rc_${"c".repeat(64)}`,
    raw_sha256: "d".repeat(64),
    canonical_text_sha256: "e".repeat(64),
    exact_quote: "Aliases: Les Bleus",
  },
  extractor: { kind: "deterministic", id: "wikidata-entity-v1", model: null },
  queued_proposal_id: null,
};

describe("MatchResearch selection and queue guards", () => {
  it("disables only unchecked pages when the four-page limit is reached", () => {
    expect(researchSelectionState(MAX_RESEARCH_PAGES, false)).toEqual({
      disabled: true,
      message: "4 of 4 pages selected. Selection limit reached; remove one to choose another.",
    });
    expect(researchSelectionState(MAX_RESEARCH_PAGES, true).disabled).toBe(false);
    expect(researchSelectionState(3, false).disabled).toBe(false);
  });

  it("disables and labels the queue action while it is pending", () => {
    const html = renderToStaticMarkup(
      React.createElement(CandidateCard, {
        candidate,
        queued: false,
        pending: true,
        onQueue: () => undefined,
      }),
    );
    expect(html).toContain("disabled=\"\"");
    expect(html).toContain("aria-busy=\"true\"");
    expect(html).toContain("Adding to correction queue…");
  });

  it("claims run creation synchronously so a second click cannot create another run", () => {
    const lock = { current: false };
    expect(claimResearchCreation(lock)).toBe(true);
    expect(claimResearchCreation(lock)).toBe(false);
  });

  it("bounds failed status polls instead of retrying forever", () => {
    let failures = 0;
    for (let index = 1; index <= RESEARCH_POLL_FAILURE_LIMIT; index += 1) {
      const next = nextResearchPollFailure(failures);
      failures = next.count;
      expect(next.paused).toBe(index === RESEARCH_POLL_FAILURE_LIMIT);
    }
  });
});
