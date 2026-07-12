import { useEffect, useState } from "react";
import { IS_DESKTOP_SHELL } from "../lib/updater";

/** Genuinely true, genuinely obscure football facts to pass the ~30-40s the
 *  onefile engine takes to unpack on a cold launch. Kept factual on purpose —
 *  this is a forecast-audit app; even the loading screen shouldn't make things
 *  up. Each is one sentence so it fits without reflow. */
const FACTS: readonly string[] = [
  "“Soccer” is British slang — short for as-SOC-iation football, coined to tell it apart from rugby.",
  "Brazil is the only country to appear at every men's World Cup since the tournament began in 1930.",
  "The most lopsided professional match ever finished 149–0 — every goal an own goal, scored in protest, in Madagascar in 2002.",
  "Denmark won Euro 1992 without qualifying: they were called up at the last minute to replace Yugoslavia.",
  "Vatican City fields its own national team, drawn mostly from Swiss Guards and clergy.",
  "Only three people have won the World Cup as both player and manager: Zagallo, Beckenbauer, and Deschamps.",
  "The fastest World Cup goal came after 11 seconds — Hakan Şükür for Turkey in 2002.",
  "The goal net was patented in 1891 by a Liverpool engineer, John Brodie.",
  "A regulation match ball must measure 68–70 cm around — the same spec used at the World Cup.",
  "Nearly 200,000 fans packed the Maracanã for the 1950 World Cup final, still a record crowd.",
  "The oldest club in the world, Sheffield FC, was founded in 1857 — before the modern rules of the game even existed.",
  "A single Law of the Game (Law 11, offside) has been rewritten more than any other in football's history.",
];

/** Time-based progress: real extraction gives us no signal, so we ease toward
 *  ~94% and let the app itself replace the splash the moment the backend is
 *  ready. Fast early, slows near the end — never stalls on a fixed number, never
 *  claims to be finished before it is. */
function estimateProgress(elapsedSeconds: number): number {
  return 94 * (1 - Math.exp(-elapsedSeconds / 12));
}

function statusFor(pct: number, desktop: boolean): string {
  if (!desktop) return "Connecting to the local server…";
  if (pct < 38) return "Unpacking the forecasting engine…";
  if (pct < 72) return "Warming up the models…";
  return "Almost ready…";
}

export function StartupSplash({
  theme,
  stalled = false,
  onRetry,
}: {
  theme: "dark" | "light";
  stalled?: boolean;
  onRetry?: () => void;
}) {
  const [pct, setPct] = useState(0);
  const [fact, setFact] = useState(() => Math.floor(Math.random() * FACTS.length));

  useEffect(() => {
    const start = performance.now();
    const id = window.setInterval(() => {
      setPct(estimateProgress((performance.now() - start) / 1000));
    }, 120);
    return () => window.clearInterval(id);
  }, []);

  useEffect(() => {
    const id = window.setInterval(() => setFact((f) => (f + 1) % FACTS.length), 5200);
    return () => window.clearInterval(id);
  }, []);

  const lockup =
    theme === "dark" ? "/brand/golavo-lockup-dark.svg" : "/brand/golavo-lockup-light.svg";
  const rounded = Math.round(pct);
  const status = statusFor(pct, IS_DESKTOP_SHELL);

  if (stalled) {
    return (
      <div className="splash" aria-label="Golavo is taking longer than expected">
        <div className="splash__inner">
          <img className="splash__logo" src={lockup} alt="Golavo" height={40} width={162} />
          <p className="splash__title">The local engine is taking a while</p>
          <p className="splash__status splash__status--stalled" role="status">
            It usually starts within a minute. If it doesn’t, quitting and
            reopening Golavo — or reinstalling — clears a stuck launch.
          </p>
          {onRetry && (
            <button type="button" className="btn btn--primary" onClick={onRetry}>
              Try again
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="splash" aria-label="Golavo is starting up">
      {/* One calm, stable announcement for assistive tech — not the ticking %. */}
      <p className="visually-hidden" role="status">
        Starting Golavo. First launch can take up to a minute while the engine unpacks.
      </p>

      <div className="splash__inner">
        <img className="splash__logo" src={lockup} alt="Golavo" height={40} width={162} />
        <p className="splash__title">Starting the local engine…</p>

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

        <div className="splash__fact" key={fact} aria-hidden="true">
          <span className="splash__fact-label">
            <span className="splash__ball" /> Did you know
          </span>
          <p className="splash__fact-text">{FACTS[fact]}</p>
        </div>
      </div>
    </div>
  );
}
