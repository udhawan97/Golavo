import { describe, expect, it } from "vitest";
import { forecastProofFilename } from "./api";

describe("portable forecast proof", () => {
  it("uses the immutable artifact id as the download name", () => {
    expect(forecastProofFilename("fa_1234567890abcdef1234")).toBe(
      "fa_1234567890abcdef1234.proof.json",
    );
  });
});
