import type { FollowEvent, FollowedMatch } from "../lib/contract";
import { utc } from "../lib/format";
import { useFollows } from "../lib/follow-context";

const EVENT_LABELS: Record<FollowEvent["event_type"], string> = {
  followed: "Started following",
  unfollowed: "Stopped following",
  refollowed: "Started following again",
  match_repointed: "Exact source identity updated",
  identity_unresolved: "Identity needs review",
  kickoff_changed: "Kickoff changed",
  venue_changed: "Location changed",
  score_published: "Score published",
  settlement_available: "Verified result available to check",
  settlement_recorded: "Forecast settlement recorded",
  source_revision_available: "Source revision available",
  source_conflict: "Source conflict",
  source_unavailable: "Source unavailable",
  source_recovered: "Source recovered",
};

function eventDetail(event: FollowEvent): string | null {
  if (event.event_type === "kickoff_changed") {
    const value = event.after?.kickoff_utc;
    return typeof value === "string" ? `Source-backed kickoff: ${utc(value)}` : null;
  }
  if (event.event_type === "venue_changed") {
    const city = event.after?.city;
    const country = event.after?.country;
    return [city, country].filter((value): value is string => typeof value === "string").join(", ") || null;
  }
  if (event.event_type === "score_published") {
    const home = event.after?.home_score;
    const away = event.after?.away_score;
    return typeof home === "number" && typeof away === "number" ? `${home}–${away}` : null;
  }
  if (event.event_type === "source_conflict") {
    return "Golavo retained the last verified fixture. No sealed forecast was changed.";
  }
  if (event.event_type === "identity_unresolved") {
    return "Golavo could not prove an exact stable identity and did not merge by similarity.";
  }
  return null;
}

export function FollowEventHistory({ followed }: { followed: FollowedMatch }) {
  const controller = useFollows();
  if (!followed.events.length) return null;
  return (
    <details
      className="follow-history"
      onToggle={(event) => {
        if (!event.currentTarget.open) return;
        const unread = followed.events
          .filter((item) => item.read_at_utc === null)
          .map((item) => item.event_id);
        void controller.markRead(unread);
      }}
    >
      <summary>
        Match history
        {followed.unread_event_count > 0 && (
          <span className="follow-history__count">{followed.unread_event_count} new</span>
        )}
      </summary>
      <ol className="follow-history__list">
        {followed.events.map((event) => (
          <li key={event.event_id} className="follow-history__event">
            <div>
              <b>{EVENT_LABELS[event.event_type]}</b>
              <span className="small dim">{utc(event.detected_at_utc)}</span>
            </div>
            {eventDetail(event) && <p>{eventDetail(event)}</p>}
            <p className="small dim">
              Source: <code>{event.source.source_id}</code>
              {event.source.checked_at_utc ? ` · checked ${utc(event.source.checked_at_utc)}` : ""}
            </p>
          </li>
        ))}
      </ol>
    </details>
  );
}
