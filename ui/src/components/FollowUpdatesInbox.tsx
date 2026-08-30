import type { FollowEvent, FollowedMatch } from "../lib/contract";
import { utc } from "../lib/format";
import { useFollows } from "../lib/follow-context";
import { FOLLOW_EVENT_LABELS, followEventDetail } from "./FollowEventHistory";

export interface FollowInboxItem {
  match: FollowedMatch;
  event: FollowEvent;
}

const NON_UPDATE_EVENTS = new Set<FollowEvent["event_type"]>([
  "followed",
  "refollowed",
  "unfollowed",
]);

export function recentFollowUpdates(matches: FollowedMatch[], maximum = 50): FollowInboxItem[] {
  return matches.flatMap((match) => match.events
    .filter((event) => !NON_UPDATE_EVENTS.has(event.event_type))
    .map((event) => ({ match, event })))
    .sort((a, b) =>
      b.event.detected_at_utc.localeCompare(a.event.detected_at_utc)
      || b.event.event_id.localeCompare(a.event.event_id))
    .slice(0, maximum);
}

export function FollowUpdatesInbox() {
  const controller = useFollows();
  const items = recentFollowUpdates(controller.list.items);
  if (!items.length) return null;
  const unreadIds = items
    .filter(({ event }) => event.read_at_utc === null)
    .map(({ event }) => event.event_id);
  return (
    <section className="panel" aria-labelledby="follow-updates-heading">
      <div className="panel__head"><h2 id="follow-updates-heading">Recent followed-match updates</h2></div>
      <div className="panel__body stack">
        <p className="small dim">Active matches only · up to 20 typed events per match and 50 shown here. This is a recent inbox, not the complete follow archive.</p>
        {unreadIds.length > 0 && <button className="btn btn--ghost" type="button" disabled={controller.markingRead} onClick={() => void controller.markRead(unreadIds)}>{controller.markingRead ? "Marking updates…" : `Mark these ${unreadIds.length} updates read`}</button>}
        {controller.markReadError && <p className="small" role="alert">Updates could not be marked read: {controller.markReadError.message}</p>}
        <ol className="follow-history__list">
          {items.map(({ match, event }) => {
            const detail = followEventDetail(event);
            return (
              <li className="follow-history__event" key={event.event_id}>
                <div><b>{FOLLOW_EVENT_LABELS[event.event_type]}</b><span className="small dim">{utc(event.detected_at_utc)}</span></div>
                <a className="small" href={`#/match/${encodeURIComponent(match.canonical_match_id)}`}>{match.current.home_team} vs {match.current.away_team}</a>
                {detail && <p>{detail}</p>}
                <p className="small dim">Source: <code>{event.source.source_id}</code>{event.source.checked_at_utc ? ` · checked ${utc(event.source.checked_at_utc)}` : ""}</p>
              </li>
            );
          })}
        </ol>
      </div>
    </section>
  );
}
