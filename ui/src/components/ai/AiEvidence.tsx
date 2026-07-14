/**
 * The evidence system for the AI read — footnote markers + one deduplicated
 * "Evidence & sources" disclosure, replacing the old per-claim citation-chip wall.
 *
 * A claim carries tiny superscript footnote buttons (¹ ²); the full source list
 * lives once, at the bottom, as a numbered legend. Verified numbers still render
 * inline as quiet monospace chips. Everything resolves through the backend
 * envelope — the UI never invents a source or a number.
 */
import { useEffect, useId, useRef, useState } from "react";
import type { EvidenceIndex } from "../../lib/aiEvidence";
import { sourceKindLine } from "../../lib/aiEvidence";
import type { NumberRef, SourceRef } from "../../lib/ai";
import {
  BookIcon,
  ChecklistIcon,
  ExternalLinkIcon,
  GlobeIcon,
  ShieldCheckIcon,
} from "../icons";

/** A verified engine number, shown inline: quiet, monospace, with its label in
 *  an accessible name. Only ever used for engine-verified numbers. */
export function NumberChip({ num }: { num: NumberRef }) {
  return (
    <span
      className="ai-num"
      title={num.label}
      aria-label={`${num.display} — ${num.label}, engine-verified`}
    >
      {num.display}
    </span>
  );
}

const KIND_ICON: Record<SourceRef["kind"], typeof BookIcon> = {
  engine: ShieldCheckIcon,
  snapshot: BookIcon,
  web: GlobeIcon,
};

/** A superscript footnote button after a claim. Opens a small popover naming the
 *  source and offering a jump to its legend row. Keyboard + click + touch reach
 *  the same content (no hover-only information). */
export function FootnoteRef({ n, source }: { n: number; source: SourceRef }) {
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
  const jump = () => {
    setOpen(false);
    const drawer = document.getElementById("ai-evidence") as HTMLDetailsElement | null;
    if (drawer) drawer.open = true;
    const el = document.getElementById(`ai-src-${n}`);
    if (el) requestAnimationFrame(() => el.focus());
  };
  return (
    <span className="ai-fnote-wrap" ref={wrap}>
      <button
        type="button"
        className="ai-fnote"
        aria-expanded={open}
        aria-controls={open ? panelId : undefined}
        aria-label={`Evidence ${n}: ${source.title}`}
        onClick={() => setOpen((o) => !o)}
      >
        {n}
      </button>
      {open && (
        <span className="ai-fnote__panel" id={panelId} role="note">
          <span className="ai-fnote__title">{source.title}</span>
          <span className="ai-fnote__kind">{sourceKindLine(source.kind)}</span>
          <span className="ai-fnote__actions">
            {source.url && (
              <a href={source.url} target="_blank" rel="noreferrer">
                open source <ExternalLinkIcon size={11} />
              </a>
            )}
            <button type="button" className="link-btn" onClick={jump}>
              see in evidence list
            </button>
          </span>
        </span>
      )}
    </span>
  );
}

/** The single "Evidence used" legend: one numbered row per distinct source,
 *  with a kind icon, an outbound link, and how many claims cited it. This is
 *  what collapses dozens of repeated chips into a short, scannable list. */
export function EvidenceLegend({ index }: { index: EvidenceIndex }) {
  if (index.ordered.length === 0) return null;
  return (
    <details id="ai-evidence" className="ai-evidence">
      <summary className="ai-evidence__summary">
        <span className="ai-evidence__summary-icon" aria-hidden><ChecklistIcon size={15} /></span>
        <span>
          <b>Evidence &amp; sources</b>
          <small>{index.ordered.length} verified source{index.ordered.length === 1 ? "" : "s"}</small>
        </span>
        <span className="ai-evidence__summary-action">View source ledger</span>
      </summary>
      <div className="ai-evidence__body-wrap">
        <p className="small dim ai-evidence__intro">
          Each source is listed once, with the number of claims it supports.
        </p>
        <ol className="ai-evidence__list">
          {index.ordered.map(({ index: n, source, citedBy }) => {
            const Icon = KIND_ICON[source.kind] ?? BookIcon;
            return (
              <li
                key={source.source_id}
                id={`ai-src-${n}`}
                tabIndex={-1}
                className={`ai-evidence__item ai-evidence__item--${source.kind}`}
              >
                <span className="ai-evidence__num num" aria-hidden>{n}</span>
                <span className="ai-evidence__icon" aria-hidden><Icon size={15} /></span>
                <span className="ai-evidence__body">
                  {source.url ? (
                    <a href={source.url} target="_blank" rel="noreferrer">
                      {source.title} <ExternalLinkIcon size={11} />
                    </a>
                  ) : (
                    <span className="ai-evidence__title">{source.title}</span>
                  )}
                  <span className="ai-evidence__kind">{sourceKindLine(source.kind)}</span>
                </span>
                <span className="ai-evidence__count dim num" aria-label={`cited by ${citedBy} claim${citedBy === 1 ? "" : "s"}`}>
                  ×{citedBy}
                </span>
              </li>
            );
          })}
        </ol>
      </div>
    </details>
  );
}
