/**
 * Settings — About & updates.
 *
 * The one place every build tells the truth about itself: version, data source,
 * and how THIS build updates. Updater-enabled desktop builds get the controls
 * (auto-check toggle, manual check, skip management, last-update record);
 * source/dev builds get an honest note instead of broken affordances.
 */
import { SCHEMA_VERSION } from "../lib/contract";
import { sourceDescription } from "../lib/api";
import { useUpdater } from "../lib/updater-context";
import { formatWhen } from "../lib/updater";
import { DOCS_URL, RELEASES_URL } from "../lib/links";

function appVersionLabel(statusVersion: string | undefined): string {
  if (statusVersion) return statusVersion;
  const injected = window.__GOLAVO_RUNTIME__?.appVersion;
  return injected ?? `source build (contract v${SCHEMA_VERSION})`;
}

export function Settings() {
  const u = useUpdater();
  const version = appVersionLabel(u.status?.appVersion);
  // From the persisted skip, not the live phase — so it's manageable even on a
  // fresh boot with auto-check off, where no check has run this session.
  const skipped = u.skippedVersion;

  return (
    <div className="stack settings">
      <header>
        <h1>Settings</h1>
        <p className="dim">About this install, and how it stays current.</p>
      </header>

      <section className="panel" aria-labelledby="settings-about">
        <div className="panel__head"><h2 id="settings-about">About</h2></div>
        <div className="panel__body stack settings__rows">
          <div className="settings__row">
            <span>Version</span>
            <span className="chip chip--neutral">Golavo {version}</span>
          </div>
          <div className="settings__row">
            <span>Data source</span>
            <span className="dim">{sourceDescription()}</span>
          </div>
          <div className="settings__row">
            <span>Links</span>
            <span>
              <a href={RELEASES_URL} target="_blank" rel="noreferrer">Releases</a>
              {" · "}
              <a href={DOCS_URL} target="_blank" rel="noreferrer">Documentation</a>
            </span>
          </div>
        </div>
      </section>

      <section className="panel" aria-labelledby="settings-updates">
        <div className="panel__head"><h2 id="settings-updates">Updates</h2></div>
        <div className="panel__body stack settings__rows">
          {!u.isDesktop && (
            <p className="dim">
              You’re running Golavo from source — update with <code>git pull</code>.
              The desktop app updates itself in-app.
            </p>
          )}

          {u.isDesktop && u.status && !u.status.enabled && (
            <p className="dim">
              This desktop build has no signed updater (development build). Update with a
              fresh download from the <a href={RELEASES_URL} target="_blank" rel="noreferrer">releases page</a>.
            </p>
          )}

          {u.isDesktop && u.status?.enabled && (
            <>
              <div className="settings__row">
                <label htmlFor="autocheck-toggle">Check for updates automatically</label>
                <input
                  id="autocheck-toggle"
                  type="checkbox"
                  checked={u.autoCheck === "on"}
                  onChange={(e) => {
                    const on = e.target.checked;
                    u.setAutoCheck(on ? "on" : "off");
                    // Match the consent card: enabling checks now, not in ~20s.
                    if (on) void u.check();
                  }}
                />
              </div>
              <p className="dim settings__hint">
                Once a day, Golavo asks GitHub whether a newer version exists. Nothing else
                leaves your machine; downloads only start when you click.
              </p>

              <div className="settings__row">
                <span>
                  {u.lastCheckedAt
                    ? `Last checked ${formatWhen(u.lastCheckedAt)}`
                    : "Not checked yet this install"}
                </span>
                <button
                  type="button"
                  className="btn"
                  onClick={() => { u.openSheet(); void u.check({ manual: true }); }}
                >
                  Check now
                </button>
              </div>

              {skipped && (
                <div className="settings__row">
                  <span className="dim">Skipping reminders for Golavo {skipped}</span>
                  <button type="button" className="btn btn--ghost" onClick={u.unskip}>
                    Show reminders again
                  </button>
                </div>
              )}

              {u.status.justUpdated && (
                <p className="dim">
                  Updated {u.status.justUpdated.from} → {u.status.justUpdated.to} on{" "}
                  {formatWhen(u.status.justUpdated.atEpoch * 1000)}
                  {u.status.justUpdated.backupTaken
                    ? " (ledger backed up before installing)."
                    : "."}
                </p>
              )}

              <p className="dim">
                Every update is cryptographically verified against the key built into this
                app before it installs, and your ledger is backed up first.
              </p>
            </>
          )}
        </div>
      </section>
    </div>
  );
}
