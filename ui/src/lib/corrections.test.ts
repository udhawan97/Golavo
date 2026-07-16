import { describe, expect, it, vi } from "vitest";
import {
  CorrectionApiError,
  fetchCorrectionCapabilities,
  saveCorrectionExport,
} from "./corrections";
import { annotationIsCurrent } from "./correction-context";
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

  it("hides an accepted annotation after the authoritative index changes", () => {
    const proposal = {
      local_visibility: "local_annotation",
      target: { index_fingerprint: "a".repeat(64) },
    } as CorrectionProposal;
    expect(annotationIsCurrent(proposal, "a".repeat(64))).toBe(true);
    expect(annotationIsCurrent(proposal, "b".repeat(64))).toBe(false);
    expect(annotationIsCurrent(proposal, null)).toBe(false);
  });
});
