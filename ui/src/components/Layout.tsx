import type { ReactNode } from "react";
import { SCHEMA_VERSION } from "../lib/contract";
import { DATA_SOURCE, sourceDescription } from "../lib/api";
import { GearIcon, MoonIcon, SunIcon } from "./icons";
import { UpdatePill } from "./updates";

type Theme = "dark" | "light";

function isActive(path: string, section: "matchday" | "ledger" | "eval"): boolean {
  if (section === "eval") return path.startsWith("/eval");
  if (section === "ledger") return path.startsWith("/ledger");
  return path === "/" || path.startsWith("/forecast");
}

export function Layout({
  path, theme, onToggleTheme, children,
}: { path: string; theme: Theme; onToggleTheme: () => void; children: ReactNode }) {
  const lockup = theme === "dark" ? "/brand/golavo-lockup-dark.svg" : "/brand/golavo-lockup-light.svg";
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
            <a href="#/ledger" aria-current={isActive(path, "ledger") ? "page" : undefined}>Ledger</a>
            <a href="#/eval" aria-current={isActive(path, "eval") ? "page" : undefined}>Evaluation</a>
          </nav>
          <div className="site-header__tools">
            <UpdatePill />
            <button
              type="button"
              className="icon-btn"
              onClick={onToggleTheme}
              aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
              title={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
            >
              {theme === "dark" ? <SunIcon /> : <MoonIcon />}
            </button>
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

      <main id="main" className="page" tabIndex={-1}>
        <div className="container">{children}</div>
      </main>

      <footer className="site-footer">
        <div className="container">
          <span>
            Golavo · Forecast Audit Workbench —{" "}
            <span className="dim">read-only. Forecasts are sealed before kickoff, scored after full time.</span>
          </span>
          <span className="dim">
            <span className={`chip chip--${DATA_SOURCE === "mock" ? "voided" : "scored"}`} style={{ marginRight: ".5rem" }}>
              {DATA_SOURCE === "mock" ? "Sample data" : "Live"}
            </span>
            {sourceDescription()} · contract v{SCHEMA_VERSION}
          </span>
        </div>
      </footer>
    </>
  );
}
