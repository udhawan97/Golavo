import { describe, expect, it } from "vitest";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import type {
  ConditionsLocation,
  ConditionsSnapshot,
  ContextDerivation,
  TravelRoute,
  WorldMapFeature,
} from "../lib/contract";
import {
  SnapshotBody,
  conditionsLocalKickoffLabel,
  routePaths,
  worldFeaturePath,
} from "./ConditionsSnapshot";

const derivation: ContextDerivation = {
  generator: "golavo-derived-context",
  algorithm_id: "test-method",
  algorithm_version: "1",
  formula: "deterministic test formula",
  input_claim_ids: ["ctxc_input"],
};

function location(
  city: string,
  country: string,
  latitude: number,
  longitude: number,
): ConditionsLocation {
  return {
    status: "available",
    reason: null,
    entity_id: `place_${city}`,
    resolution_status: "resolved",
    city,
    country,
    latitude,
    longitude,
    elevation_m: 40,
    elevation_source: "survey",
    timezone: "America/Los_Angeles",
    source_id: "geonames",
    provenance: {},
  };
}

function snapshot(precision: "exact" | "day"): ConditionsSnapshot {
  const matchLocation = location("Inglewood", "United States", 33.962, -118.353);
  const sourceRef = {
    source_id: "martj42-international-results",
    source_record_id: "row-1",
    source_revision: "abc123",
    snapshot_sha256: "a".repeat(64),
    retrieved_at_utc: null,
    field: "identity",
  };
  return {
    schema_version: "0.3.0",
    label: "Context, not a model input.",
    capability: {
      schema_version: "0.1.0",
      status: "partial",
      display_only: true,
      model_input: false,
      context_pack_version: "2026.07.15.1",
      context_pack_sha256: "b".repeat(64),
      index_fingerprint: "c".repeat(64),
      features: { place: "partial", venue: "partial", weather: "blocked" },
      reason_codes: ["venue-coverage-is-world-cup-2026-only"],
    },
    match: {
      match_id: "m_test",
      kickoff_utc: "2026-07-15T19:00:00Z",
      kickoff_precision: precision,
      source_refs: [sourceRef],
      local_kickoff: {
        status: "unknown",
        reason: "timezone-unknown",
        value: null,
        timezone: null,
        utc_offset_minutes: null,
        tzdb_fingerprint: null,
        derivation: null,
      },
      venue: {
        status: "available",
        reason: null,
        entity_id: "venue_sofi",
        name: "SoFi Stadium",
        latitude: 33.953,
        longitude: -118.339,
        capacity: 70000,
        identity_link_status: "conflicting",
        identity_conflict_reason: "Coordinates disagree; identities remain separate.",
        provenance: {
          canonical_label: { claim_id: "ctxc_name", source_refs: [{ ...sourceRef, source_id: "openfootball-worldcup-json", field: "name" }] },
          capacity: { claim_id: "ctxc_capacity", source_refs: [{ ...sourceRef, source_id: "openfootball-worldcup-json", field: "capacity" }] },
        },
      },
      location: matchLocation,
    },
    teams: (["home", "away"] as const).map((side) => ({
      side,
      team: side === "home" ? "United States" : "Paraguay",
      team_entity_id: `team_${side}`,
      kickoff_gap: {
        status: "available",
        reason: null,
        precision: precision === "exact" ? "exact" : "calendar-day",
        elapsed_hours: precision === "exact" ? 144 : null,
        complete_days: precision === "exact" ? 6 : null,
        calendar_gap_days: precision === "day" ? 6 : null,
        previous_match_id: `m_previous_${side}`,
        previous_kickoff_utc: "2026-07-09T19:00:00Z",
        coverage_label: "Previous completed match found in Golavo's local core index.",
        derivation,
      },
      rest: {
        status: precision === "exact" ? "available" : "unknown",
        reason: precision === "exact" ? null : "kickoff-precision-is-calendar-day",
        days: precision === "exact" ? 6 : null,
        previous_match_id: `m_previous_${side}`,
        previous_kickoff_utc: "2026-07-09T19:00:00Z",
      },
      travel: {
        status: "unknown",
        reason: "previous-match-location-unknown",
        measurement: "great-circle-between-indexed-match-locations",
        distance_km: null,
        origin: null,
        destination: matchLocation,
        derivation: null,
      },
    })),
    travel_map: { status: "unknown", source_id: "natural-earth", attribution: "Made with Natural Earth.", routes: [] },
    weather_context: {
      status: "blocked",
      reason_code: "no_leakage_safe_historical_forecast_source",
      reason: "Observed weather is not substituted.",
      model_input: false,
      source_id: null,
    },
    sources: [
      {
        source_id: "geonames",
        attribution: "Data from GeoNames.",
        license: "CC-BY-4.0",
        upstream_ref: "2026-07-15",
        retrieved_at_utc: "2026-07-15T07:57:00Z",
        manifest_sha256: "d".repeat(64),
      },
      {
        source_id: "natural-earth",
        attribution: "Made with Natural Earth.",
        license: "PUBLIC-DOMAIN",
        upstream_ref: "v5.1.1",
        retrieved_at_utc: "2026-07-15T07:57:00Z",
        manifest_sha256: "e".repeat(64),
      },
    ],
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

  it("splits antimeridian routes instead of drawing across the entire map", () => {
    const origin = location("Suva", "Fiji", -18.14, 178.44);
    const destination = location("Apia", "Samoa", -13.83, -171.75);
    const route: TravelRoute = {
      side: "home",
      team: "Fiji",
      distance_km: 1140,
      origin,
      destination,
      derivation,
    };
    const paths = routePaths(route);
    expect(paths).toHaveLength(2);
    expect(paths[0]).toContain("720.0");
    expect(paths[1]).toContain("M0.0");
  });

  it("uses calendar-gap language and never rest for date-only inputs", () => {
    const html = renderToStaticMarkup(createElement(SnapshotBody, { snapshot: snapshot("day") }));
    expect(html).toContain("Calendar gap");
    expect(html).toContain("6 calendar days");
    expect(html).not.toContain("<dt>Rest</dt>");
  });

  it("discloses venue conflicts, sources, methods, and the model boundary", () => {
    const html = renderToStaticMarkup(createElement(SnapshotBody, { snapshot: snapshot("exact") }));
    expect(html).toContain("SoFi Stadium");
    expect(html).toContain("Venue identity kept separate");
    expect(html).toContain("Sources, coverage and calculations");
    expect(html).toContain("Display only. These facts and calculations are not model inputs");
  });

  it("renders the conditions as scannable fact cards, timelines, and an intentional map state", () => {
    const html = renderToStaticMarkup(createElement(SnapshotBody, { snapshot: snapshot("exact") }));
    expect(html.match(/conditions-fact-card(?: |&quot;)/g)).toHaveLength(4);
    expect(html.match(/class="conditions-team__timeline /g)).toHaveLength(2);
    expect(html).toContain("conditions-coverage-strip");
    expect(html).toContain("Map waiting for location coverage");
    expect(html).toContain("conditions-map-empty__art");
  });

  it("shows weather as blocked context and never as a value", () => {
    const html = renderToStaticMarkup(createElement(SnapshotBody, { snapshot: snapshot("exact") }));
    expect(html).toContain("Weather context unavailable");
    expect(html).toContain("Observed weather is not substituted");
    expect(html).not.toContain("Temperature");
  });
});
