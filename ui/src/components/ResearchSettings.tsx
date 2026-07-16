import { useEffect, useState } from "react";
import {
  clearResearchHistory,
  fetchResearchSettings,
  saveResearchSettings,
} from "../lib/research";
import type { ResearchSettings } from "../lib/research";

export function ResearchSettingsPanel() {
  const [settings, setSettings] = useState<ResearchSettings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    fetchResearchSettings().then(
      (value) => { if (live) setSettings(value); },
      () => { if (live) setSettings(null); },
    );
    return () => { live = false; };
  }, []);

  if (!settings) {
    return <p className="settings__hint">Match research is unavailable without the private desktop engine.</p>;
  }

  const update = async (next: ResearchSettings) => {
    setSaving(true);
    setError(null);
    setNotice(null);
    try { setSettings(await saveResearchSettings(next)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Research settings could not be saved."); }
    finally { setSaving(false); }
  };

  return (
    <div className="settings__field">
      <div className="settings__row">
        <label htmlFor="match-research">Match research</label>
        <input
          id="match-research"
          type="checkbox"
          checked={settings.enabled}
          disabled={saving}
          onChange={(event) => void update({ ...settings, enabled: event.target.checked })}
        />
      </div>
      <p className="settings__hint">
        Off by default. Enabling this setting makes no network request. Each run shows a preflight
        and waits for you to select its Wikipedia or Wikidata pages. Captured text is untrusted,
        locally stored evidence; it never changes a forecast or authoritative match value.
      </p>
      <div className="settings__row">
        <label htmlFor="research-retention">Unqueued history retention</label>
        <select
          id="research-retention"
          className="select"
          value={settings.retention_days}
          disabled={saving}
          onChange={(event) => void update({ ...settings, retention_days: Number(event.target.value) })}
        >
          <option value={7}>7 days</option>
          <option value={30}>30 days</option>
          <option value={90}>90 days</option>
        </select>
      </div>
      <p className="settings__hint">
        Expired unqueued runs are removed before the next research run. Evidence already added to
        a correction draft is retained with that draft.
      </p>
      <button
        type="button"
        className="btn btn--quiet"
        onClick={() => {
          if (!window.confirm("Remove local research history? Correction proposals are kept separately.")) return;
          setSaving(true);
          clearResearchHistory().then(
            () => {
              setError(null);
              setNotice("Local research history removed. Match research remains enabled until you turn it off.");
            },
            (reason) => setError(reason instanceof Error ? reason.message : "History could not be removed."),
          ).finally(() => setSaving(false));
        }}
        disabled={saving}
      >
        Clear research history
      </button>
      {notice && <p role="status" className="small dim">{notice}</p>}
      {error && <p role="alert" className="small dim">{error}</p>}
    </div>
  );
}
