import type { ReactNode } from "react";
import { SCHEMA_VERSION } from "../lib/contract";
import { DATA_SOURCE, sourceDescription } from "../lib/api";
import type { ForecastSource } from "../lib/api";
import type { ReadingPrefs } from "../lib/hooks";
import { GearIcon, SearchIcon } from "./icons";
import { ReadingComfort } from "./ReadingComfort";
import { UpdatePill } from "./updates";
import { DOCS_URL } from "../lib/links";

function isActive(path: string, section: "matchday" | "matches" | "ledger" | "eval"): boolean {
  if (section === "eval") return path.startsWith("/eval");
  if (section === "ledger") return path.startsWith("/ledger");
  // "matches" owns /matches and /match/{id}; keep it distinct from Matchday so
  // opening the directory never also lights up the Matchday tab.
  if (section === "matches") return path === "/matches" || path.startsWith("/match/");
  return path === "/" || path.startsWith("/forecast");
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
            <a href="#/" aria-current={isActive(path, "matchday") ? "page" : undefined}>Matchday</a>
            <a href="#/matches" aria-current={isActive(path, "matches") ? "page" : undefined}>Matches</a>
            <a href="#/ledger" aria-current={isActive(path, "ledger") ? "page" : undefined}>Ledger</a>
            <a href="#/eval" aria-current={isActive(path, "eval") ? "page" : undefined}>Evaluation</a>
          </nav>
          <div className="site-header__tools">
            <UpdatePill />
            <a
              className="icon-btn"
              href="#/matches"
              aria-label="Search matches"
              title="Search matches"
              aria-current={isActive(path, "matches") ? "page" : undefined}
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
            You’re exploring <strong>sample forecasts</strong> so you can see how Golavo works.
            Forecasts you seal before kickoff will replace these and appear in your Ledger — the
            samples are synthetic and never counted toward your forward record.
            <span className="sample-banner__cta">
              {DATA_SOURCE === "mock" ? (
                <>
                  <a href={DOCS_URL} target="_blank" rel="noreferrer">How sealing works ›</a>
                  <a href="#/matches">Search matches ›</a>
                </>
              ) : (
                <>
                  <a href="#/matches">Search matches ›</a>
                  <a href={DOCS_URL} target="_blank" rel="noreferrer">How sealing works ›</a>
                </>
              )}
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
            Golavo · Forecast Audit Workbench —{" "}
            <span className="dim">read-only. Forecasts are sealed before kickoff, scored after full time.</span>
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
