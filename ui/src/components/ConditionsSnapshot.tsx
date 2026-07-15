import type { ConditionsLocation, ConditionsSnapshot as Snapshot, TravelRoute, WorldMapFeature } from "../lib/contract";
import { fetchMatchConditions, fetchWorldMap } from "../lib/api";
import { useAsync } from "../lib/hooks";
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

function routePath(route: TravelRoute): string {
  const origin = route.origin;
  const destination = route.destination;
  if (origin.longitude === null || origin.latitude === null || destination.longitude === null || destination.latitude === null)
    return "";
  const [x1, y1] = point(origin.longitude, origin.latitude);
  const [x2, y2] = point(destination.longitude, destination.latitude);
  const cx = (x1 + x2) / 2;
  const cy = Math.max(8, Math.min(y1, y2) - 18 - Math.abs(x2 - x1) * 0.08);
  return `M${x1.toFixed(1)},${y1.toFixed(1)} Q${cx.toFixed(1)},${cy.toFixed(1)} ${x2.toFixed(1)},${y2.toFixed(1)}`;
}

function placeLabel(location: ConditionsLocation | null): string {
  if (!location || location.status !== "available") return "Unknown";
  return [location.city, location.country].filter(Boolean).join(", ");
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
      <svg viewBox={`0 0 ${MAP_WIDTH} ${MAP_HEIGHT}`} role="img" aria-label="Travel routes from each team’s previous indexed match to this match">
        <title>Travel from each team’s previous indexed match</title>
        <g className="conditions-map__land">
          {state.data.features.map((feature, index) => (
            <path key={`${feature.properties.iso_a2 ?? feature.properties.name ?? "land"}-${index}`} d={worldFeaturePath(feature)} />
          ))}
        </g>
        <g className="conditions-map__routes">
          {routes.map((route) => {
            const d = routePath(route);
            if (!d || route.origin.longitude === null || route.origin.latitude === null || route.destination.longitude === null || route.destination.latitude === null)
              return null;
            const [x1, y1] = point(route.origin.longitude, route.origin.latitude);
            const [x2, y2] = point(route.destination.longitude, route.destination.latitude);
            return (
              <g key={route.side} className={`conditions-map__route conditions-map__route--${route.side}`}>
                <path d={d} />
                <circle cx={x1} cy={y1} r="4" />
                <circle cx={x2} cy={y2} r="5" />
              </g>
            );
          })}
        </g>
      </svg>
      <figcaption>
        {routes.map((route) => `${route.team}: ${placeLabel(route.origin)} → ${placeLabel(route.destination)} · ${Math.round(route.distance_km).toLocaleString()} km`).join(" · ")}
      </figcaption>
    </figure>
  );
}

export function SnapshotBody({ snapshot }: { snapshot: Snapshot }) {
  const location = snapshot.match.location;
  return (
    <>
      <div className="conditions-facts">
        <dl>
          <div><dt>Match city</dt><dd>{placeLabel(location)}</dd></div>
          <div><dt>Venue</dt><dd>Unknown — no stadium-level source</dd></div>
          <div><dt>Local kickoff</dt><dd>{conditionsLocalKickoffLabel(snapshot)}</dd></div>
          <div><dt>Elevation</dt><dd>{location.elevation_m === null ? "Unknown" : `${location.elevation_m.toLocaleString()} m`}</dd></div>
        </dl>
        {location.status === "available" && (
          <p className="small muted num">{location.latitude?.toFixed(3)}°, {location.longitude?.toFixed(3)}° · {location.timezone}</p>
        )}
      </div>

      <div className="conditions-teams">
        {snapshot.teams.map((team) => (
          <article key={team.side}>
            <span className="upper">{team.side}</span>
            <h3>{team.team}</h3>
            <dl>
              <div><dt>Rest</dt><dd>{team.rest.days === null ? "Unknown" : `${team.rest.days} days`}</dd></div>
              <div><dt>Travel</dt><dd>{team.travel.distance_km === null ? "Unknown" : `${Math.round(team.travel.distance_km).toLocaleString()} km`}</dd></div>
              <div><dt>From</dt><dd>{placeLabel(team.travel.origin)}</dd></div>
            </dl>
          </article>
        ))}
      </div>

      {snapshot.travel_map.routes.length > 0 ? (
        <TravelMap routes={snapshot.travel_map.routes} />
      ) : (
        <p className="conditions-map-empty small muted">Travel map unavailable until both the current and previous match cities resolve in the pinned GeoNames dump.</p>
      )}

      <div className="callout callout--info conditions-weather" role="note">
        <div>
          <div className="callout__title">Weather context unavailable</div>
          <p>{snapshot.weather_context.reason}</p>
        </div>
      </div>

      <footer className="conditions-snapshot__sources">
        <span>{snapshot.sources.find((source) => source.source_id === "geonames")?.attribution}</span>
        <span>{snapshot.travel_map.attribution}</span>
      </footer>
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
          <h2 id="conditions-title">Place, rest and travel</h2>
        </div>
        <span className="chip chip--neutral">Context only</span>
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
