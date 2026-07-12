import type { ReactNode } from "react";
import { SCHEMA_VERSION } from "../lib/contract";
import { DATA_SOURCE, sourceDescription } from "../lib/api";
import type { ForecastSource } from "../lib/api";
import { AI_PROVIDERS, lastAiProvider, useAiProvider } from "../lib/ai";
import type { ReadingPrefs } from "../lib/hooks";
import { GearIcon, SearchIcon } from "./icons";
import { ReadingComfort } from "./ReadingComfort";
import { UpdatePill } from "./updates";
import { DOCS_URL } from "../lib/links";

function isActive(path: string, section: "games" | "leagues" | "lab"): boolean {
  if (section === "leagues") return path === "/leagues" || path.startsWith("/league/");
  // Model Lab owns the relocated audit surface, sealed-forecast detail, and the
  // legacy /ledger and /eval addresses that redirect into it.
  if (section === "lab")
    return (
      path.startsWith("/lab") ||
      path.startsWith("/forecast") ||
      path.startsWith("/ledger") ||
      path.startsWith("/eval")
    );
  // Games owns the home, the match directory, and any match cockpit.
  return path === "/" || path === "/matches" || path.startsWith("/match/");
}

/** One-click AI mode from anywhere — but only once a provider has been chosen.
 *
 * Shown only when AI is currently on, or was configured before (a remembered
 * last provider): a first-time user must still make the explicit opt-in choice
 * in Settings or on an AI panel, so this toggle can never be the thing that
 * turns AI on for the first time. Toggling changes the SAME persisted setting
 * every AI panel reads — never a number, never a forecast. */
function AiQuickToggle() {
  const [provider, setProvider] = useAiProvider();
  const last = lastAiProvider();
  const on = provider !== "off";
  if (!on && !last) return null; // never configured — no quick path into AI
  const label = on
    ? `AI on (${AI_PROVIDERS.find((p) => p.value === provider)?.label ?? provider}) — click to turn off`
    : `AI off — click to turn back on (${AI_PROVIDERS.find((p) => p.value === last)?.label ?? last})`;
  return (
    <button
      type="button"
      className={`icon-btn ai-toggle${on ? " ai-toggle--on" : ""}`}
      aria-pressed={on}
      aria-label={label}
      title={label}
      onClick={() => setProvider(on ? "off" : (last as typeof provider))}
    >
      <span className="ai-toggle__text" aria-hidden>AI</span>
      <span className={`ai-toggle__dot${on ? " on" : ""}`} aria-hidden />
    </button>
  );
}

export function Layout({
  path, prefs, onChangePrefs, forecastSource, children,
}: {
  path: string;
  prefs: ReadingPrefs;
  onChangePrefs: (patch: Partial<ReadingPrefs>) => void;
  forecastSource?: ForecastSource | null;
  children: ReactNode;
}) {
  // Light uses the light lockup; dark and warm are both dark surfaces.
  const lockup = prefs.theme === "light" ? "/brand/golavo-lockup-light.svg" : "/brand/golavo-lockup-dark.svg";
  // "sample" = fresh install serving synthetic demos; "mock" = web bundle. Both
  // are labelled honestly as sample data, never as live forecasts.
  const isSample = forecastSource === "sample" || DATA_SOURCE === "mock";
  // Until the source is resolved (meta fetch pending in desktop mode), stay
  // neutral rather than asserting "Live" — otherwise synthetic samples flash a
  // "Live" badge for a frame before correcting, the exact thing to avoid.
  const sourceKnown = forecastSource !== null || DATA_SOURCE === "mock";
  return (
    <>
      {/* Intercept the click so the fragment does not drive the hash router. */}
      <a
        className="skip-link"
        href="#main"
        onClick={(e) => {
          e.preventDefault();
          const m = document.getElementById("main");
          if (m) { m.focus(); m.scrollIntoView(); }
        }}
      >
        Skip to content
      </a>
      <header className="site-header">
        <div className="container site-header__inner">
          <a className="brand-link" href="#/" aria-label="Golavo — home">
            <img src={lockup} alt="" height={30} width={122} />
            <span className="visually-hidden">Golavo</span>
          </a>
          <nav className="nav" aria-label="Primary">
            <a href="#/" aria-current={isActive(path, "games") ? "page" : undefined}>Games</a>
            <a href="#/leagues" aria-current={isActive(path, "leagues") ? "page" : undefined}>Leagues</a>
            <a href="#/lab" aria-current={isActive(path, "lab") ? "page" : undefined}>Model Lab</a>
          </nav>
          <div className="site-header__tools">
            <UpdatePill />
            <AiQuickToggle />
            <a
              className="icon-btn"
              href="#/matches"
              aria-label="Search matches"
              title="Search matches"
              aria-current={path === "/matches" ? "page" : undefined}
            >
              <SearchIcon />
            </a>
            <ReadingComfort prefs={prefs} onChange={onChangePrefs} />
            <a
              className="icon-btn"
              href="#/settings"
              aria-label="Settings — about & updates"
              title="Settings"
              aria-current={path.startsWith("/settings") ? "page" : undefined}
            >
              <GearIcon />
            </a>
          </div>
        </div>
      </header>

      {isSample && (
        <div className="sample-banner" role="note">
          <div className="container">
            {DATA_SOURCE === "mock" ? (
              <>
                This is the <strong>web preview</strong>. Browsing and the facts work here, but the
                model council needs the local Golavo app connected to the engine — sample forecasts
                are synthetic and never counted toward any record.
              </>
            ) : (
              <>
                Your ledger is empty, so <strong>sample forecasts</strong> are shown under Model Lab
                to illustrate sealing. Games, search, and the model council all use your real local
                data — the samples are synthetic and never counted toward your record.
              </>
            )}
            <span className="sample-banner__cta">
              <a href="#/matches">Search matches ›</a>
              <a href={DOCS_URL} target="_blank" rel="noreferrer">How it works ›</a>
            </span>
          </div>
        </div>
      )}

      <main id="main" className="page" tabIndex={-1}>
        <div className="container">{children}</div>
      </main>

      <footer className="site-footer">
        <div className="container">
          <span>
            Golavo · Local Football Intelligence —{" "}
            <span className="dim">read-only, offline, no account. Predictions you seal before kickoff are scored after full time.</span>
            {" · "}
            <a href="#/settings">Settings</a>
          </span>
          <span className="dim">
            <span
              className={`chip chip--${isSample ? "voided" : sourceKnown ? "scored" : "neutral"}`}
              style={{ marginRight: ".5rem" }}
            >
              {isSample ? "Sample data" : sourceKnown ? "Live" : "Connecting…"}
            </span>
            {sourceKnown
              ? sourceDescription(forecastSource ?? undefined)
              : "Connecting to the local engine…"}{" "}
            · contract v{SCHEMA_VERSION}
          </span>
        </div>
      </footer>
    </>
  );
}
