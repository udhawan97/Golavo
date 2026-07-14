import { useEffect, useMemo, useRef, useState } from "react";
import { IS_DESKTOP_SHELL } from "../lib/updater";
import { stageProgress, startupCopyFor } from "../lib/startup";
import type { SplashStage } from "../lib/startup";
import { buildLaunchDeck } from "../lib/waitContent";

function prefersReducedMotion(): boolean {
  return typeof window !== "undefined"
    && typeof window.matchMedia === "function"
    && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** The seigaiha ground from the README icon, expanded into a quiet horizon.
 * It is decorative: startup state remains entirely in the live text above. */
function SplashWaves() {
  return (
    <div className="splash__waves" aria-hidden="true">
      <svg width="100%" height="100%" focusable="false">
        <defs>
          <pattern
            id="splash-seigaiha"
            width="128"
            height="180"
            patternUnits="userSpaceOnUse"
          >
            <g fill="var(--ink)" stroke="currentColor" strokeWidth="2.4">
              <circle cx="64" cy="126" r="58" />
              <circle cx="64" cy="126" r="44" fill="none" />
              <circle cx="64" cy="126" r="30" fill="none" />
              <circle cx="64" cy="126" r="16" fill="none" />

              <circle cx="0" cy="174" r="58" />
              <circle cx="0" cy="174" r="44" fill="none" />
              <circle cx="0" cy="174" r="30" fill="none" />
              <circle cx="0" cy="174" r="16" fill="none" />
              <circle cx="128" cy="174" r="58" />
              <circle cx="128" cy="174" r="44" fill="none" />
              <circle cx="128" cy="174" r="30" fill="none" />
              <circle cx="128" cy="174" r="16" fill="none" />
            </g>
          </pattern>
        </defs>
        <rect
          className="splash__waves-drift"
          width="120%"
          height="100%"
          fill="url(#splash-seigaiha)"
        />
      </svg>
    </div>
  );
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
  const deck = useMemo(() => buildLaunchDeck(Math.floor(Math.random() * 12)), []);
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
    if (prefersReducedMotion()) return;
    const id = window.setInterval(() => setCard((c) => (c + 1) % deck.length), 9000);
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
  const { detail, announce } = startupCopyFor(stage, IS_DESKTOP_SHELL, rows);
  const current = deck[card];
  const elapsedSec = Math.floor(elapsedMs / 1000);
  const activeStage = stage === "index" ? 1 : 0;
  const setupStages = ["Engine", "Match data", "Ready"];

  if (failed) {
    return (
      <div className="splash" aria-label="Golavo could not start the engine">
        <div className="splash__inner">
          <div className="splash__brand">
            <span className="splash__eyebrow">Local-first match intelligence</span>
            <img className="splash__logo" src={lockup} alt="Golavo" height={48} width={194} />
          </div>
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
        <SplashWaves />
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
        <div className="splash__brand">
          <span className="splash__eyebrow">Local-first match intelligence</span>
          <img className="splash__logo" src={lockup} alt="Golavo" height={48} width={194} />
        </div>

        <div className="splash__lead">
          <p className="splash__title">Setting the pitch</p>
          <p className="splash__detail splash__stage-swap" key={detail}>{detail}</p>
        </div>

        <div className="splash__progress">
          <div className="splash__progress-meta">
            <span>{stage === "extracting" ? "One-time setup" : "Match library"}</span>
            <span className="splash__pct">{rounded}%</span>
          </div>
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
          <ol className="splash__stages" aria-label="Startup stages">
            {setupStages.map((label, index) => {
              const state = index < activeStage ? "complete" : index === activeStage ? "current" : "pending";
              return (
                <li
                  className={`splash__stage splash__stage--${state}`}
                  key={label}
                  aria-current={state === "current" ? "step" : undefined}
                >
                  <span className="splash__stage-marker" aria-hidden="true" />
                  <span>{label}</span>
                </li>
              );
            })}
          </ol>
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
      <SplashWaves />
    </div>
  );
}
