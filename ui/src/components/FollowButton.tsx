import { BookmarkIcon } from "./icons";
import { useFollows } from "../lib/follow-context";

export function FollowButton({ matchId, compact = false }: { matchId: string; compact?: boolean }) {
  const controller = useFollows();
  const followed = controller.byMatchId.get(matchId);
  const busy = controller.changingMatchId === matchId;
  const active = followed?.subscription_state === "active";
  const label = !controller.supported
    ? "Follow match — available in the local desktop app"
    : active ? "Unfollow match" : "Follow match";
  return (
    <button
      type="button"
      className={`follow-button${active ? " is-active" : ""}${compact ? " follow-button--compact" : ""}`}
      aria-pressed={active}
      aria-label={label}
      title={label}
      disabled={!controller.supported || busy}
      onClick={() => {
        if (active && followed) void controller.unfollow(followed.follow_id, matchId);
        else void controller.follow(matchId);
      }}
    >
      <BookmarkIcon size={compact ? 14 : 17} />
      <span>{busy ? "Saving…" : active ? "Following" : "Follow match"}</span>
    </button>
  );
}
