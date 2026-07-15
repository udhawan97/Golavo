import { useState } from "react";
import { handleExternalLinkClick } from "../lib/external-links";
import { formatBytes, formatWhen } from "../lib/updater";
import { useOpenLigaDB } from "../lib/openligadb-context";
import type { OpenLigaDBShortcut } from "../lib/openligadb";

const COMPETITIONS: Array<{ shortcut: OpenLigaDBShortcut; label: string }> = [
  { shortcut: "bl1", label: "Bundesliga" },
  { shortcut: "bl2", label: "2. Bundesliga" },
  { shortcut: "bl3", label: "3. Liga" },
  { shortcut: "dfb", label: "DFB-Pokal" },
];

function when(value: string | null): string {
  return value ? formatWhen(Date.parse(value)) : "never";
}

export function OpenLigaDBSettings() {
  const overlay = useOpenLigaDB();
  const [accepted, setAccepted] = useState(false);
  const status = overlay.status;
  const busy = overlay.job?.state === "queued" || overlay.job?.state === "running";

  if (!status) return <p className="settings__hint">Checking optional community overlay support…</p>;
  if (!status.overlay_supported) {
    return <p className="settings__hint">The optional OpenLigaDB overlay is unavailable in this build.</p>;
  }

  const toggleCompetition = (shortcut: OpenLigaDBShortcut) => {
    const selected = status.selected_competitions.includes(shortcut)
      ? status.selected_competitions.filter((item) => item !== shortcut)
      : [...status.selected_competitions, shortcut];
    if (selected.length > 0) void overlay.setCompetitions(selected);
  };

  return (
    <div className="settings__field stack" style={{ ["--gap" as string]: ".7rem" }}>
      <div className="settings__row">
        <div>
          <label>OpenLigaDB community overlay</label>
          <p className="settings__hint" style={{ margin: ".2rem 0 0" }}>
            Optional, keyless and fetched per user. Data is community-maintained under ODbL 1.0.
          </p>
        </div>
        <span className={`chip ${status.enabled ? "chip--success" : "chip--neutral"}`}>
          {status.enabled ? status.health : "off"}
        </span>
      </div>

      <p className="settings__hint" style={{ margin: 0 }}>
        <b>Display-only boundary:</b> this separate database never trains Golavo’s models, changes a
        probability, seals or settles a forecast, affects calibration, or enters exports. Source team
        identities are not fuzzy-merged with Golavo’s CC0 warehouse. Newer community data does not
        override a core fact.
      </p>

      {!status.enabled ? (
        <>
          <label className="settings__hint" style={{ display: "flex", gap: ".55rem", alignItems: "flex-start" }}>
            <input
              type="checkbox"
              checked={accepted}
              onChange={(event) => setAccepted(event.target.checked)}
            />
            <span>
              I understand OpenLigaDB data is ODbL, separately stored and community-maintained, and
              agree to the local fetch and attribution disclosure.
            </span>
          </label>
          <div>
            <button
              type="button"
              className="btn btn--primary"
              disabled={!accepted}
              onClick={() => void overlay.enable(accepted)}
            >
              Enable community overlay
            </button>
          </div>
        </>
      ) : (
        <>
          <div className="settings__row">
            <label htmlFor="openligadb-policy">Refresh</label>
            <select
              id="openligadb-policy"
              className="select"
              value={status.refresh_policy}
              onChange={(event) => void overlay.setPolicy(event.target.value as "manual" | "while_open")}
            >
              <option value="manual">Only when I click refresh</option>
              <option value="while_open">On launch and periodically while open</option>
            </select>
          </div>
          <p className="settings__hint" style={{ margin: 0 }}>
            Golavo installs no helper or LaunchAgent. Closing the app stops refresh work. The backend
            enforces this setting even if a stale UI attempts an automatic request.
          </p>
          <div className="settings__row" style={{ alignItems: "flex-start" }}>
            <span>Competitions</span>
            <span style={{ display: "grid", gap: ".35rem" }}>
              {COMPETITIONS.map((item) => (
                <label key={item.shortcut} className="small">
                  <input
                    type="checkbox"
                    checked={status.selected_competitions.includes(item.shortcut)}
                    disabled={status.selected_competitions.length === 1 && status.selected_competitions[0] === item.shortcut}
                    onChange={() => toggleCompetition(item.shortcut)}
                  />{" "}{item.label} <span className="dim">({item.shortcut})</span>
                </label>
              ))}
            </span>
          </div>
          <div className="settings__row" style={{ justifyContent: "flex-start", gap: ".6rem", flexWrap: "wrap" }}>
            <button type="button" className="btn btn--primary" disabled={busy} onClick={() => void overlay.refreshNow()}>
              Refresh overlay
            </button>
            {busy && (
              <button type="button" className="btn btn--ghost" onClick={() => void overlay.cancel()}>
                Cancel
              </button>
            )}
            {status.active_generation?.rollback_available && (
              <button type="button" className="btn btn--ghost" onClick={() => void overlay.rollback()}>
                Use previous overlay
              </button>
            )}
            <button type="button" className="btn btn--ghost" onClick={() => void overlay.disable()}>
              Disable
            </button>
            <button
              type="button"
              className="btn btn--ghost"
              onClick={() => {
                if (window.confirm("Delete all locally fetched OpenLigaDB responses and overlay databases? Golavo’s CC0 data and forecasts are unaffected.")) {
                  void overlay.deleteAll();
                }
              }}
            >
              Disable &amp; delete data
            </button>
          </div>
          {busy && (
            <p className="settings__hint" role="status">
              Overlay stage: <b>{overlay.job?.stage.replaceAll("_", " ")}</b>. The previous verified
              generation remains active until the atomic swap.
            </p>
          )}
        </>
      )}

      {overlay.error && <p className="settings__hint" role="alert">OpenLigaDB: {overlay.error.message}</p>}
      {status.last_error && (
        <p className="settings__hint" role="alert">
          Last source error: {status.last_error.message}. Existing overlay data was not replaced.
        </p>
      )}
      {status.active_generation?.using_previous_generation && (
        <p className="settings__hint" role="alert">
          The newest overlay generation failed local verification. Golavo is displaying the previous
          verified OpenLigaDB generation instead; CC0 data and forecasts remain unaffected.
        </p>
      )}

      <div className="settings__row">
        <span>Source health</span>
        <span className="small dim" style={{ textAlign: "right" }}>
          {status.health} · checked {when(status.last_checked_at_utc)} · activated {when(status.last_activated_at_utc)}
          {status.storage_bytes > 0 ? ` · ${formatBytes(status.storage_bytes)} local` : " · no local data"}
        </span>
      </div>
      {status.capabilities.map((capability) => (
        <div className="settings__row" key={capability.shortcut}>
          <span>{COMPETITIONS.find((item) => item.shortcut === capability.shortcut)?.label ?? capability.shortcut}</span>
          <span className="small dim" style={{ textAlign: "right" }}>
            {capability.state === "available"
              ? `${capability.league_name ?? capability.shortcut} · ${capability.group_count ?? 0} groups`
              : capability.reason ?? capability.state}
          </span>
        </div>
      ))}

      {status.enabled && overlay.matches.length > 0 && (
        <div className="stack" style={{ ["--gap" as string]: ".35rem" }}>
          <p className="settings__hint" style={{ margin: 0 }}>
            <b>Community overlay preview</b> — source-local identities, not Golavo fixtures.
          </p>
          {overlay.matches.slice(0, 6).map((match) => (
            <div className="settings__row" key={match.source_match_id}>
              <span>{match.home_team_name} — {match.away_team_name}</span>
              <span className="small dim" style={{ textAlign: "right" }}>
                {match.shortcut} · {new Date(match.kickoff_utc).toLocaleString()}
                {match.is_finished ? ` · ${match.final_home_goals}–${match.final_away_goals}` : " · community fixture"}
              </span>
            </div>
          ))}
        </div>
      )}

      <p className="settings__hint" style={{ margin: 0 }}>
        {status.license.attribution}{" "}
        <a href={status.license.url} target="_blank" rel="noreferrer" onClick={handleExternalLinkClick}>
          License and attribution details
        </a>
      </p>
    </div>
  );
}
