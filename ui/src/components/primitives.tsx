import { useEffect, useId, useRef, useState } from "react";
import type { ReactNode } from "react";
import type { ArtifactStatus, Horizon, Probs, Uncertainty } from "../lib/contract";
import { HORIZON_LABELS, STATUS_LABELS } from "../lib/contract";
import { largestRemainder, shortHash } from "../lib/format";
import { useCopy } from "../lib/hooks";
import { CheckIcon, CopyIcon, InfoIcon } from "./icons";

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
  // Whole-number labels that still sum to 100 — widths stay exact from the raw
  // probabilities, only the displayed text is rounded.
  const [homePct, drawPct, awayPct] = largestRemainder([probs.home, probs.draw, probs.away]);
  const segs = [
    { key: "home", label: home, v: probs.home, w: homePct },
    { key: "draw", label: "Draw", v: probs.draw, w: drawPct },
    { key: "away", label: away, v: probs.away, w: awayPct },
  ] as const;
  const summary = `${home} to win ${homePct}%, draw ${drawPct}%, ${away} to win ${awayPct}%.`;
  return (
    <div className="probbar" style={{ ["--h" as string]: `${height}px` }}>
      <div className="probbar__track" role="img" aria-label={summary}>
        {segs.map((s) => (
          <div
            key={s.key}
            className={`probbar__seg probbar__seg--${s.key}`}
            style={{ width: `${s.v * 100}%` }}
            aria-hidden
            title={`${s.label}: ${s.w}%`}
          >
            {s.v >= 0.12 && <span>{s.w}%</span>}
          </div>
        ))}
      </div>
      <div className="probbar__legend" aria-hidden>
        <span className="leg"><span className="leg__sw leg__sw--home" /><b>{home}</b>&nbsp;{homePct}%</span>
        <span className="leg leg--c"><span className="leg__sw leg__sw--draw" /><b>Draw</b>&nbsp;{drawPct}%</span>
        <span className="leg leg--r"><span className="leg__sw leg__sw--away" /><b>{away}</b>&nbsp;{awayPct}%</span>
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
        aria-label={copied ? "Copied to clipboard" : "Copy to clipboard"}
      >
        {copied ? <CheckIcon /> : <CopyIcon />}
      </button>
    </span>
  );
}

/** One aligned metadata line for a page header. Each item keeps its icon and
 *  text together (no orphaned icon on wrap) and items are separated by a hairline
 *  middot via CSS. */
export function MetaLine({ children }: { children: ReactNode }) {
  return <div className="meta-line">{children}</div>;
}

export function MetaItem({ icon, children }: { icon?: ReactNode; children: ReactNode }) {
  return (
    <span className="meta-item">
      {icon && <span className="meta-item__icon" aria-hidden>{icon}</span>}
      <span>{children}</span>
    </span>
  );
}

/** A small ⓘ that reveals one guarantee in a popover — used so a page states each
 *  promise once, then offers the detail on demand instead of a wall of copy.
 *  Keyboard: focusable button, Escape closes, click-away closes. */
export function InfoPopover({ label, children }: { label: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const wrap = useRef<HTMLSpanElement>(null);
  const panelId = useId();
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (wrap.current && !wrap.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);
  return (
    <span className="pop" ref={wrap}>
      <button
        type="button"
        className="pop__btn"
        aria-expanded={open}
        aria-controls={open ? panelId : undefined}
        aria-label={label}
        onClick={() => setOpen((o) => !o)}
      >
        <InfoIcon size={15} />
      </button>
      {open && (
        <span className="pop__panel" id={panelId} role="note">
          {children}
        </span>
      )}
    </span>
  );
}

export interface TrustItem {
  icon?: ReactNode;
  label: ReactNode;
  tip?: ReactNode;
  tipLabel?: string;
}

/** The one compact trust row. States each guarantee once; the detail lives in an
 *  ⓘ popover. Never hides the truth — the strip itself is always visible. */
export function TrustStrip({ items }: { items: TrustItem[] }) {
  return (
    <div className="trust-strip">
      {items.map((it, i) => (
        <span className="trust-strip__item" key={i}>
          {it.icon && <span className="trust-strip__icon" aria-hidden>{it.icon}</span>}
          <span>{it.label}</span>
          {it.tip && <InfoPopover label={it.tipLabel ?? "More detail"}>{it.tip}</InfoPopover>}
        </span>
      ))}
    </div>
  );
}

/** A thin bar that gives a base rate a shape as well as a number. Read-only,
 *  honest: the number is always shown beside the fill. Used in insight cards and
 *  notebook fact rows. */
export function RateBar({ value, caption }: { value: number; caption?: string }) {
  const p = Math.max(0, Math.min(1, value));
  const whole = Math.round(p * 100);
  return (
    <div className="rate-bar" role="img" aria-label={caption ?? `${whole}%`}>
      <span className="rate-bar__track" aria-hidden>
        <span className="rate-bar__fill" style={{ width: `${p * 100}%` }} />
      </span>
      <span className="rate-bar__val num">{whole}%</span>
    </div>
  );
}

/** Stripe-style stat: small label over a large tabular value, optional hint.
 *  Shared by the forecast metric grids and scored panel. */
export function StatTile({
  value, label, hint, tone,
}: { value: ReactNode; label: ReactNode; hint?: ReactNode; tone?: "gold" | "green" }) {
  return (
    <div className={`stat-tile${tone ? ` stat-tile--${tone}` : ""}`}>
      <div className="stat-tile__val num">{value}</div>
      <div className="stat-tile__label">{label}</div>
      {hint && <div className="stat-tile__hint">{hint}</div>}
    </div>
  );
}
