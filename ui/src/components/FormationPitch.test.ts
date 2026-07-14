import { describe, expect, it } from "vitest";
import { parseFormation } from "./FormationPitch";

describe("parseFormation", () => {
  it("accepts conventional three- to five-line shapes", () => {
    expect(parseFormation("4-4-2")).toEqual([4, 4, 2]);
    expect(parseFormation("4–2–3–1")).toEqual([4, 2, 3, 1]);
    expect(parseFormation(" 3-4-2-1 ")).toEqual([3, 4, 2, 1]);
  });

  it("fails closed on malformed or non-ten-player shapes", () => {
    expect(parseFormation("4-3-2")).toBeNull();
    expect(parseFormation("4-0-6")).toBeNull();
    expect(parseFormation("four-four-two")).toBeNull();
    expect(parseFormation("4-4")).toBeNull();
  });
});
