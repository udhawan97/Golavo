import type { ReactNode } from "react";
import { SCHEMA_VERSION } from "../lib/contract";
import { DATA_SOURCE, sourceDescription } from "../lib/api";
import { MoonIcon, SunIcon } from "./icons";

type Theme = "dark" | "light";

function isActive(path: string, section: "matchday" | "eval"): boolean {
  if (section === "eval") return path.startsWith("/eval");
  return path === "/" || path.startsWith("/forecast");
}

export function Layout({
  path, theme, onToggleTheme, children,
}: { path: string; theme: Theme; onToggleTheme: () => void; children: ReactNode }) {
  const lockup = theme === "dark" ? "/brand/golavo-lockup-dark.svg" : "/brand/golavo-lockup-light.svg";
  return (
    <>
      <a className="skip-link" href="#main">Skip to content</a>
      <header className="site-header">
        <div className="container site-header__inner">
          <a className="brand-link" href="#/" aria-label="Golavo — home">
            <img src={lockup} alt="" height={30} width={122} />
            <span className="visually-hidden">Golavo</span>
          </a>
          <nav className="nav" aria-label="Primary">
            <a href="#/" aria-current={isActive(path, "matchday") ? "page" : undefined}>Matchday</a>
            <a href="#/eval" aria-current={isActive(path, "eval") ? "page" : undefined}>Evaluation</a>
          </nav>
          <button
            type="button"
            className="icon-btn"
            onClick={onToggleTheme}
            aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
            title={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
          >
            {theme === "dark" ? <SunIcon /> : <MoonIcon />}
          </button>
        </div>
      </header>

      <main id="main" className="page">
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
