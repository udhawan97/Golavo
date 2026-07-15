import type {
  ConditionsLocation,
  ConditionsSnapshot as Snapshot,
  ConditionsTeam,
  TravelRoute,
  WorldMapFeature,
} from "../lib/contract";
import { fetchMatchConditions, fetchWorldMap } from "../lib/api";
import { useAsync } from "../lib/hooks";
import {
  claimSourceId,
  ContextProvenance,
  FactSource,
} from "./ContextProvenance";
import { BlockSkeleton } from "./states";

const MAP_WIDTH = 720;
const MAP_HEIGHT = 360;

function point(longitude: number, latitude: number): [number, number] {
  return [((longitude + 180) / 360) * MAP_WIDTH, ((90 - latitude) / 180) * MAP_HEIGHT];
}

function ringPath(ring: number[][]): string {
  return ring
    .filter((pair) => pair.length >= 2)
    .map(([lon, lat], index) => {
      const [x, y] = point(lon, lat);
      return `${index === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ") + " Z";
}

export function worldFeaturePath(feature: WorldMapFeature): string {
  const polygons = feature.geometry.type === "Polygon"
    ? [feature.geometry.coordinates as number[][][]]
    : feature.geometry.coordinates as number[][][][];
  return polygons.flatMap((polygon) => polygon.map(ringPath)).join(" ");
}

function curvedPath(lon1: number, lat1: number, lon2: number, lat2: number): string {
  const [x1, y1] = point(lon1, lat1);
  const [x2, y2] = point(lon2, lat2);
  const cx = (x1 + x2) / 2;
  const cy = Math.max(8, Math.min(y1, y2) - 18 - Math.abs(x2 - x1) * 0.08);
  return `M${x1.toFixed(1)},${y1.toFixed(1)} Q${cx.toFixed(1)},${cy.toFixed(1)} ${x2.toFixed(1)},${y2.toFixed(1)}`;
}

/** Return the shortest visual route, split at the antimeridian when required. */
export function routePaths(route: TravelRoute): string[] {
  const { origin, destination } = route;
  if (
    origin.longitude === null || origin.latitude === null
    || destination.longitude === null || destination.latitude === null
  ) return [];

  const lon1 = origin.longitude;
  const lat1 = origin.latitude;
  const lon2 = destination.longitude;
  const lat2 = destination.latitude;
  let unwrappedLon2 = lon2;
  if (unwrappedLon2 - lon1 > 180) unwrappedLon2 -= 360;
  if (unwrappedLon2 - lon1 < -180) unwrappedLon2 += 360;
  if (unwrappedLon2 >= -180 && unwrappedLon2 <= 180) {
    return [curvedPath(lon1, lat1, lon2, lat2)];
  }

  const boundary = unwrappedLon2 > 180 ? 180 : -180;
  const wrappedBoundary = boundary === 180 ? -180 : 180;
  const fraction = (boundary - lon1) / (unwrappedLon2 - lon1);
  const boundaryLatitude = lat1 + (lat2 - lat1) * fraction;
  return [
    curvedPath(lon1, lat1, boundary, boundaryLatitude),
    curvedPath(wrappedBoundary, boundaryLatitude, lon2, lat2),
  ];
}

function placeLabel(location: ConditionsLocation | null): string {
  if (!location || location.status !== "available") return "Unknown";
  return [location.city, location.country].filter(Boolean).join(", ");
}

function gapLabel(team: ConditionsTeam): string {
  const gap = team.kickoff_gap;
  if (gap.status !== "available") return "Unknown";
  if (gap.precision === "exact" && gap.complete_days !== null && gap.elapsed_hours !== null) {
    return `${gap.complete_days} complete days · ${gap.elapsed_hours.toLocaleString()} hours`;
  }
  if (gap.precision === "calendar-day" && gap.calendar_gap_days !== null) {
    return `${gap.calendar_gap_days} calendar days`;
  }
  return "Unknown";
}

function gapTerm(team: ConditionsTeam): string {
  if (team.kickoff_gap.precision === "exact") return "Kickoff gap";
  if (team.kickoff_gap.precision === "calendar-day") return "Calendar gap";
  return "Prior-match gap";
}

export function conditionsLocalKickoffLabel(snapshot: Snapshot): string {
  const local = snapshot.match.local_kickoff;
  if (local.status !== "available" || !local.value || !local.timezone) {
    return snapshot.match.kickoff_precision === "day"
      ? "Unknown — kickoff is date-only"
      : "Unknown — timezone not resolved";
  }
  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZone: local.timezone,
    timeZoneName: "short",
  }).format(new Date(local.value));
}

function TravelMap({ routes }: { routes: TravelRoute[] }) {
  const state = useAsync(fetchWorldMap, []);
  if (state.status === "loading") return <BlockSkeleton lines={3} />;
  if (state.status === "error" || !state.data) return <p className="small muted">Offline basemap unavailable.</p>;
  return (
    <figure className="conditions-map">
      <svg viewBox={`0 0 ${MAP_WIDTH} ${MAP_HEIGHT}`} role="img" aria-label="Great-circle routes from each team’s previous indexed match location to this match location">
        <title>Great-circle travel context from previous indexed matches</title>
        <g className="conditions-map__land">
          {state.data.features.map((feature, index) => (
            <path key={`${feature.properties.iso_a2 ?? feature.properties.name ?? "land"}-${index}`} d={worldFeaturePath(feature)} />
          ))}
        </g>
        <g className="conditions-map__routes">
          {routes.map((route) => {
            const paths = routePaths(route);
            if (
              paths.length === 0 || route.origin.longitude === null || route.origin.latitude === null
              || route.destination.longitude === null || route.destination.latitude === null
            ) return null;
            const [x1, y1] = point(route.origin.longitude, route.origin.latitude);
            const [x2, y2] = point(route.destination.longitude, route.destination.latitude);
            return (
              <g key={route.side} className={`conditions-map__route conditions-map__route--${route.side}`}>
                {paths.map((path, index) => <path key={index} d={path} />)}
                <circle cx={x1} cy={y1} r="4" />
                <circle cx={x2} cy={y2} r="5" />
              </g>
            );
          })}
        </g>
      </svg>
      <figcaption>
        <span>{routes.map((route) => `${route.team}: ${placeLabel(route.origin)} → ${placeLabel(route.destination)} · ${Math.round(route.distance_km).toLocaleString()} km`).join(" · ")}</span>
        <FactSource sourceId="natural-earth" />
      </figcaption>
    </figure>
  );
}

function VenueFact({ snapshot }: { snapshot: Snapshot }) {
  const venue = snapshot.match.venue;
  if (venue.status !== "available" || !venue.name) {
    return <dd>Unknown — no reviewed stadium assignment</dd>;
  }
  const nameSourceId = claimSourceId(venue.provenance.canonical_label);
  const capacitySourceId = claimSourceId(venue.provenance.capacity);
  const sharedSource = venue.capacity !== null && nameSourceId === capacitySourceId;
  return (
    <dd className="conditions-venue-value">
      <span>
        {venue.name}{venue.capacity !== null && sharedSource ? ` · ${venue.capacity.toLocaleString()} capacity` : ""}
        <FactSource sourceId={nameSourceId} />
      </span>
      {venue.capacity !== null && !sharedSource && (
        <span>{venue.capacity.toLocaleString()} capacity<FactSource sourceId={capacitySourceId} /></span>
      )}
    </dd>
  );
}

export function SnapshotBody({ snapshot }: { snapshot: Snapshot }) {
  const location = snapshot.match.location;
  const venue = snapshot.match.venue;
  return (
    <>
      <div className="conditions-facts">
        <dl>
          <div>
            <dt>Match location</dt>
            <dd>{placeLabel(location)}{location.status === "available" && <FactSource sourceId="geonames" />}</dd>
          </div>
          <div><dt>Venue</dt><VenueFact snapshot={snapshot} /></div>
          <div>
            <dt>Local kickoff</dt>
            <dd>{conditionsLocalKickoffLabel(snapshot)}{snapshot.match.local_kickoff.status === "available" && <FactSource sourceId="geonames" derived />}</dd>
          </div>
          <div>
            <dt>Elevation</dt>
            <dd>{location.elevation_m === null ? "Unknown" : `${location.elevation_m.toLocaleString()} m`}{location.elevation_m !== null && <FactSource sourceId="geonames" />}</dd>
          </div>
        </dl>
        {location.status === "available" && (
          <p className="small muted num">
            {location.latitude?.toFixed(3)}°, {location.longitude?.toFixed(3)}° · {location.timezone}
            <FactSource sourceId="geonames" />
          </p>
        )}
        {venue.identity_link_status === "conflicting" && venue.identity_conflict_reason && (
          <div className="callout callout--warning conditions-identity-conflict" role="note">
            <div>
              <div className="callout__title">Venue identity kept separate</div>
              <p>{venue.identity_conflict_reason}</p>
              <FactSource sourceId="openfootball-worldcup-json" /> <FactSource sourceId="wikidata" />
            </div>
          </div>
        )}
      </div>

      <div className="conditions-teams">
        {snapshot.teams.map((team) => (
          <article key={team.side}>
            <span className="upper">{team.side}</span>
            <h3>{team.team}</h3>
            <dl>
              <div>
                <dt>{gapTerm(team)}</dt>
                <dd>{gapLabel(team)}{team.kickoff_gap.status === "available" && <FactSource sourceId={snapshot.match.source_refs[0]?.source_id ?? "local match index"} derived />}</dd>
              </div>
              <div>
                <dt>Great-circle</dt>
                <dd>{team.travel.distance_km === null ? "Unknown" : `${Math.round(team.travel.distance_km).toLocaleString()} km`}{team.travel.distance_km !== null && <FactSource sourceId="geonames" derived />}</dd>
              </div>
              <div>
                <dt>From</dt>
                <dd>{placeLabel(team.travel.origin)}{team.travel.origin?.status === "available" && <FactSource sourceId="geonames" />}</dd>
              </div>
            </dl>
            <p className="small muted conditions-coverage-note">{team.kickoff_gap.coverage_label}</p>
          </article>
        ))}
      </div>

      {snapshot.travel_map.routes.length > 0 ? (
        <TravelMap routes={snapshot.travel_map.routes} />
      ) : (
        <p className="conditions-map-empty small muted">Travel map unavailable until both current and previous match locations resolve in the reviewed GeoNames pack.</p>
      )}

      <div className="callout callout--info conditions-weather" role="note">
        <div>
          <div className="callout__title">Weather context unavailable</div>
          <p>{snapshot.weather_context.reason}</p>
        </div>
      </div>

      <ContextProvenance snapshot={snapshot} />
    </>
  );
}

export function ConditionsSnapshot({ matchId }: { matchId: string }) {
  const state = useAsync(() => fetchMatchConditions(matchId), [matchId]);
  return (
    <section className="conditions-snapshot" aria-labelledby="conditions-title">
      <header>
        <div>
          <span className="upper">Conditions snapshot</span>
          <h2 id="conditions-title">Place, venue, schedule and travel</h2>
        </div>
        <div className="badge-row">
          <span className="chip chip--neutral">Context only</span>
          {state.status === "ready" && state.data?.capability.status === "partial" && (
            <span className="chip chip--neutral">Partial coverage</span>
          )}
        </div>
      </header>
      <p className="conditions-snapshot__label">Context, not a model input.</p>
      {state.status === "loading" ? <BlockSkeleton lines={4} /> : state.status === "error" ? (
        <p className="muted">Conditions are unavailable from the local data bundle.</p>
      ) : state.data ? (
        <SnapshotBody snapshot={state.data} />
      ) : (
        <p className="muted">Conditions are available in the connected Golavo app; this preview does not fabricate location data.</p>
      )}
    </section>
  );
}
