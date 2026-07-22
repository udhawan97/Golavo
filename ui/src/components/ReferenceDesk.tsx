import type { ConditionsVenue, ContextSourceRef } from "../lib/contract";
import { fetchMatchConditions } from "../lib/api";
import { useAsync } from "../lib/hooks";
import { BookIcon, PinIcon } from "./icons";
import { BlockSkeleton } from "./states";

export function venueSourceRefs(venue: ConditionsVenue): ContextSourceRef[] {
  const seen = new Set<string>();
  const refs: ContextSourceRef[] = [];
  for (const claim of Object.values(venue.provenance)) {
    for (const ref of claim.source_refs) {
      const key = `${ref.source_id}:${ref.source_record_id}:${ref.source_revision}`;
      if (!seen.has(key)) {
        seen.add(key);
        refs.push(ref);
      }
    }
  }
  return refs.sort((a, b) =>
    `${a.source_id}:${a.source_record_id}`.localeCompare(`${b.source_id}:${b.source_record_id}`),
  );
}

export function ReferenceDesk({ matchId, home, away }: { matchId: string; home: string; away: string }) {
  const state = useAsync(() => fetchMatchConditions(matchId), [matchId]);
  if (state.status === "loading") return <BlockSkeleton lines={2} />;
  if (state.status === "error" || !state.data) return null;
  const venue = state.data.match.venue;
  const refs = venueSourceRefs(venue);
  return (
    <section className="reference-desk surface" aria-labelledby="reference-desk-title">
      <header className="section-heading">
        <span className="section-heading__icon"><BookIcon /></span>
        <div>
          <p className="eyebrow">Revision-pinned facts</p>
          <h2 id="reference-desk-title">Reference Desk</h2>
          <p>Display context only. Nothing here enters a forecast.</p>
        </div>
      </header>
      <div className="two-col">
        <article className="card">
          <h3><PinIcon /> Venue</h3>
          {venue.status === "available" ? (
            <>
              <p><strong>{venue.name}</strong></p>
              <p className="small muted">
                {venue.capacity ? `${venue.capacity.toLocaleString()} recorded capacity · ` : ""}
                identity {venue.identity_link_status}
              </p>
              {venue.identity_conflict_reason && <p className="small">{venue.identity_conflict_reason}</p>}
              <ul className="small provenance-list">
                {refs.map((ref) => (
                  <li key={`${ref.source_id}:${ref.source_record_id}:${ref.source_revision}`}>
                    {ref.source_id} · {ref.source_record_id} · revision <code>{ref.source_revision}</code>
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <p className="muted">No reviewed, revision-pinned venue assignment for this fixture.</p>
          )}
        </article>
        <article className="card">
          <h3>Managers</h3>
          <p><strong>{home}</strong> · not shown</p>
          <p><strong>{away}</strong> · not shown</p>
          <p className="small muted">
            Golavo has no revision-pinned manager-tenure pack for these teams, so it does not turn a
            changeable “current manager” lookup into a fact.
          </p>
        </article>
      </div>
    </section>
  );
}
