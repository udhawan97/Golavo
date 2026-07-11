import { useEffect, useState } from "react";
import { IS_DESKTOP_SHELL } from "../lib/updater";

/** Full-window "starting up" screen shown while the local engine extracts and
 *  boots. Honest about the wait so a slow first launch never reads as broken:
 *  after a few seconds it adds a line. The "unpacks its engine" copy is
 *  desktop-only — in source-web mode we're just waiting on a hand-started
 *  server, so the message stays generic (and mentions it may be unreachable). */
export function StartupSplash({ theme }: { theme: "dark" | "light" }) {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const t = window.setTimeout(() => setSlow(true), 4000);
    return () => window.clearTimeout(t);
  }, []);

  const lockup =
    theme === "dark" ? "/brand/golavo-lockup-dark.svg" : "/brand/golavo-lockup-light.svg";

  const hint = !slow
    ? "Warming up your private forecasting workbench."
    : IS_DESKTOP_SHELL
      ? "First launch takes ~30–40 seconds while Golavo unpacks its engine. Later launches are quicker."
      : "Still connecting to the local server — make sure it’s running.";

  return (
    <div className="splash" role="status" aria-live="polite">
      <div className="splash__inner">
        <img className="splash__logo" src={lockup} alt="Golavo" height={44} width={178} />
        <div className="splash__spinner" aria-hidden />
        <p className="splash__title">Starting the local engine…</p>
        <p className="splash__hint">{hint}</p>
      </div>
    </div>
  );
}
