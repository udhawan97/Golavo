import { useEffect, useMemo, useRef, useState } from "react";
import { IS_DESKTOP_SHELL } from "../lib/updater";
import { stageProgress } from "../lib/startup";
import type { SplashStage } from "../lib/startup";
import { buildWaitDeck } from "../lib/waitContent";

function prefersReducedMotion(): boolean {
  return typeof window !== "undefined"
    && typeof window.matchMedia === "function"
    && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** Stage title + status line. Everything here is TRUE for the stage it names:
 *  stage 1 is a real self-extract, stage 2 is a real index load. */
function copyFor(stage: SplashStage, desktop: boolean, rows: number | null): {
  title: string;
  status: string;
  announce: string;
} {
  if (!desktop) {
    return {
      title: "Connecting to the local server…",
      status: "Connecting to the local server…",
      announce: "Starting Golavo — connecting to the local server.",
    };
  }
  if (stage === "extracting") {
    return {
      title: "Unpacking the engine…",
      status: "First launch takes the longest — the whole engine self-extracts.",
      announce: "Starting Golavo — unpacking the engine. This can take up to a minute.",
    };
  }
  const seated = rows ? rows.toLocaleString() : "75,000+";
  return {
    title: "Waking the match library…",
    status: `Engine is up — seating ${seated} matches.`,
    announce: "Engine running — waking the match library. Almost ready.",
  };
}

export function StartupSplash({
  theme,
  stage = "extracting",
  rows = null,
  reassure = false,
  failed = false,
  elapsedMs = 0,
  onRetry,
  onSkip,
}: {
  theme: "dark" | "light";
  stage?: SplashStage;
  rows?: number | null;
  /** Past the patience threshold but still starting — show a calm note. */
  reassure?: boolean;
  /** The shell reported the engine failed after its own retry — offer a manual one. */
  failed?: boolean;
  elapsedMs?: number;
  onRetry?: () => void;
  onSkip?: () => void;
}) {
  const [pct, setPct] = useState(0);
  const stageStart = useRef<number>(performance.now());
  const deck = useMemo(() => buildWaitDeck(Math.floor(Math.random() * 12)), []);
  const [card, setCard] = useState(0);
  const retryRef = useRef<HTMLButtonElement>(null);

  // Reset the eased progress clock whenever the real stage changes, so stage 2
  // starts from its own floor (a visible step forward), not wherever stage 1 was.
  useEffect(() => {
    stageStart.current = performance.now();
  }, [stage]);

  useEffect(() => {
    if (failed) return; // progress clock is meaningless once we've stopped.
    const id = window.setInterval(() => {
      setPct(stageProgress(stage, (performance.now() - stageStart.current) / 1000));
    }, 120);
    return () => window.clearInterval(id);
  }, [stage, failed]);

  useEffect(() => {
    const period = prefersReducedMotion() ? 9000 : 6000;
    const id = window.setInterval(() => setCard((c) => (c + 1) % deck.length), period);
    return () => window.clearInterval(id);
  }, [deck.length]);

  // Move focus to the retry action the moment the failure tier appears, so a
  // keyboard/screen-reader user lands on the one thing to do.
  useEffect(() => {
    if (failed) retryRef.current?.focus();
  }, [failed]);

  const lockup =
    theme === "dark" ? "/brand/golavo-lockup-dark.svg" : "/brand/golavo-lockup-light.svg";
  const rounded = Math.round(pct);
  const { title, status, announce } = copyFor(stage, IS_DESKTOP_SHELL, rows);
  const current = deck[card];
  const elapsedSec = Math.floor(elapsedMs / 1000);

  if (failed) {
    return (
      <div className="splash" aria-label="Golavo could not start the engine">
        <div className="splash__inner">
          <img className="splash__logo" src={lockup} alt="Golavo" height={40} width={162} />
          <p className="splash__title">The local engine didn’t start</p>
          {/* One announcement, with focus moved to the button below. */}
          <p className="splash__status splash__status--stalled" role="alert">
            This is usually temporary. Try again, and if it keeps happening,
            quitting and reopening Golavo — or reinstalling — clears a stuck launch.
          </p>
          {onRetry && (
            <button
              type="button"
              className="btn btn--primary"
              onClick={onRetry}
              ref={retryRef}
            >
              Try again
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="splash" aria-label="Golavo is starting up">
      {/* One calm announcement per stage — not the ticking %. `key` re-announces
          only when the stage-specific text actually changes. */}
      <p className="visually-hidden" role="status" key={announce}>
        {announce}
      </p>

      <div className="splash__inner">
        <img className="splash__logo" src={lockup} alt="Golavo" height={40} width={162} />
        <p className="splash__title splash__stage-swap" key={title}>{title}</p>

        <div className="splash__progress">
          <div
            className="splash__bar"
            role="progressbar"
            aria-label="Startup progress"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={rounded}
          >
            <div className="splash__fill" style={{ width: `${Math.max(4, pct)}%` }} />
          </div>
          <div className="splash__status">
            <span>{status}</span>
            <span className="splash__pct">{rounded}%</span>
          </div>
        </div>

        {/* Reassurance: shown only past the patience threshold. The elapsed
            seconds tick silently (aria-hidden) so screen readers aren't spammed;
            the reassuring sentence is announced exactly once via its keyed node. */}
        {reassure && (
          <p className="splash__reassure">
            <span role="status">Still working — nothing is wrong; a first launch can take a couple of minutes.</span>{" "}
            <span className="splash__elapsed" aria-hidden="true">{elapsedSec}s</span>
          </p>
        )}

        {current && (
          <div className="splash__fact" key={card} aria-hidden="true">
            <span className="splash__fact-label">
              <span className="splash__ball" /> {current.label}
            </span>
            <p className="splash__fact-text">{current.text}</p>
          </div>
        )}

        {onSkip && (
          <button type="button" className="splash__skip" onClick={onSkip}>
            Browse while the library warms ›
          </button>
        )}
      </div>
    </div>
  );
}
