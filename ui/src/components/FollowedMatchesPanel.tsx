import { useFollows } from "../lib/follow-context";
import { useDataRefresh } from "../lib/data-refresh-context";
import { utcDate } from "../lib/format";
import { FollowButton } from "./FollowButton";

function stateLabel(state: string): string {
  return state.replaceAll("_", " ");
}

export function FollowedMatchesPanel() {
  const follows = useFollows();
  const refresh = useDataRefresh();
  if (!follows.list.items.length) return null;
  return (
    <section className="followed-panel stack" aria-labelledby="followed-matches-heading">
      <div className="followed-panel__head">
        <div>
          <p className="eyebrow">Local watchlist</p>
          <h2 id="followed-matches-heading">Followed matches</h2>
        </div>
        <button
          type="button"
          className="btn btn--ghost"
          onClick={() => void refresh.refreshFollowedNow()}
          disabled={refresh.job?.state === "queued" || refresh.job?.state === "running"}
        >
          Check followed matches now
        </button>
      </div>
      <p className="small dim" style={{ margin: 0 }}>
        Checks use approved sources only while Golavo is running. Closing the app stops checks.
      </p>
      <div className="followed-panel__grid">
        {follows.list.items.map((item) => (
          <article className="followed-panel__item" key={item.follow_id}>
            <a href={`#/match/${encodeURIComponent(item.canonical_match_id)}`}>
              <b>{item.current.home_team} v {item.current.away_team}</b>
              <span>{item.current.competition} · {utcDate(item.current.kickoff_utc)}</span>
              <span className={`followed-panel__state followed-panel__state--${item.data_state}`}>
                {stateLabel(item.data_state)}
                {item.unread_event_count > 0 ? ` · ${item.unread_event_count} new` : ""}
              </span>
            </a>
            <FollowButton matchId={item.canonical_match_id} compact />
          </article>
        ))}
      </div>
    </section>
  );
}
