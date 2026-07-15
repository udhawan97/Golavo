import { describe, expect, it } from "vitest";
import { narrativeJobWasLost } from "./api";

describe("narrative job polling", () => {
  it("tolerates a brief hand-off race before the first successful poll", () => {
    expect(narrativeJobWasLost(false, 1)).toBe(false);
    expect(narrativeJobWasLost(false, 2)).toBe(false);
    expect(narrativeJobWasLost(false, 3)).toBe(true);
  });

  it("stops immediately when a previously visible job disappears", () => {
    expect(narrativeJobWasLost(true, 1)).toBe(true);
  });
});
