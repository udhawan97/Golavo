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
import { defaultModelAssignment, downloadFollowCalendar, fetchLocalModels, sourceDescription } from "../lib/api";
import type { LocalModelInfo } from "../lib/api";
import { AI_PROVIDERS, useAiBackground, useAiModels, useAiProvider } from "../lib/ai";
import type { AiProvider } from "../lib/ai";
import { useDataRefresh } from "../lib/data-refresh-context";
import type { DataRefreshPolicy } from "../lib/fixtures";
import type { ReadingPrefs } from "../lib/hooks";
import { ReadingControls } from "../components/ReadingComfort";
import { useUpdater } from "../lib/updater-context";
import { ERROR_HINTS, ERROR_TITLES, formatBytes, formatWhen } from "../lib/updater";
import type { UpdaterController } from "../lib/updater";
import { ProgressBar, ReleaseNotes } from "../components/updates";
import { DOCS_URL, RELEASES_URL } from "../lib/links";
import { handleExternalLinkClick } from "../lib/external-links";
import { replayTours, tourEnabled } from "../lib/tour";
import { openPageGuide } from "../lib/guides";
import {
  LOCAL_MODELS_CHANGED_EVENT,
  OllamaModelGuide,
} from "../components/ai/OllamaModelGuide";
import { OpenLigaDBSettings } from "../components/OpenLigaDBSettings";
import { useFollows } from "../lib/follow-context";
import { BellIcon, CheckIcon, PitchIcon } from "../components/icons";
import { useCorrections } from "../lib/correction-context";
import { ResearchSettingsPanel } from "../components/ResearchSettings";
import { SportmonksSettings } from "../components/SportmonksSettings";
import {
  FollowHistoryRemovalAction,
  ProposalRemovalAction,
} from "../components/DataRemovalActions";

function appVersionLabel(statusVersion: string | undefined): string {
  if (statusVersion) return statusVersion;
  const injected = window.__GOLAVO_RUNTIME__?.appVersion;
  return injected ?? `source build (contract v${SCHEMA_VERSION})`;
}

function SettingsSectionHead({
  id,
  eyebrow,
  title,
  summary,
}: {
  id: string;
  eyebrow: string;
  title: string;
  summary: string;
}) {
  return (
    <div className="settings__section-head">
      <p>{eyebrow}</p>
      <h2 id={id} tabIndex={-1}>{title}</h2>
      <span>{summary}</span>
    </div>
  );
}

function jumpToSettingsSection(id: string): void {
  const heading = document.getElementById(id);
  if (!heading) return;
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  heading.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
  heading.focus({ preventScroll: true });
}

const REFRESH_SOURCE_LABELS: Record<string, string> = {
  "martj42-international-results": "International results",
  "openfootball-worldcup-json": "World Cup fixtures",
  "openfootball-football-json": "Top-five historical base",
  "openfootball-england": "Premier League current season",
  "openfootball-deutschland": "Bundesliga current season",
  "openfootball-espana": "La Liga current season",
  "openfootball-italy": "Serie A current season",
  "openfootball-europe": "Ligue 1 current season",
};

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
  const dataRefresh = useDataRefresh();
  const follows = useFollows();
  const corrections = useCorrections();
  const [aiProvider, setAiProvider] = useAiProvider();
  const [aiBackground, setAiBackground] = useAiBackground();
  const version = appVersionLabel(u.status?.appVersion);
  const buildSha = window.__GOLAVO_RUNTIME__?.buildSha;
  // From the persisted skip, not the live phase — so it's manageable even on a
  // fresh boot with auto-check off, where no check has run this session.
  const skipped = u.skippedVersion;

  return (
    <div className="stack settings">
      <header className="settings__hero" aria-labelledby="settings-title">
        <div className="settings__hero-copy">
          <p className="settings__eyebrow"><PitchIcon size={16} /> Control room</p>
          <h1 id="settings-title">Settings</h1>
          <p>
            Shape how Golavo reads, refreshes, and connects. Every optional network lane stays
            visible, bounded, and off until you choose it.
          </p>
        </div>
        <div className="settings__boundary" role="note" aria-label="Golavo's permanent boundaries">
          <p>Local by default</p>
          <ul>
            <li><CheckIcon size={15} /> No account required</li>
            <li><CheckIcon size={15} /> Network choices are opt-in</li>
            <li><CheckIcon size={15} /> Sealed forecasts never change</li>
          </ul>
        </div>
      </header>

      <nav className="settings__nav" aria-label="Settings sections">
        <span>Jump to</span>
        <button type="button" onClick={() => jumpToSettingsSection("settings-appearance")}>Reading</button>
        <button type="button" onClick={() => jumpToSettingsSection("settings-data")}>Sources</button>
        <button type="button" onClick={() => jumpToSettingsSection("settings-ai")}>Intelligence</button>
        <button type="button" onClick={() => jumpToSettingsSection("settings-updates")}>Updates</button>
        <button type="button" onClick={() => jumpToSettingsSection("settings-about")}>Install</button>
      </nav>

      <div className="settings__intro-grid">
        {prefs && onChangePrefs && (
          <section className="panel settings__panel settings__panel--reading" aria-labelledby="settings-appearance">
            <div className="panel__head">
              <SettingsSectionHead
                id="settings-appearance"
                eyebrow="Reading"
                title="Appearance"
                summary="Make every page comfortable without changing its data."
              />
            </div>
            <div className="panel__body stack" style={{ ["--gap" as string]: "var(--space-3)" }}>
              <p className="small dim" style={{ margin: 0 }}>
                These are the same controls as the <span aria-hidden>“Aa”</span> button in the
                header. Choices apply everywhere and stay on this device.
              </p>
              <ReadingControls prefs={prefs} onChange={onChangePrefs} />
            </div>
          </section>
        )}

        <section className="panel settings__panel settings__panel--guide" aria-labelledby="settings-tour">
          <div className="panel__head">
            <SettingsSectionHead
              id="settings-tour"
              eyebrow="Guidance"
              title="Help that follows the page"
              summary="Open a short, contextual guide whenever you need your next step."
            />
          </div>
          <div className="panel__body stack" style={{ ["--gap" as string]: "var(--space-3)" }}>
            <p className="settings__hint">
              The book button in the header explains the page you are on, what to do first, and
              where to go next. It never changes a setting or starts a network request.
            </p>
            <div className="controls">
              <button type="button" className="btn btn--primary" onClick={openPageGuide}>
                Open this page’s guide
              </button>
              {tourEnabled() && (
                <button
                  type="button"
                  className="btn btn--ghost"
                  onClick={() => {
                    window.location.hash = "#/";
                    replayTours();
                  }}
                >
                  Replay spotlight tour
                </button>
              )}
            </div>
          </div>
        </section>
      </div>

      <section className="panel settings__panel" aria-labelledby="settings-data">
        <div className="panel__head">
          <SettingsSectionHead
            id="settings-data"
            eyebrow="Sources"
            title="Data &amp; local history"
            summary="Choose what may refresh, what remains separate, and what to remove."
          />
        </div>
        <div className="panel__body stack settings__rows">
          <div className="settings__field">
            <div className="settings__row">
              <label htmlFor="data-refresh-policy">Approved-source refresh</label>
              <select
                id="data-refresh-policy"
                className="select"
                value={dataRefresh.policy}
                onChange={(event) => dataRefresh.setPolicy(event.target.value as DataRefreshPolicy)}
              >
                <option value="off">Off</option>
                <option value="check_only">Check and tell me</option>
                <option value="auto_refresh">Refresh while Golavo is open</option>
              </select>
            </div>
            <p className="settings__hint">
              Off by default. <b>Check and tell me</b> reads only source revisions. <b>Refresh</b>
              downloads pinned CC0 snapshots, validates a complete new generation, and activates it
              atomically. Automatic work runs only while this window is open; Golavo installs no
              helper or background daemon. Existing sealed forecasts are never changed.
            </p>
            <div className="settings__row" style={{ justifyContent: "flex-start", gap: ".6rem", flexWrap: "wrap" }}>
              <button type="button" className="btn btn--ghost" onClick={() => void dataRefresh.checkNow()}>
                Check approved sources
              </button>
              <button type="button" className="btn btn--primary" onClick={() => void dataRefresh.refreshNow()}>
                Refresh now
              </button>
              {(dataRefresh.job?.state === "queued" || dataRefresh.job?.state === "running") && (
                <button type="button" className="btn btn--ghost" onClick={() => void dataRefresh.cancel()}>
                  Cancel
                </button>
              )}
              {dataRefresh.status?.active_generation?.rollback_available && (
                <button type="button" className="btn btn--ghost" onClick={() => void dataRefresh.rollback()}>
                  Use previous data
                </button>
              )}
            </div>
            {dataRefresh.job && (dataRefresh.job.state === "queued" || dataRefresh.job.state === "running") && (
              <p className="settings__hint" role="status">
                Refresh stage: <b>{dataRefresh.job.stage.replaceAll("_", " ")}</b>. The current data
                stays active until validation and the final atomic swap finish.
              </p>
            )}
            {dataRefresh.error && (
              <p className="settings__hint" role="alert">Refresh could not complete: {dataRefresh.error.message}</p>
            )}
            {dataRefresh.status && (
              <div className="stack" style={{ ["--gap" as string]: ".45rem" }}>
                {dataRefresh.status.sources.map((source) => (
                  <div className="settings__row" key={source.source_id}>
                    <span>
                      {REFRESH_SOURCE_LABELS[source.source_id] ?? source.source_id}
                    </span>
                    <span className="small dim" style={{ textAlign: "right" }}>
                      {source.capability === "absent"
                        ? `${source.season ?? "Current season"} not published by source`
                        : `${source.health} · ${source.capability}`}
                      {source.last_checked_at_utc
                        ? ` · checked ${formatWhen(Date.parse(source.last_checked_at_utc))}`
                        : " · not checked yet"}
                      {source.last_activated_at_utc
                        ? ` · activated ${formatWhen(Date.parse(source.last_activated_at_utc))}`
                        : ""}
                      {source.active_ref ? ` · active ${source.active_ref.slice(0, 8)}` : ""}
                      {source.observed_ref && source.observed_ref !== source.active_ref
                        ? ` · observed ${source.observed_ref.slice(0, 8)}`
                        : ""}
                    </span>
                  </div>
                ))}
                {dataRefresh.status.using_bundled_fallback && (
                  <p className="settings__hint">Using the bundled, offline data generation.</p>
                )}
              </div>
            )}
          </div>
          <hr style={{ width: "100%", border: 0, borderTop: "1px solid var(--line)" }} />
          <div className="settings__field">
            <div className="settings__row">
              <div>
                <label>Followed matches</label>
                <p className="settings__hint" style={{ margin: ".2rem 0 0" }}>
                  {follows.list.total === 1 ? "1 match followed locally" : `${follows.list.total} matches followed locally`}
                </p>
                {follows.list.total > 0 && <p className="settings__hint" style={{ margin: ".2rem 0 0" }}>
                  Calendar: {follows.list.calendar_exportable_count} exact-time {follows.list.calendar_exportable_count === 1 ? "match" : "matches"} included · {follows.list.calendar_omitted_count} date-only or unknown-time {follows.list.calendar_omitted_count === 1 ? "match" : "matches"} omitted. Golavo never guesses a kickoff time.
                </p>}
              </div>
              {follows.list.total > 0 && (
                <div className="controls">
                  <button type="button" className="btn btn--ghost" disabled={follows.list.calendar_exportable_count === 0} onClick={() => void downloadFollowCalendar()}>Export calendar</button>
                  <button
                    type="button"
                    className="btn btn--ghost"
                    onClick={() => void dataRefresh.refreshFollowedNow()}
                  >
                    Check followed matches
                  </button>
                </div>
              )}
            </div>
            <p className="settings__hint">
              Golavo checks followed matches on launch and periodically only while the app is
              running. Closing Golavo stops checks. No helper, Login Item, or LaunchAgent is
              installed. Following never changes a sealed forecast or enables network refresh.
            </p>
            <div className="settings__row">
              <span className="inline-icon"><BellIcon /> Local notifications</span>
              {follows.settings.notifications_opt_in ? (
                <button
                  type="button"
                  className="btn btn--ghost"
                  onClick={() => void follows.disableNotifications()}
                >
                  Disable notifications
                </button>
              ) : (
                <button
                  type="button"
                  className="btn btn--ghost"
                  disabled={!follows.settings.notifications_supported}
                  onClick={() => void follows.enableNotifications()}
                >
                  Enable local notifications
                </button>
              )}
            </div>
            <p className="settings__hint">
              Notifications are sent only for changes Golavo detects while it is open. They do not
              monitor matches after you quit. Notification text is generic and never exposes teams,
              scores, picks, or probabilities on the lock screen.
              {!follows.settings.notifications_supported && " Notifications are available in the installed desktop app."}
              {follows.permission === "denied" && " Permission was denied; followed matches and history still work normally."}
            </p>
            <div className="settings__row">
              <span>Local follow history</span>
              <FollowHistoryRemovalAction onConfirm={follows.removeHistory} />
            </div>
            {follows.error && <p className="settings__hint" role="alert">{follows.error.message}</p>}
          </div>
          <div className="settings__row">
            <span>Proofs, backups &amp; local integrity</span>
            <a href="#/trust">Open Trust Center ›</a>
          </div>
          <div className="settings__row">
            <span>Map &amp; place data</span>
            <span className="dim">
              Data from <a href="https://www.geonames.org/" target="_blank" rel="noreferrer" onClick={handleExternalLinkClick}>GeoNames</a>, CC BY 4.0
              {" · "}Made with <a href="https://www.naturalearthdata.com/" target="_blank" rel="noreferrer" onClick={handleExternalLinkClick}>Natural Earth</a>
            </span>
          </div>
          <hr style={{ width: "100%", border: 0, borderTop: "1px solid var(--line)" }} />
          <OpenLigaDBSettings />
          <hr style={{ width: "100%", border: 0, borderTop: "1px solid var(--line)" }} />
          <SportmonksSettings />
          <hr style={{ width: "100%", border: 0, borderTop: "1px solid var(--line)" }} />
          <div className="settings__field">
            <div className="settings__row">
              <span>
                <b>Correction proposals</b>
                <span className="dim"> · {corrections.list.total} stored locally</span>
              </span>
              <a className="btn btn--ghost" href="#/corrections">Review queue</a>
            </div>
            <p className="settings__hint">
              No account or moderation service. Proposals and captured evidence stay on this Mac,
              separated by source license. They never change bundled packs, verified indexes,
              forecasts, settlement, calibration, or model inputs.
            </p>
            <div className="settings__row">
              <span>Local proposal data</span>
              <ProposalRemovalAction onConfirm={corrections.removeAll} />
            </div>
            {corrections.error && <p className="settings__hint" role="alert">{corrections.error.message}</p>}
          </div>
        </div>
      </section>

      <section id="local-ai-setup" className="panel settings__panel settings__panel--intelligence" aria-labelledby="settings-ai">
        <div className="panel__head">
          <SettingsSectionHead
            id="settings-ai"
            eyebrow="Analysis"
            title="Local intelligence"
            summary="Add explanation around the sealed numbers without giving AI the whistle."
          />
        </div>
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

            <ResearchSettingsPanel />
          </div>
        </div>
      </section>

      <section className="panel settings__panel" aria-labelledby="settings-updates">
        <div className="panel__head">
          <SettingsSectionHead
            id="settings-updates"
            eyebrow="Maintenance"
            title="Updates"
            summary="Keep the application current through the path this build actually supports."
          />
        </div>
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

      <section className="panel settings__panel settings__panel--about" aria-labelledby="settings-about">
        <div className="panel__head">
          <SettingsSectionHead
            id="settings-about"
            eyebrow="Install"
            title="About this build"
            summary="The exact version, engine, and public reference links for this install."
          />
        </div>
        <div className="panel__body stack settings__rows">
          <div className="settings__row">
            <span>Version</span>
            <span className="chip chip--neutral">Golavo {version}</span>
          </div>
          <div className="settings__row">
            <span>Build</span>
            <span className="mono dim" title={buildSha}>
              {buildSha ? buildSha.slice(0, 12) : "source build"}
            </span>
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
              <a
                href={RELEASES_URL}
                target="_blank"
                rel="noreferrer"
                onClick={handleExternalLinkClick}
              >
                releases page
              </a>.
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
            <a
              href={RELEASES_URL}
              target="_blank"
              rel="noreferrer"
              onClick={handleExternalLinkClick}
            >
              releases page
            </a>
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
