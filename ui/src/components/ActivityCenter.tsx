/**
 * Header activity center.
 *
 * One quiet place for "something is happening" — the match library warming, an
 * update downloading/installing, an on-demand fixtures check. It composes three
 * existing sources (the warmup store, the updater controller, the ad-hoc activity
 * registry) into one popover, cloning the ReadingComfort interaction pattern
 * (click-away + Escape). It renders NOTHING when nothing is running and the panel
 * is closed, so it never adds header noise at rest.
 */
import { useEffect, useId, useRef, useState } from "react";
import { useWarmupStatus } from "../lib/warmup";
import { useActivities } from "../lib/activity";
import { useUpdater } from "../lib/updater-context";
import { formatBytes } from "../lib/updater";
import { PulseIcon } from "./icons";
import { useFollows } from "../lib/follow-context";

interface Row {
  id: string;
  label: string;
  /** Determinate percent, or null for an indeterminate bar, or undefined for no bar. */
  pct?: number | null;
  detail?: string;
  action?: { label: string; onClick: () => void };
}

function IndeterminateOrPct({ pct }: { pct: number | null }) {
  return (
    <div className="update-progress activity__bar">
      <div
        className="update-progress__track"
        role="progressbar"
        aria-label="Activity progress"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct ?? undefined}
      >
        <div
          className={`update-progress__fill${pct === null ? " update-progress__fill--indeterminate" : ""}`}
          style={pct === null ? undefined : { width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export function ActivityCenter() {
  const warmup = useWarmupStatus();
  const activities = useActivities();
  const u = useUpdater();
  const follows = useFollows();
  const [open, setOpen] = useState(false);
  const wrap = useRef<HTMLDivElement>(null);
  const panelId = useId();

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (wrap.current && !wrap.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const rows: Row[] = [];

  if (warmup.phase === "warming") {
    rows.push({
      id: "warmup",
      label: "Waking the match library",
      pct: null,
      detail: warmup.rows ? `Seating ${warmup.rows.toLocaleString()} matches` : undefined,
    });
  }

  const p = u.phase;
  if (p.kind === "checking") {
    rows.push({ id: "update", label: "Checking for updates", pct: null });
  } else if (p.kind === "downloading") {
    const pct = p.total ? Math.min(100, Math.round((p.downloaded / p.total) * 100)) : null;
    rows.push({
      id: "update",
      label: `Downloading Golavo ${p.info.version}`,
      pct,
      detail: p.total ? `${formatBytes(p.downloaded)} of ${formatBytes(p.total)}` : formatBytes(p.downloaded),
    });
  } else if (p.kind === "installing") {
    rows.push({ id: "update", label: `Installing Golavo ${p.info.version}`, pct: null });
  } else if (p.kind === "ready") {
    rows.push({
      id: "update",
      label: `Update ready — Golavo ${p.info.version}`,
      detail: "Downloaded and verified.",
      action: { label: "Open Software Update", onClick: u.openSheet },
    });
  }

  for (const a of activities) {
    rows.push({ id: `act:${a.id}`, label: a.label, pct: null });
  }

  if (follows.list.unread_event_count > 0) {
    rows.push({
      id: "follow-events",
      label: `${follows.list.unread_event_count} followed match ${follows.list.unread_event_count === 1 ? "update" : "updates"}`,
      detail: "Stored locally with source provenance.",
      action: {
        label: "Review followed matches",
        onClick: () => {
          window.location.hash = "#/games";
          setOpen(false);
        },
      },
    });
  }

  const active = rows.length > 0;
  // At rest with the panel closed, add nothing to the header.
  if (!active && !open) return null;

  return (
    <div className="activity rc" ref={wrap}>
      <button
        type="button"
        className="icon-btn activity__trigger"
        aria-haspopup="true"
        aria-expanded={open}
        aria-controls={open ? panelId : undefined}
        aria-label={active ? `Current activity and updates — ${rows.length}` : "Current activity"}
        title="Current activity"
        onClick={() => setOpen((o) => !o)}
      >
        <PulseIcon />
        {active && <span className="activity__dot" aria-hidden />}
      </button>
      {open && (
        <div className="rc__panel activity__panel" id={panelId} role="group" aria-label="Current activity and updates">
          {rows.length === 0 ? (
            <p className="activity__empty dim">All quiet — nothing running.</p>
          ) : (
            rows.map((r) => (
              <div className="activity__row" key={r.id}>
                <div className="activity__label">{r.label}</div>
                {r.pct !== undefined && <IndeterminateOrPct pct={r.pct} />}
                {r.detail && <div className="activity__detail dim small">{r.detail}</div>}
                {r.action && (
                  <button type="button" className="btn activity__action" onClick={r.action.onClick}>
                    {r.action.label}
                  </button>
                )}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
