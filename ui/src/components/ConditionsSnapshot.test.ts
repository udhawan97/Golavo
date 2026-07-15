import { describe, expect, it } from "vitest";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import type { ConditionsSnapshot, WorldMapFeature } from "../lib/contract";
import { SnapshotBody, conditionsLocalKickoffLabel, worldFeaturePath } from "./ConditionsSnapshot";

function snapshot(precision: "exact" | "day"): ConditionsSnapshot {
  return {
    schema_version: "0.2.0",
    label: "Context, not a model input.",
    match: {
      match_id: "m_test",
      kickoff_utc: "2026-07-15T19:00:00Z",
      kickoff_precision: precision,
      local_kickoff: { status: "unknown", reason: "timezone-unknown", value: null, timezone: null },
      venue: { status: "unknown", name: null, reason: "no-stadium-level-source" },
      location: {
        status: "unknown", reason: "unresolved", city: "Somewhere", country: "Country",
        latitude: null, longitude: null, elevation_m: null, timezone: null, source_id: null,
      },
    },
    teams: [],
    travel_map: { status: "unknown", source_id: "natural-earth", attribution: "Made with Natural Earth.", routes: [] },
    weather_context: {
      status: "blocked",
      reason_code: "no_leakage_safe_historical_forecast_source",
      reason: "Observed weather is not substituted.",
      model_input: false,
      source_id: null,
    },
    sources: [],
  };
}

describe("Conditions Snapshot honesty", () => {
  it("distinguishes a missing timezone from a day-only kickoff", () => {
    expect(conditionsLocalKickoffLabel(snapshot("exact"))).toBe("Unknown — timezone not resolved");
    expect(conditionsLocalKickoffLabel(snapshot("day"))).toBe("Unknown — kickoff is date-only");
  });

  it("projects polygon rings into a closed SVG path", () => {
    const feature: WorldMapFeature = {
      type: "Feature",
      properties: { name: "Test", iso_a2: "TT" },
      geometry: { type: "Polygon", coordinates: [[[0, 0], [10, 0], [10, 10], [0, 0]]] },
    };
    const path = worldFeaturePath(feature);
    expect(path).toContain("M360.0,180.0");
    expect(path.trim().endsWith("Z")).toBe(true);
  });

  it("shows weather as blocked context and never as a value", () => {
    const html = renderToStaticMarkup(createElement(SnapshotBody, { snapshot: snapshot("exact") }));
    expect(html).toContain("Weather context unavailable");
    expect(html).toContain("Observed weather is not substituted");
    expect(html).not.toContain("Temperature");
  });
});
