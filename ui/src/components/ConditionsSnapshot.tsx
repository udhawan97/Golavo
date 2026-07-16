import type {
  ConditionsLocation,
  ConditionsSnapshot as Snapshot,
  ConditionsTeam,
  TravelRoute,
  WorldMapFeature,
} from "../lib/contract";
import type { ReactNode } from "react";
import { fetchMatchConditions, fetchWorldMap } from "../lib/api";
import { useAsync } from "../lib/hooks";
import {
  claimSourceId,
  ContextProvenance,
  FactSource,
} from "./ContextProvenance";
import {
  CalendarIcon,
  ClockIcon,
  GlobeIcon,
  InfoIcon,
  PinIcon,
  PitchIcon,
  SunIcon,
} from "./icons";
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

function gapSummary(team: ConditionsTeam): { value: string; unit: string; detail: string } {
  const gap = team.kickoff_gap;
  if (gap.status !== "available") {
    return { value: "—", unit: "not resolved", detail: "Prior match timing unavailable" };
  }
  if (gap.precision === "exact" && gap.complete_days !== null && gap.elapsed_hours !== null) {
    return {
      value: gap.complete_days.toLocaleString(),
      unit: "complete days",
      detail: `${gap.elapsed_hours.toLocaleString()} hours between kickoffs`,
    };
  }
  if (gap.precision === "calendar-day" && gap.calendar_gap_days !== null) {
    return {
      value: gap.calendar_gap_days.toLocaleString(),
      unit: "calendar days",
      detail: "Date-level interval",
    };
  }
  return { value: "—", unit: "not resolved", detail: "Prior match timing unavailable" };
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

function VenueValue({ snapshot }: { snapshot: Snapshot }) {
  const venue = snapshot.match.venue;
  if (venue.status !== "available" || !venue.name) {
    return <>Not resolved — no reviewed stadium assignment</>;
  }
  const nameSourceId = claimSourceId(venue.provenance.canonical_label);
  const capacitySourceId = claimSourceId(venue.provenance.capacity);
  const sharedSource = venue.capacity !== null && nameSourceId === capacitySourceId;
  return (
    <span className="conditions-venue-value">
      <span>
        {venue.name}{venue.capacity !== null && sharedSource ? ` · ${venue.capacity.toLocaleString()} capacity` : ""}
        <FactSource sourceId={nameSourceId} />
      </span>
      {venue.capacity !== null && !sharedSource && (
        <span>{venue.capacity.toLocaleString()} capacity<FactSource sourceId={capacitySourceId} /></span>
      )}
    </span>
  );
}

function ConditionFact({
  icon,
  label,
  available,
  children,
}: {
  icon: ReactNode;
  label: string;
  available: boolean;
  children: ReactNode;
}) {
  return (
    <div className={`conditions-fact-card${available ? " is-resolved" : " is-unresolved"}`}>
      <span className="conditions-fact-card__icon">{icon}</span>
      <div>
        <dt>{label}</dt>
        <dd>{children}</dd>
      </div>
    </div>
  );
}

function ConditionsSectionHead({
  id,
  eyebrow,
  title,
  children,
}: {
  id: string;
  eyebrow: string;
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="conditions-section-head">
      <div>
        <span className="upper">{eyebrow}</span>
        <h3 id={id}>{title}</h3>
      </div>
      {children}
    </div>
  );
}

function CoverageStrip({ resolved, total }: { resolved: number; total: number }) {
  return (
    <div className="conditions-coverage-strip" aria-label={`${resolved} of ${total} match-setting fields resolved`}>
      <span className="conditions-coverage-strip__dots" aria-hidden="true">
        {Array.from({ length: total }, (_, index) => (
          <i key={index} className={index < resolved ? "is-resolved" : undefined} />
        ))}
      </span>
      <small>{resolved}/{total} resolved</small>
    </div>
  );
}

function TeamRecoveryCard({ team, sourceId }: { team: ConditionsTeam; sourceId: string }) {
  const gap = gapSummary(team);
  const gapAvailable = team.kickoff_gap.status === "available";
  return (
    <article className={`conditions-team conditions-team--${team.side}`}>
      <header className="conditions-team__head">
        <span className="conditions-team__crest" aria-hidden="true"><PitchIcon size={18} /></span>
        <div>
          <span className="upper">{team.side} team</span>
          <h4>{team.team}</h4>
        </div>
      </header>

      <div className={`conditions-team__timeline${gapAvailable ? " is-resolved" : " is-unresolved"}`} aria-label={gapLabel(team)}>
        <span className="upper conditions-team__timeline-label">{gapTerm(team)}</span>
        <div className="conditions-team__gap">
          <strong className="num">{gap.value}</strong>
          <span>{gap.unit}</span>
          <small>{gap.detail}</small>
        </div>
        <div className="conditions-team__track" aria-hidden="true">
          <span><CalendarIcon size={14} /></span>
          <i />
          <span><PitchIcon size={14} /></span>
        </div>
        <div className="conditions-team__track-labels" aria-hidden="true">
          <small>Previous match</small>
          <small>This kickoff</small>
        </div>
        {gapAvailable && <FactSource sourceId={sourceId} derived />}
      </div>

      <dl className="conditions-team__details">
        <div>
          <dt><PinIcon size={14} /> Travel from</dt>
          <dd>
            {team.travel.origin?.status === "available" ? placeLabel(team.travel.origin) : "Not resolved"}
            {team.travel.origin?.status === "available" && <FactSource sourceId="geonames" />}
          </dd>
        </div>
        <div>
          <dt><GlobeIcon size={14} /> Great-circle distance</dt>
          <dd>
            {team.travel.distance_km === null ? "Not resolved" : `${Math.round(team.travel.distance_km).toLocaleString()} km`}
            {team.travel.distance_km !== null && <FactSource sourceId="geonames" derived />}
          </dd>
        </div>
      </dl>

      <p className="conditions-coverage-note"><InfoIcon size={14} />{team.kickoff_gap.coverage_label}</p>
    </article>
  );
}

function EmptyTravelMap() {
  return (
    <figure className="conditions-map-empty">
      <div className="conditions-map-empty__art" aria-hidden="true">
        <span className="conditions-map-empty__globe"><GlobeIcon size={38} /></span>
        <span className="conditions-map-empty__route"><i /><i /><i /></span>
        <span className="conditions-map-empty__pin"><PinIcon size={24} /></span>
      </div>
      <figcaption>
        <div>
          <span className="upper">Route view</span>
          <strong>Map waiting for location coverage</strong>
          <p>Both the current venue and previous match locations must resolve before Golavo draws a route.</p>
        </div>
        <span className="chip chip--neutral">Fail-closed</span>
      </figcaption>
    </figure>
  );
}

export function SnapshotBody({ snapshot }: { snapshot: Snapshot }) {
  const location = snapshot.match.location;
  const venue = snapshot.match.venue;
  const localKickoffAvailable = snapshot.match.local_kickoff.status === "available";
  const resolvedFacts = [
    location.status === "available",
    venue.status === "available",
    localKickoffAvailable,
    location.elevation_m !== null,
  ].filter(Boolean).length;
  const gapSourceId = snapshot.match.source_refs[0]?.source_id ?? "local match index";
  return (
    <>
      <section className="conditions-facts" aria-labelledby="conditions-setting-title">
        <ConditionsSectionHead id="conditions-setting-title" eyebrow="Match setting" title="Venue & kickoff">
          <CoverageStrip resolved={resolvedFacts} total={4} />
        </ConditionsSectionHead>
        <dl>
          <ConditionFact icon={<PinIcon size={18} />} label="Match location" available={location.status === "available"}>
            {location.status === "available" ? placeLabel(location) : "Not resolved"}
            {location.status === "available" && <FactSource sourceId="geonames" />}
          </ConditionFact>
          <ConditionFact icon={<PitchIcon size={18} />} label="Venue" available={venue.status === "available"}>
            <VenueValue snapshot={snapshot} />
          </ConditionFact>
          <ConditionFact icon={<ClockIcon size={18} />} label="Local kickoff" available={localKickoffAvailable}>
            {conditionsLocalKickoffLabel(snapshot)}
            {localKickoffAvailable && <FactSource sourceId="geonames" derived />}
          </ConditionFact>
          <ConditionFact icon={<GlobeIcon size={18} />} label="Elevation" available={location.elevation_m !== null}>
            {location.elevation_m === null ? "Not resolved" : `${location.elevation_m.toLocaleString()} m`}
            {location.elevation_m !== null && <FactSource sourceId="geonames" />}
          </ConditionFact>
        </dl>
        {location.status === "available" && (
          <p className="conditions-location-meta num">
            <PinIcon size={13} />
            {location.latitude?.toFixed(3)}°, {location.longitude?.toFixed(3)}°
            <span aria-hidden="true">·</span>{location.timezone}
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
      </section>

      <section className="conditions-recovery" aria-labelledby="conditions-recovery-title">
        <ConditionsSectionHead id="conditions-recovery-title" eyebrow="Team context" title="Recovery & travel">
          <span className="conditions-section-head__note"><CalendarIcon size={14} /> Indexed match history</span>
        </ConditionsSectionHead>
        <div className="conditions-teams">
          {snapshot.teams.map((team) => (
            <TeamRecoveryCard key={team.side} team={team} sourceId={gapSourceId} />
          ))}
        </div>
      </section>

      {snapshot.travel_map.routes.length > 0 ? (
        <TravelMap routes={snapshot.travel_map.routes} />
      ) : (
        <EmptyTravelMap />
      )}

      <div className="conditions-weather" role="note">
        <span className="conditions-weather__icon"><SunIcon size={18} /></span>
        <div>
          <strong>Weather context unavailable</strong>
          <p>{snapshot.weather_context.reason}</p>
        </div>
        <span className="chip chip--neutral">No substitution</span>
      </div>

      <ContextProvenance snapshot={snapshot} />
    </>
  );
}

export function ConditionsSnapshot({ matchId }: { matchId: string }) {
  const state = useAsync(() => fetchMatchConditions(matchId), [matchId]);
  return (
    <section className="conditions-snapshot" aria-labelledby="conditions-title">
      <header className="conditions-snapshot__head">
        <div className="conditions-snapshot__identity">
          <span className="conditions-snapshot__mark" aria-hidden="true"><GlobeIcon size={22} /></span>
          <div>
            <span className="upper">Conditions snapshot</span>
            <h2 id="conditions-title">Match conditions</h2>
            <p>Venue, local kickoff, recovery and travel. Context only — never a forecast input.</p>
          </div>
        </div>
        <div className="badge-row">
          <span className="chip chip--neutral">Context only</span>
          {state.status === "ready" && state.data?.capability.status === "partial" && (
            <span className="chip chip--neutral">Partial coverage</span>
          )}
        </div>
      </header>
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
