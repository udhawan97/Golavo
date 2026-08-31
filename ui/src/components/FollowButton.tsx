import { BookmarkIcon } from "./icons";
import { useFollows } from "../lib/follow-context";

export function FollowButton({ matchId, compact = false }: { matchId: string; compact?: boolean }) {
  const controller = useFollows();
  const followed = controller.byMatchId.get(matchId);
  const listStatus = controller.listStatus
    ?? (controller.loading ? "loading" : controller.error ? "error" : "ready");
  const busy = listStatus === "loading" || controller.changingMatchId !== null;
  const unavailable = listStatus === "error";
  const active = followed?.subscription_state === "active";
  let label = active ? "Unfollow match" : "Follow match";
  let text = active ? "Following" : "Follow match";
  if (!controller.supported) {
    label = "Follow match — available in the local desktop app";
  } else if (unavailable) {
    label = "Follow state unavailable";
    text = "Follow unavailable";
  } else if (listStatus === "loading") {
    label = "Checking follow state";
    text = "Checking follow…";
  } else if (controller.changingMatchId === matchId) {
    text = "Saving…";
  }
  return (
    <button
      type="button"
      className={`follow-button${active ? " is-active" : ""}${compact ? " follow-button--compact" : ""}`}
      aria-pressed={active}
      aria-label={label}
      title={label}
      disabled={!controller.supported || busy || unavailable}
      onClick={() => {
        if (active && followed) void controller.unfollow(followed.follow_id, matchId);
        else void controller.follow(matchId);
      }}
    >
      <BookmarkIcon size={compact ? 14 : 17} />
      <span>{text}</span>
    </button>
  );
}
