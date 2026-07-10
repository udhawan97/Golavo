import type { ArtifactStatus, Horizon, Probs, Uncertainty } from "../lib/contract";
import { HORIZON_LABELS, STATUS_LABELS } from "../lib/contract";
import { pct, shortHash } from "../lib/format";
import { useCopy } from "../lib/hooks";
import { CheckIcon, CopyIcon } from "./icons";

export function StatusChip({ status }: { status: ArtifactStatus }) {
  return (
    <span className={`chip chip--${status}`}>
      <span className="chip__dot" aria-hidden />
      {STATUS_LABELS[status]}
    </span>
  );
}

export function HorizonChip({ horizon }: { horizon: Horizon }) {
  return (
    <span className="chip chip--horizon" title="Seal horizon before kickoff">
      {HORIZON_LABELS[horizon]}
    </span>
  );
}

const UNCERT_FILL: Record<Uncertainty, number> = { low: 1, medium: 2, high: 3 };

export function UncertaintyTag({ level }: { level: Uncertainty }) {
  const fill = UNCERT_FILL[level];
  return (
    <span className={`uncert uncert--${level}`}>
      <span className="uncert__bars" aria-hidden>
        {[1, 2, 3].map((i) => <i key={i} className={i <= fill ? "on" : ""} />)}
      </span>
      <span><span className="muted">Uncertainty</span> {level}</span>
    </span>
  );
}

/** W/D/L probability bar. Read-only, honest: percentages to one decimal, and a
 *  single accessible summary rather than per-segment noise. */
export function ProbabilityBar({
  probs, home, away, height = 40,
}: { probs: Probs; home: string; away: string; height?: number }) {
  const segs = [
    { key: "home", label: home, v: probs.home },
    { key: "draw", label: "Draw", v: probs.draw },
    { key: "away", label: away, v: probs.away },
  ] as const;
  const summary = `${home} to win ${pct(probs.home)}, draw ${pct(probs.draw)}, ${away} to win ${pct(probs.away)}.`;
  return (
    <div className="probbar" style={{ ["--h" as string]: `${height}px` }}>
      <div className="probbar__track" role="img" aria-label={summary}>
        {segs.map((s) => (
          <div
            key={s.key}
            className={`probbar__seg probbar__seg--${s.key}`}
            style={{ width: `${s.v * 100}%` }}
            aria-hidden
            title={`${s.label}: ${pct(s.v)}`}
          >
            {s.v >= 0.12 && <span>{pct(s.v)}</span>}
          </div>
        ))}
      </div>
      <div className="probbar__legend" aria-hidden>
        <span className="leg"><span className="leg__sw leg__sw--home" /><b>{home}</b>&nbsp;{pct(probs.home)}</span>
        <span className="leg leg--c"><span className="leg__sw leg__sw--draw" /><b>Draw</b>&nbsp;{pct(probs.draw)}</span>
        <span className="leg leg--r"><span className="leg__sw leg__sw--away" /><b>{away}</b>&nbsp;{pct(probs.away)}</span>
      </div>
    </div>
  );
}

/** Monospace, copyable hash/id. Truncates for display; the full value is in the
 *  title and copied verbatim. */
export function Hash({ value, mono = true, truncate = true }: { value: string; mono?: boolean; truncate?: boolean }) {
  const [copied, copy] = useCopy();
  const shown = truncate ? shortHash(value) : value;
  return (
    <span className="hash">
      <code className={mono ? "mono" : undefined} title={value}>{shown}</code>
      <button
        type="button"
        className={`hash__btn${copied ? " copied" : ""}`}
        onClick={() => copy(value, "h")}
        aria-label={copied ? "Copied" : `Copy ${value}`}
      >
        {copied ? <CheckIcon /> : <CopyIcon />}
      </button>
    </span>
  );
}
