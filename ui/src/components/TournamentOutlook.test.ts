import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { TournamentOutlook } from "../lib/contract";
import { TournamentOutlookBody } from "./TournamentOutlook";

const AVAILABLE: TournamentOutlook = {
  schema_version: "0.1.0",
  status: "available",
  label: "Tournament outlook — a simulation from current model fits. Not a sealed forecast.",
  tournament_id: "worldcup-2026",
  tournament_name: "2026 FIFA World Cup",
  as_of_utc: "2026-07-15T08:00:00Z",
  data_through_utc: "2026-07-12T01:00:00Z",
  outlook_rule: "ko-2026.07.1",
  method: "exact-four-team-bracket-enumeration",
  ledger_status: "never_persisted_or_scored_as_a_seal",
  snapshot_status: "result_refresh_needed",
  snapshot_note: "One result is missing.",
  semifinals: [],
  voices: ["elo_ordlogit", "dixon_coles", "equal-chance-baseline"].map((voiceId) => ({
    voice_id: voiceId as "elo_ordlogit" | "dixon_coles" | "equal-chance-baseline",
    label: voiceId,
    role: voiceId === "equal-chance-baseline" ? "baseline" as const : "voice" as const,
    draw_resolution: "declared rule",
    teams: ["Argentina", "England", "France", "Spain"].map((team) => ({
      team, reach_final: 0.5, reach_third_place_match: 0.5, champion: 0.25, third: 0.25,
    })),
    totals: { reach_final: 2, reach_third_place_match: 2, champion: 1, third: 1 },
  })),
  provenance: { index_sha256: "0".repeat(64) },
};

describe("TournamentOutlookBody", () => {
  it("keeps voices separate and labels a stale bracket snapshot", () => {
    const html = renderToStaticMarkup(createElement(TournamentOutlookBody, { outlook: AVAILABLE }));
    expect(html).toContain("Result refresh needed");
    expect(html).toContain("Ratings");
    expect(html).toContain("Goals");
    expect(html).toContain("Baseline");
    expect(html).toContain("25.0%");
    expect(html).toContain("never written to the forecast ledger");
  });

  it("renders typed unavailable copy without fabricated zeros", () => {
    const html = renderToStaticMarkup(createElement(TournamentOutlookBody, {
      outlook: { ...AVAILABLE, status: "unavailable", reason: "No bracket", voices: [] },
    }));
    expect(html).toContain("Tournament outlook unavailable");
    expect(html).toContain("No bracket");
    expect(html).not.toContain("0.0%");
  });
});
