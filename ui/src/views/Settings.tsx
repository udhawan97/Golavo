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
import { AI_PROVIDERS, useAiBackground, useAiProvider } from "../lib/ai";
import { useKeepFixturesFresh } from "../lib/fixtures";
import type { ReadingPrefs } from "../lib/hooks";
import { ReadingControls } from "../components/ReadingComfort";
import { useUpdater } from "../lib/updater-context";
import { formatWhen } from "../lib/updater";
import { DOCS_URL, RELEASES_URL } from "../lib/links";

function appVersionLabel(statusVersion: string | undefined): string {
  if (statusVersion) return statusVersion;
  const injected = window.__GOLAVO_RUNTIME__?.appVersion;
  return injected ?? `source build (contract v${SCHEMA_VERSION})`;
}

export function Settings({
  prefs,
  onChangePrefs,
}: {
  prefs?: ReadingPrefs;
  onChangePrefs?: (patch: Partial<ReadingPrefs>) => void;
} = {}) {
  const u = useUpdater();
  const [keepFresh, setKeepFresh] = useKeepFixturesFresh();
  const [aiProvider, setAiProvider] = useAiProvider();
  const [aiBackground, setAiBackground] = useAiBackground();
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

      {prefs && onChangePrefs && (
        <section className="panel" aria-labelledby="settings-appearance">
          <div className="panel__head"><h2 id="settings-appearance">Appearance</h2></div>
          <div className="panel__body stack" style={{ ["--gap" as string]: "var(--space-3)" }}>
            <p className="small dim" style={{ margin: 0 }}>
              The same theme and reading controls as the <span aria-hidden>“Aa”</span> button in the
              header. Choices apply everywhere and are remembered on this device.
            </p>
            <ReadingControls prefs={prefs} onChange={onChangePrefs} />
          </div>
        </section>
      )}

      <section className="panel" aria-labelledby="settings-data">
        <div className="panel__head"><h2 id="settings-data">Data</h2></div>
        <div className="panel__body stack settings__rows">
          <div className="settings__field">
            <div className="settings__row">
              <label htmlFor="fixtures-toggle">Keep fixtures up to date</label>
              <input
                id="fixtures-toggle"
                type="checkbox"
                checked={keepFresh}
                onChange={(e) => setKeepFresh(e.target.checked)}
              />
            </div>
            <p className="settings__hint">
              When on, Golavo asks the public CC0 fixture source, on launch, whether a new
              upcoming international match has appeared, and flags it on the Matches page so you
              can forecast it. This is the only time the app reaches the internet on its own —
              it’s off by default, reads only public fixture data, and sends nothing.
            </p>
          </div>
        </div>
      </section>

      <section className="panel" aria-labelledby="settings-ai">
        <div className="panel__head"><h2 id="settings-ai">Local intelligence</h2></div>
        <div className="panel__body stack settings__rows">
          <div className="settings__field">
            <div className="settings__row">
              <label htmlFor="ai-provider">AI Deep Read</label>
              <select
                id="ai-provider"
                className="select"
                value={aiProvider}
                onChange={(e) => setAiProvider(e.target.value as typeof aiProvider)}
              >
                {AI_PROVIDERS.map((p) => (
                  <option key={p.value} value={p.value}>{p.label}</option>
                ))}
              </select>
            </div>
            <p className="settings__hint">
              Off by default. Choose a model to enable the optional <b>AI Deep Read</b> panel on
              forecast pages — it only reads and cites the sealed numbers, and can never change a
              probability or improve accuracy. <b>Local</b> options (Ollama, llama.cpp) run entirely
              on your machine and send nothing out; the BYOK options send the evidence bundle to
              that provider with your own key. The AI runs through Golavo’s local engine, so in this
              sample build it will show as unavailable until a desktop engine is connected.
            </p>
            <div className="settings__row">
              <label htmlFor="ai-background">AI background (general knowledge)</label>
              <input
                id="ai-background"
                type="checkbox"
                checked={aiBackground}
                onChange={(e) => setAiBackground(e.target.checked)}
              />
            </div>
            <p className="settings__hint">
              Optional second lane, off by default. When on, the model may add qualitative colour —
              managers, style reputations, rivalries — from its <b>own general knowledge</b>. It is
              clearly badged as not-Golavo-data, may be outdated, and is <b>forbidden from stating any
              number</b>: anything numeric it writes is deleted before you see it. The grounded read
              above it is unchanged.
            </p>
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
              <div className="settings__field">
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
                <p className="settings__hint">
                  Once a day, Golavo asks GitHub whether a newer version exists. Nothing else
                  leaves your machine; downloads only start when you click.
                </p>
              </div>

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
