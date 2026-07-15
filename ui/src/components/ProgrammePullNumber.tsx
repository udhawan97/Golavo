import type { ProgrammePullNumber as PullNumber } from "../lib/insights";

export function ProgrammePullNumber({ pull }: { pull: PullNumber | null }) {
  if (!pull) return null;
  return (
    <aside className="programme-pull" aria-label={pull.ariaLabel}>
      <div className="programme-pull__stat">
        <span className="upper">{pull.label}</span>
        <strong className="programme-pull__value num mono">{pull.value}</strong>
      </div>
      <p>{pull.takeaway}</p>
    </aside>
  );
}
