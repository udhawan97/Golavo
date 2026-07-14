/**
 * Settings — About & updates.
 *
 * The one place every build tells the truth about itself: version, data source,
 * and how THIS build updates. Updater-enabled desktop builds get the controls
 * (auto-check toggle, manual check, skip management, last-update record);
 * source/dev builds get an honest note instead of broken affordances.
 */
import { useEffect, useState } from "react";
import { SCHEMA_VERSION } from "../lib/contract";
import { defaultModelAssignment, fetchLocalModels, sourceDescription } from "../lib/api";
import type { LocalModelInfo } from "../lib/api";
import { AI_PROVIDERS, useAiBackground, useAiModels, useAiProvider, useAiResearch } from "../lib/ai";
import type { AiProvider } from "../lib/ai";
import { useKeepFixturesFresh } from "../lib/fixtures";
import type { ReadingPrefs } from "../lib/hooks";
import { ReadingControls } from "../components/ReadingComfort";
import { useUpdater } from "../lib/updater-context";
import { ERROR_HINTS, ERROR_TITLES, formatBytes, formatWhen } from "../lib/updater";
import type { UpdaterController } from "../lib/updater";
import { ProgressBar, ReleaseNotes } from "../components/updates";
import { DOCS_URL, RELEASES_URL } from "../lib/links";
import { handleExternalLinkClick } from "../lib/external-links";
import { replayTours, tourEnabled } from "../lib/tour";
import {
  LOCAL_MODELS_CHANGED_EVENT,
  OllamaModelGuide,
} from "../components/ai/OllamaModelGuide";

function appVersionLabel(statusVersion: string | undefined): string {
  if (statusVersion) return statusVersion;
  const injected = window.__GOLAVO_RUNTIME__?.appVersion;
  return injected ?? `source build (contract v${SCHEMA_VERSION})`;
}

/** Assign which installed local model runs the Fast and Deep reads. Auto-detects
 *  a sensible default (Fast = smallest, Deep = largest) the first time. Only
 *  meaningful for local providers; hidden otherwise. */
function LocalModelPicker({ provider }: { provider: AiProvider }) {
  const { fastModel, deepModel, setFastModel, setDeepModel } = useAiModels();
  const [models, setModels] = useState<LocalModelInfo[]>([]);
  const [loaded, setLoaded] = useState(false);
  const isLocal = provider === "ollama" || provider === "llama_server";

  useEffect(() => {
    if (!isLocal) return;
    let live = true;
    const load = () => {
      setLoaded(false);
      fetchLocalModels(provider).then((m) => {
        if (!live) return;
        setModels(m);
        setLoaded(true);
        // Auto-assign defaults when unset or when the stored choice is no longer
        // installed, so the picker is never empty on a machine that has models.
        const names = new Set(m.map((x) => x.name));
        if (m.length > 0) {
          const def = defaultModelAssignment(m);
          if (!fastModel || !names.has(fastModel)) setFastModel(def.fast);
          if (!deepModel || !names.has(deepModel)) setDeepModel(def.deep);
        }
      });
    };
    load();
    window.addEventListener(LOCAL_MODELS_CHANGED_EVENT, load);
    return () => {
      live = false;
      window.removeEventListener(LOCAL_MODELS_CHANGED_EVENT, load);
    };
    // Re-run only when the provider changes; assignment setters are stable.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [provider, isLocal]);

  if (!isLocal) return null;

  const label = (m: LocalModelInfo) => `${m.name}${m.parameter_size ? ` · ${m.parameter_size}` : ""}`;
  return (
    <div className="settings__field ai-model-picker">
      <div className="settings__row">
        <label htmlFor="ai-fast-model">Fast model</label>
        <select
          id="ai-fast-model"
          className="select"
          value={fastModel}
          disabled={models.length === 0}
          onChange={(e) => setFastModel(e.target.value)}
        >
          {models.length === 0 && <option value="">{loaded ? "no models found" : "loading…"}</option>}
          {models.map((m) => <option key={m.name} value={m.name}>{label(m)}</option>)}
        </select>
      </div>
      <div className="settings__row">
        <label htmlFor="ai-deep-model">Deep model</label>
        <select
          id="ai-deep-model"
          className="select"
          value={deepModel}
          disabled={models.length === 0}
          onChange={(e) => setDeepModel(e.target.value)}
        >
          {models.length === 0 && <option value="">{loaded ? "no models found" : "loading…"}</option>}
          {models.map((m) => <option key={m.name} value={m.name}>{label(m)}</option>)}
        </select>
      </div>
      <p className="settings__hint">
        The <b>Fast</b> model runs the quick read (seconds); the <b>Deep</b> model runs the fuller
        analysis (a bigger model, usually 5–8 minutes). Pick them from the models you have installed —
        auto-set to smallest and largest.{" "}
        {loaded && models.length === 0 && "Start Ollama and pull a model to choose here."}
      </p>
    </div>
  );
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
  const [aiResearch, setAiResearch] = useAiResearch();
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
              <a href={RELEASES_URL} target="_blank" rel="noreferrer" onClick={handleExternalLinkClick}>Releases</a>
              {" · "}
              <a href={DOCS_URL} target="_blank" rel="noreferrer" onClick={handleExternalLinkClick}>Documentation</a>
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

      {tourEnabled() && (
        <section className="panel" aria-labelledby="settings-tour">
          <div className="panel__head"><h2 id="settings-tour">Getting started</h2></div>
          <div className="panel__body stack" style={{ ["--gap" as string]: "var(--space-3)" }}>
            <div className="settings__row">
              <div>
                <label>Show the guided tour again</label>
                <p className="settings__hint" style={{ margin: ".2rem 0 0" }}>
                  Replays the short spotlight tour of the home and a match’s cockpit.
                </p>
              </div>
              <button
                type="button"
                className="btn btn--ghost"
                onClick={() => {
                  // Land on the home first so the tour's first anchor exists.
                  window.location.hash = "#/";
                  replayTours();
                }}
              >
                Replay tour
              </button>
            </div>
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

      <section id="local-ai-setup" className="panel" aria-labelledby="settings-ai">
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

            {(aiProvider === "off" || aiProvider === "ollama") && (
              <OllamaModelGuide
                ollamaActive={aiProvider === "ollama"}
                onActivateOllama={() => setAiProvider("ollama")}
              />
            )}

            <LocalModelPicker provider={aiProvider} />

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

            <div className="settings__row">
              <label htmlFor="ai-research">Let the AI research on the web</label>
              <input
                id="ai-research"
                type="checkbox"
                checked={aiResearch}
                onChange={(e) => setAiResearch(e.target.checked)}
              />
            </div>
            <p className="settings__hint">
              Off by default — this is the <b>only</b> setting that lets the app reach the general web.
              When on, a read fetches a few <b>Wikipedia</b> pages and a <b>web search</b> for the
              fixture and adds an <b>“Analyst research”</b> section. Those findings are clearly badged
              <b> not engine-verified</b>: their numbers are checked against the quoted page, never
              against Golavo’s engine, and the grounded read above is unchanged. Web search is
              best-effort — it quietly falls back to Wikipedia-only when unavailable.
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

          {u.isDesktop && u.status && !u.status.enabled && <FallbackUpdates u={u} />}

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

/**
 * Updates panel for builds WITHOUT the signed updater (dev/source builds).
 *
 * Rather than dead-ending on a "go to the releases page" link, this fetches the
 * latest release straight from GitHub and downloads the correct installer, then
 * opens it. The final install step is manual (drag to Applications / run the
 * setup) because Golavo does NOT cryptographically verify the artifact here (the
 * signed updater's job) — trust is the OS's installer check. The copy says so
 * plainly, and the check is manual to honour the no-surprise-network promise.
 */
function FallbackUpdates({ u }: { u: UpdaterController }) {
  const current = u.status?.appVersion ?? "";
  const platform = u.status?.platform ?? "other";
  const phase = u.fallbackPhase;

  const installHint =
    platform === "windows"
      ? "This runs the official installer — follow its prompts. Golavo stops its background helper so the installer can replace it; reopen Golavo when it finishes."
      : platform === "macos"
        ? "This opens the disk image — drag Golavo into your Applications folder (replacing the old one), then reopen Golavo."
        : "Open the downloaded file to install, then reopen Golavo.";

  return (
    <div className="stack settings__rows" data-testid="fallback-updates">
      <p className="dim">
        This build doesn’t include the signed auto-updater, so Golavo can’t swap itself in
        place. It can still fetch the latest release from GitHub and download the installer
        for you — you finish the install yourself. Nothing is downloaded until you click.
      </p>
      <p className="dim">
        Unlike the signed auto-updater, Golavo <b>can’t cryptographically verify this download
        itself</b> — your operating system checks the installer when you open it, so only
        update on a network you trust. The installer replaces the Golavo app only; your ledger
        and data are left untouched (no automatic backup is taken on this path).
      </p>

      {phase.kind === "checking" ? (
        <p role="status" aria-live="polite">Checking GitHub for the latest release…</p>
      ) : phase.kind === "downloading" ? (
        <>
          <p>Downloading Golavo {phase.rel.version}…</p>
          <ProgressBar downloaded={phase.downloaded} total={phase.total} />
          <div className="settings__row">
            <button type="button" className="btn" onClick={() => void u.fallbackCancel()}>
              Cancel
            </button>
          </div>
        </>
      ) : phase.kind === "ready" ? (
        <>
          <p role="status" aria-live="polite">
            <strong>Golavo {phase.rel.version}</strong> is downloaded.
          </p>
          <p className="settings__hint">{installHint}</p>
          {phase.openError && (
            <p className="dim">
              Couldn’t open it automatically ({phase.openError.message}). It’s saved at{" "}
              <code>{phase.path}</code> — open it yourself, or download again.
            </p>
          )}
          <div className="settings__row">
            <button
              type="button"
              className="btn btn--primary"
              onClick={() => void u.fallbackOpen()}
            >
              Open installer
            </button>
            <button type="button" className="btn btn--ghost" onClick={() => void u.fallbackDownload()}>
              Download again
            </button>
          </div>
          {!phase.openError && (
            <p className="settings__hint">
              Saved at <code>{phase.path}</code> (re-download only if it won’t open).
            </p>
          )}
        </>
      ) : phase.kind === "available" ? (
        <>
          <p role="status" aria-live="polite">
            <strong>Golavo {phase.rel.version}</strong> is available
            {current ? <> — you have {current}</> : null}.
          </p>
          {phase.rel.notes && <ReleaseNotes notes={phase.rel.notes} />}
          {phase.rel.assetUrl ? (
            <>
              <div className="settings__row">
                <button
                  type="button"
                  className="btn btn--primary"
                  onClick={() => void u.fallbackDownload()}
                >
                  Download {phase.rel.version}
                  {phase.rel.assetSize ? ` (${formatBytes(phase.rel.assetSize)})` : ""}
                </button>
                <button type="button" className="btn btn--ghost" onClick={() => void u.fallbackCheck()}>
                  Check again
                </button>
              </div>
              <p className="settings__hint">{installHint}</p>
            </>
          ) : (
            <p className="settings__hint">
              There’s no installer for your platform in that release. Update from the{" "}
              <a href={RELEASES_URL} target="_blank" rel="noreferrer">releases page</a>.
            </p>
          )}
        </>
      ) : phase.kind === "upToDate" ? (
        <>
          <p role="status" aria-live="polite">
            You’re on the latest version{phase.version ? ` — Golavo ${phase.version}` : ""}.
          </p>
          <div className="settings__row">
            <span className="dim">
              {u.lastCheckedAt ? `Last checked ${formatWhen(u.lastCheckedAt)}` : ""}
            </span>
            <button type="button" className="btn" onClick={() => void u.fallbackCheck()}>
              Check again
            </button>
          </div>
        </>
      ) : phase.kind === "error" ? (
        <>
          <p role="status" aria-live="polite"><strong>{ERROR_TITLES[phase.error.kind]}</strong></p>
          {ERROR_HINTS[phase.error.kind] && (
            <p className="dim">{ERROR_HINTS[phase.error.kind]}</p>
          )}
          <p className="dim">{phase.error.message}</p>
          <div className="settings__row">
            <button
              type="button"
              className="btn"
              onClick={() =>
                // Retry the exact action that failed (tracked on the phase), so a
                // failed re-check re-checks instead of downloading a stale rel.
                phase.retry === "download" ? void u.fallbackDownload() : void u.fallbackCheck()
              }
            >
              Try again
            </button>
            <a href={RELEASES_URL} target="_blank" rel="noreferrer">releases page</a>
          </div>
        </>
      ) : (
        <div className="settings__row">
          <span>
            {u.lastCheckedAt
              ? `Last checked ${formatWhen(u.lastCheckedAt)}`
              : "Not checked yet"}
          </span>
          <button type="button" className="btn" onClick={() => void u.fallbackCheck()}>
            Check for updates
          </button>
        </div>
      )}
    </div>
  );
}
