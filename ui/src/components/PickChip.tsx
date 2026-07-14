import type { MatchRow, PickView } from "../lib/contract";

export function pickChipLabel(match: MatchRow, pick?: PickView): string {
  if (!pick) return match.is_complete ? "" : "Make your call ›";
  if (pick.status === "scored") return `${pick.scoring?.user.total ?? 0} pts`;
  if (pick.status === "void") return "Void";
  const score = `${pick.record.user_pick.home_goals}–${pick.record.user_pick.away_goals}`;
  return pick.status === "locked" ? `Locked ${score}` : `Your call ${score}`;
}

export function PickChip({ match, pick }: { match: MatchRow; pick?: PickView }) {
  const label = pickChipLabel(match, pick);
  if (!label) return null;
  return (
    <span className={`pick-chip pick-chip--${pick?.status ?? "open"}`}>
      {label}{pick?.preview && <span> · practice</span>}
    </span>
  );
}
