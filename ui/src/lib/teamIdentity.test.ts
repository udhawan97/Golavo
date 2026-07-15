import { describe, expect, it } from "vitest";
import { nationalFlag, teamMonogram, teamNameDensity } from "./teamIdentity";

describe("team identity", () => {
  it("uses explicit national flags without guessing unknown teams", () => {
    expect(nationalFlag("Switzerland")).toBe("🇨🇭");
    expect(nationalFlag("Manchester United")).toBeNull();
  });

  it("creates useful monograms for club and fallback identities", () => {
    expect(teamMonogram("Manchester United")).toBe("MU");
    expect(teamMonogram("Nottingham Forest FC")).toBe("NF");
    expect(teamMonogram("Brazil")).toBe("BR");
  });

  it("only changes typography for unusually demanding names", () => {
    expect(teamNameDensity("Spain")).toBe("regular");
    expect(teamNameDensity("Manchester United")).toBe("regular");
    expect(teamNameDensity("Wolverhampton Wanderers")).toBe("compact");
    expect(teamNameDensity("Borussia Mönchengladbach")).toBe("tight");
  });
});
