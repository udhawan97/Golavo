import { useEffect, useState } from "react";
import { handleExternalLinkClick } from "../lib/external-links";
import { configureSportmonks, fetchSportmonksStatus } from "../lib/sportmonks";
import { IS_DESKTOP_SHELL } from "../lib/updater";
import { requestSportmonksSettingsFocus } from "./SportmonksSettings";

export const SPORTMONKS_WELCOME_DECISION_KEY = "golavo-sportmonks-welcome-v1";

function storedDecision(): "setup" | "local" | null {
  try {
    const value = localStorage.getItem(SPORTMONKS_WELCOME_DECISION_KEY);
    return value === "setup" || value === "local" ? value : null;
  } catch {
    return null;
  }
}

function rememberDecision(value: "setup" | "local"): void {
  try { localStorage.setItem(SPORTMONKS_WELCOME_DECISION_KEY, value); } catch { /* non-persistent shell */ }
}

export function SportmonksWelcomeCard({
  eligible,
  onVisibilityChange,
}: {
  eligible: boolean;
  onVisibilityChange: (visible: boolean) => void;
}) {
  const [decision, setDecision] = useState(storedDecision);
  const [checked, setChecked] = useState(!IS_DESKTOP_SHELL || decision !== null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!IS_DESKTOP_SHELL || decision !== null) return;
    let live = true;
    void fetchSportmonksStatus().then(
      (status) => {
        if (!live) return;
        if (status.terms_acceptance_version === status.provider.terms_acceptance_version) {
          rememberDecision("setup");
          setDecision("setup");
        }
        setChecked(true);
      },
      () => { if (live) setChecked(true); },
    );
    return () => { live = false; };
  }, [decision]);

  const visible = IS_DESKTOP_SHELL && checked && decision === null && eligible;
  useEffect(() => {
    onVisibilityChange(visible);
    return () => onVisibilityChange(false);
  }, [onVisibilityChange, visible]);

  if (!visible) return null;
  return (
    <div className="consent-card consent-card--wide card" role="region" aria-label="Optional outside football signals">
      <p className="consent-card__title">Add outside football signals?</p>
      <p className="dim">
        Golavo can show Sportmonks match probabilities and bookmaker prices in a separate panel.
        They never change Golavo’s own forecast. Nothing is requested until you click on a match.
      </p>
      <p className="dim consent-card__hint">
        Requires your own paid Sportmonks account and token. A request sends the fixture date and
        team names to Sportmonks; responses are not kept on disk. Review the{" "}
        <a href="https://www.sportmonks.com/terms-of-service/" target="_blank" rel="noreferrer" onClick={handleExternalLinkClick}>terms</a>
        {" and "}<a href="https://www.sportmonks.com/privacy-policy/" target="_blank" rel="noreferrer" onClick={handleExternalLinkClick}>privacy policy</a>.
      </p>
      <div className="update-sheet__actions">
        <button
          type="button"
          className="btn btn--primary"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            setError(null);
            try {
              await configureSportmonks({
                enabled: true,
                capabilities: ["external_prediction", "external_odds"],
                accept_terms: true,
              });
              rememberDecision("setup");
              setDecision("setup");
              requestSportmonksSettingsFocus();
              window.location.hash = "#/settings";
            } catch (reason) {
              setError(reason instanceof Error ? reason.message : String(reason));
            } finally {
              setBusy(false);
            }
          }}
        >
          Accept &amp; set up
        </button>
        <button
          type="button"
          className="btn btn--ghost"
          disabled={busy}
          onClick={() => {
            rememberDecision("local");
            setDecision("local");
          }}
        >
          Keep current setup
        </button>
      </div>
      {error && <p className="dim consent-card__hint" role="alert">Could not save this choice: {error}</p>}
      <p className="dim consent-card__hint">You can change this anytime in Settings.</p>
    </div>
  );
}
