import { describe, expect, it, vi } from "vitest";
import {
  CorrectionApiError,
  correctionLoadFailureState,
  fetchCorrectionCapabilities,
  saveCorrectionExport,
} from "./corrections";
import { annotationIsCurrent, mergeCorrectionLists } from "./correction-context";
import type { CorrectionProposal } from "./corrections";

describe("local correction client boundary", () => {
  it("fails closed without an installed sidecar and does not fetch", async () => {
    const network = vi.fn();
    vi.stubGlobal("fetch", network);

    await expect(fetchCorrectionCapabilities()).rejects.toMatchObject({
      name: "CorrectionApiError",
      reasonCode: "desktop_required",
    });
    expect(network).not.toHaveBeenCalled();
  });

  it("requires the native save bridge for correction exports", () => {
    expect(() => saveCorrectionExport(`cx_${"a".repeat(64)}`)).toThrow(
      CorrectionApiError,
    );
  });

  it("calls only an exact 404 not found and keeps network failures recoverable", () => {
    expect(correctionLoadFailureState(new CorrectionApiError("missing", 404, "missing"))).toBe("not_found");
    expect(correctionLoadFailureState(new CorrectionApiError("offline", 503, "unavailable"))).toBe("error");
    expect(correctionLoadFailureState(new TypeError("Failed to fetch"))).toBe("error");
  });

  it("hides an accepted annotation after the authoritative index changes", () => {
    const proposal = {
      local_visibility: "local_annotation",
      target: { index_fingerprint: "a".repeat(64) },
    } as CorrectionProposal;
    expect(annotationIsCurrent(proposal, "a".repeat(64))).toBe(true);
    expect(annotationIsCurrent(proposal, "b".repeat(64))).toBe(false);
    expect(annotationIsCurrent(proposal, null)).toBe(false);
  });

  it("appends correction pages without hiding or duplicating earlier proposals", () => {
    const first = { proposal_id: "cp_first" } as CorrectionProposal;
    const second = { proposal_id: "cp_second" } as CorrectionProposal;
    const merged = mergeCorrectionLists(
      { schema_version: "0.1.0", items: [first], total: 2, limit: 100, offset: 0 },
      { schema_version: "0.1.0", items: [first, second], total: 2, limit: 100, offset: 1 },
    );
    expect(merged.items.map((item) => item.proposal_id)).toEqual(["cp_first", "cp_second"]);
    expect(merged.total).toBe(2);
  });
});
