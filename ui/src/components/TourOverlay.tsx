import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { TourController } from "../lib/tour";

interface Rect { top: number; left: number; width: number; height: number; }

function measure(el: HTMLElement | null): Rect | null {
  if (!el) return null;
  const r = el.getBoundingClientRect();
  if (r.width === 0 && r.height === 0) return null;
  return { top: r.top, left: r.left, width: r.width, height: r.height };
}

function reducedMotion(): boolean {
  return typeof window !== "undefined"
    && typeof window.matchMedia === "function"
    && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** A coach-mark overlay: a dim, click-blocking backdrop with a bright cutout over
 *  the current target and a positioned card. The background is inert while it
 *  shows (advancement is via the card only), so clicking the highlighted element
 *  can't strand the tour. Nothing renders when `ctrl.step` is null. */
export function TourOverlay({ ctrl }: { ctrl: TourController }) {
  const { step, index, total, targetEl, next, back, skip } = ctrl;
  const [rect, setRect] = useState<Rect | null>(null);
  const cardRef = useRef<HTMLDivElement>(null);

  // Bring the target into view when the step changes (instant under reduced
  // motion, and to avoid fighting the global smooth-scroll override).
  useEffect(() => {
    if (!targetEl) return;
    targetEl.scrollIntoView({
      behavior: reducedMotion() ? "auto" : "smooth",
      block: "center",
      inline: "nearest",
    });
  }, [targetEl]);

  // Keep the cutout aligned as the page scrolls, resizes, or reflows (cockpit
  // panels mount late). Measure synchronously first (so the overlay paints
  // immediately), then poll on an interval — a timer keeps working when the
  // window is occluded/backgrounded, where requestAnimationFrame is paused.
  useLayoutEffect(() => {
    if (!step || !targetEl) {
      setRect(null);
      return;
    }
    let last = "";
    const sync = () => {
      const next = measure(targetEl);
      const key = next ? `${next.top}|${next.left}|${next.width}|${next.height}` : "";
      if (key !== last) {
        last = key;
        setRect(next);
      }
    };
    sync();
    const id = window.setInterval(sync, 150);
    return () => window.clearInterval(id);
  }, [step, targetEl]);

  // Move focus into the card on each step, and trap Tab within it. Keyboard:
  // Esc skips, ArrowRight/Enter advance, ArrowLeft goes back.
  useEffect(() => {
    if (!step) return;
    cardRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { e.preventDefault(); skip(); }
      else if (e.key === "ArrowRight") { e.preventDefault(); next(); }
      else if (e.key === "ArrowLeft") { e.preventDefault(); back(); }
      else if (e.key === "Tab") {
        const focusables = cardRef.current?.querySelectorAll<HTMLElement>(
          "button:not([disabled])",
        );
        if (!focusables || focusables.length === 0) return;
        const first = focusables[0];
        const eltLast = focusables[focusables.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); eltLast.focus(); }
        else if (!e.shiftKey && document.activeElement === eltLast) { e.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener("keydown", onKey, true);
    return () => document.removeEventListener("keydown", onKey, true);
  }, [step, next, back, skip]);

  if (!step || !rect) return null;

  const pad = 6;
  const holeTop = Math.max(0, rect.top - pad);
  const holeLeft = Math.max(0, rect.left - pad);
  const holeW = rect.width + pad * 2;
  const holeH = rect.height + pad * 2;

  // Place the card below the target when there's room, otherwise above; clamp
  // horizontally so it never leaves the viewport on a small window.
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const cardW = Math.min(360, vw - 32);
  const below = holeTop + holeH + 12;
  const placeBelow = below + 180 < vh;
  const cardTop = placeBelow ? below : Math.max(16, holeTop - 12 - 180);
  let cardLeft = rect.left + rect.width / 2 - cardW / 2;
  cardLeft = Math.max(16, Math.min(cardLeft, vw - cardW - 16));

  const isLast = index >= total - 1;

  return createPortal(
    <div className="tour" role="dialog" aria-modal="true" aria-labelledby="tour-title">
      <div className="tour__backdrop" onClick={skip} aria-hidden="true" />
      <div
        className="tour__hole"
        aria-hidden="true"
        style={{ top: holeTop, left: holeLeft, width: holeW, height: holeH }}
      />
      <div
        className="tour__card"
        ref={cardRef}
        tabIndex={-1}
        style={{ top: cardTop, left: cardLeft, width: cardW }}
      >
        <p className="tour__step" aria-hidden="true">{index + 1} of {total}</p>
        <h2 className="tour__title" id="tour-title">{step.title}</h2>
        {/* Announce the whole step once per change. */}
        <p className="tour__body" role="status">{step.body}</p>
        <div className="tour__dots" aria-hidden="true">
          {Array.from({ length: total }, (_, i) => (
            <span key={i} className={i === index ? "tour__dot tour__dot--on" : "tour__dot"} />
          ))}
        </div>
        <div className="tour__actions">
          <button type="button" className="tour__skip" onClick={skip}>Skip tour</button>
          <div className="tour__nav">
            {index > 0 && (
              <button type="button" className="btn btn--ghost" onClick={back}>Back</button>
            )}
            <button type="button" className="btn btn--primary" onClick={isLast ? skip : next}>
              {isLast ? "Done" : "Next"}
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}
