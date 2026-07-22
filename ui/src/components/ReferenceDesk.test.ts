import { describe, expect, it } from "vitest";
import type { ConditionsVenue } from "../lib/contract";
import { venueSourceRefs } from "./ReferenceDesk";

describe("Reference Desk", () => {
  it("deduplicates revision-pinned venue references across claims", () => {
    const ref = {
      source_id: "wikidata",
      source_record_id: "Q1",
      source_revision: "42",
      snapshot_sha256: "a".repeat(64),
      retrieved_at_utc: "2026-07-15T00:00:00Z",
      field: "capacity",
    };
    const venue = {
      status: "available",
      provenance: {
        canonical_label: { claim_id: "c1", source_refs: [ref] },
        capacity: { claim_id: "c2", source_refs: [ref] },
      },
    } as unknown as ConditionsVenue;

    expect(venueSourceRefs(venue)).toEqual([ref]);
  });
});
