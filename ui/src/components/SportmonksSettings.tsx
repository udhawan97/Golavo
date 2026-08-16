import { useEffect, useState } from "react";
import { handleExternalLinkClick } from "../lib/external-links";
import {
  configureSportmonks,
  deleteSportmonksCredential,
  fetchSportmonksStatus,
  saveSportmonksCredential,
} from "../lib/sportmonks";
import type { SportmonksCapability, SportmonksStatus } from "../lib/sportmonks";

const FOCUS_KEY = "golavo-sportmonks-focus-setup";

export function requestSportmonksSettingsFocus(): void {
  try { localStorage.setItem(FOCUS_KEY, "1"); } catch { /* non-persistent shell */ }
}

export function SportmonksSettings() {
  const [status, setStatus] = useState<SportmonksStatus | null>(null);
  const [accepted, setAccepted] = useState(false);
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    void fetchSportmonksStatus().then(
      (value) => { if (live) setStatus(value); },
      (reason: unknown) => { if (live) setError(reason instanceof Error ? reason.message : String(reason)); },
    );
    let focus = false;
    try {
      focus = localStorage.getItem(FOCUS_KEY) === "1";
      if (focus) localStorage.removeItem(FOCUS_KEY);
    } catch { /* non-persistent shell */ }
    if (focus) {
      const timer = window.setTimeout(
        () => document.getElementById("settings-sportmonks")?.scrollIntoView({ block: "start" }),
        80,
      );
      return () => { live = false; window.clearTimeout(timer); };
    }
    return () => { live = false; };
  }, []);

  const run = async (action: () => Promise<SportmonksStatus>) => {
    setBusy(true);
    setError(null);
    try {
      setStatus(await action());
      return true;
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
      return false;
    } finally {
      setBusy(false);
    }
  };

  if (!status && !error)
    return <p className="settings__hint">Checking Sportmonks connector support…</p>;
  if (!status)
    return <p className="settings__hint" role="alert">Sportmonks settings: {error}</p>;
  if (!status.connector_supported)
    return <p className="settings__hint">Sportmonks is unavailable in this build.</p>;

  const termsCurrent =
    status.terms_acceptance_version === status.provider.terms_acceptance_version;
  const toggleCapability = (capability: SportmonksCapability) => {
    const next = status.capabilities.includes(capability)
      ? status.capabilities.filter((item) => item !== capability)
      : [...status.capabilities, capability];
    if (next.length > 0) void run(() => configureSportmonks({ capabilities: next }));
  };
  const disconnect = async () => {
    if (!window.confirm(
      "Disable Sportmonks and remove its Keychain token? Golavo forecasts and local data are unaffected.",
    )) return;
    const disabled = await run(() => configureSportmonks({ enabled: false }));
    if (disabled && status.credential.source === "keychain") {
      await run(deleteSportmonksCredential);
    }
  };

  return (
    <div id="settings-sportmonks" className="settings__field stack" style={{ ["--gap" as string]: ".7rem", scrollMarginTop: "1rem" }}>
      <div className="settings__row">
        <div>
          <label>Sportmonks outside signals</label>
          <p className="settings__hint" style={{ margin: ".2rem 0 0" }}>
            Optional BYOK predictions and bookmaker prices from a paid third-party football API.
          </p>
        </div>
        <span className={`chip ${status.enabled ? "chip--success" : "chip--neutral"}`}>
          {status.enabled ? (status.credential.configured ? "ready" : "needs token") : "off"}
        </span>
      </div>

      <p className="settings__hint" style={{ margin: 0 }}>
        <b>Outside-signal boundary:</b> these values are labelled Sportmonks opinions. They never
        change a Golavo probability, model, verdict, seal, score, calibration, AI read, or export.
        Golavo requests them only when you click on a match and does not persist the response.
      </p>

      {!status.enabled ? (
        <>
          {!termsCurrent && (
            <label className="settings__hint" style={{ display: "flex", gap: ".55rem", alignItems: "flex-start" }}>
              <input
                type="checkbox"
                checked={accepted}
                onChange={(event) => setAccepted(event.target.checked)}
              />
              <span>
                I understand Sportmonks is a paid third-party service, requests send this fixture’s
                date and team names, its data may be incomplete, and its odds/predictions are not
                advice or Golavo forecasts. I have reviewed the linked terms and privacy policy.
              </span>
            </label>
          )}
          <div>
            <button
              type="button"
              className="btn btn--primary"
              disabled={busy || (!termsCurrent && !accepted)}
              onClick={() => void run(() => configureSportmonks({
                enabled: true,
                accept_terms: !termsCurrent && accepted,
              }))}
            >
              Enable outside signals
            </button>
          </div>
        </>
      ) : (
        <>
          <div className="settings__row" style={{ alignItems: "flex-start" }}>
            <span>Capabilities</span>
            <span style={{ display: "grid", gap: ".35rem" }}>
              <label className="small">
                <input
                  type="checkbox"
                  checked={status.capabilities.includes("external_prediction")}
                  disabled={busy || status.capabilities.length === 1 && status.capabilities[0] === "external_prediction"}
                  onChange={() => toggleCapability("external_prediction")}
                />{" "}Provider match probabilities
              </label>
              <label className="small">
                <input
                  type="checkbox"
                  checked={status.capabilities.includes("external_odds")}
                  disabled={busy || status.capabilities.length === 1 && status.capabilities[0] === "external_odds"}
                  onChange={() => toggleCapability("external_odds")}
                />{" "}Pre-match match-winner odds
              </label>
            </span>
          </div>

          <div className="settings__field">
            <div className="settings__row">
              <label htmlFor="sportmonks-token">API token</label>
              <span className="small dim">
                {status.credential.configured
                  ? `Configured via ${status.credential.source}`
                  : "Not configured"}
              </span>
            </div>
            {status.credential.writable ? (
              <div className="settings__row" style={{ justifyContent: "flex-start" }}>
                <input
                  id="sportmonks-token"
                  type="password"
                  autoComplete="off"
                  spellCheck={false}
                  value={token}
                  placeholder={status.credential.configured ? "Replace Keychain token" : "Paste Sportmonks token"}
                  onChange={(event) => setToken(event.target.value)}
                />
                <button
                  type="button"
                  className="btn btn--primary"
                  disabled={busy || token.length < 12}
                  onClick={async () => {
                    const saved = await run(() => saveSportmonksCredential(token));
                    if (saved) setToken("");
                  }}
                >
                  Save to Keychain
                </button>
              </div>
            ) : (
              <p className="settings__hint">
                Set <code>{status.credential.environment_variable}</code> before starting Golavo on
                this platform. The token is never written to project data or returned to the UI.
              </p>
            )}
          </div>

          <div className="settings__row" style={{ justifyContent: "flex-start", gap: ".6rem" }}>
            <button type="button" className="btn btn--ghost" disabled={busy} onClick={() => void run(() => configureSportmonks({ enabled: false }))}>
              Disable
            </button>
            <button type="button" className="btn btn--ghost" disabled={busy} onClick={() => void disconnect()}>
              Disconnect{status.credential.source === "keychain" ? " & remove token" : ""}
            </button>
          </div>
        </>
      )}

      {error && <p className="settings__hint" role="alert">Sportmonks: {error}</p>}

      <p className="settings__hint" style={{ margin: 0 }}>
        Terms reviewed {status.provider.terms_reviewed_date}. Subscription and the Odds &amp;
        Predictions add-on are purchased directly from Sportmonks. No logos or player images are
        requested.{" "}
        <a href={status.provider.docs_url} target="_blank" rel="noreferrer" onClick={handleExternalLinkClick}>API docs</a>
        {" · "}<a href={status.provider.pricing_url} target="_blank" rel="noreferrer" onClick={handleExternalLinkClick}>Pricing</a>
        {" · "}<a href={status.provider.terms_url} target="_blank" rel="noreferrer" onClick={handleExternalLinkClick}>Terms</a>
        {" · "}<a href={status.provider.privacy_url} target="_blank" rel="noreferrer" onClick={handleExternalLinkClick}>Privacy</a>
      </p>
    </div>
  );
}
