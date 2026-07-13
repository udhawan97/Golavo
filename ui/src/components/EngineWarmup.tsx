/**
 * Home warming surfaces, shared with the splash's rotation.
 *
 * When the home mounts while the match index is still loading, we show a calm
 * WarmupHero (a smaller continuation of the splash's messaging) instead of bare
 * skeletons — and we DON'T fire the matches query yet, which would otherwise
 * block ~25s inside pandas' import lock. The warmup store flips to "ready" the
 * moment the index is up, at which point the caller mounts the real rails.
 */
import { useEffect, useMemo, useState } from "react";
import { buildWaitDeck } from "../lib/waitContent";

function prefersReducedMotion(): boolean {
  return typeof window !== "undefined"
    && typeof window.matchMedia === "function"
    && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** A card index that advances on an interval. Slower under reduced motion. */
export function useRotatingIndex(len: number, baseMs = 7000): number {
  const [i, setI] = useState(0);
  useEffect(() => {
    if (len <= 1) return;
    const period = prefersReducedMotion() ? baseMs + 3000 : baseMs;
    const id = window.setInterval(() => setI((n) => (n + 1) % len), period);
    return () => window.clearInterval(id);
  }, [len, baseMs]);
  return len > 0 ? i % len : 0;
}

/** One rotating wait card (why-it-takes-a-bit / hidden gem / football fact). */
export function RotatingFact({ compact = false }: { compact?: boolean }) {
  const deck = useMemo(() => buildWaitDeck(Math.floor(Math.random() * 12)), []);
  const idx = useRotatingIndex(deck.length, 7000);
  const card = deck[idx];
  if (!card) return null;
  return (
    <div className={`splash__fact${compact ? " splash__fact--compact" : ""}`} key={idx} aria-hidden="true">
      <span className="splash__fact-label">
        <span className="splash__ball" /> {card.label}
      </span>
      <p className="splash__fact-text">{card.text}</p>
    </div>
  );
}

/** The home's warming card: honest status + an indeterminate bar + one rotating
 *  fact. Auto-replaced by real content when the store reports ready. */
export function WarmupHero({ rows }: { rows: number | null }) {
  const seated = rows ? rows.toLocaleString() : "the";
  return (
    <section className="warmup-hero card" aria-label="Match library warming up">
      <h2 className="warmup-hero__title">Waking the match library…</h2>
      <p className="warmup-hero__status dim">
        {rows
          ? `Seating ${seated} matches — usually under half a minute. Games appear the moment it's ready.`
          : "Getting the match library ready — usually under half a minute. Games appear the moment it's ready."}
      </p>
      <div className="update-progress warmup-hero__bar">
        <div
          className="update-progress__track"
          role="progressbar"
          aria-label="Match library warm-up"
          aria-valuemin={0}
          aria-valuemax={100}
        >
          <div className="update-progress__fill update-progress__fill--indeterminate" />
        </div>
      </div>
      <RotatingFact compact />
      <span className="visually-hidden" role="status">
        The match library is still warming. Games will appear automatically when it's ready.
      </span>
    </section>
  );
}
