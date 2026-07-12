/**
 * The "keep fixtures up to date" preference (off by default).
 *
 * Golavo makes no automatic network calls; turning this on is the user's explicit
 * consent for the app to ask the CC0 data source, on launch, whether a new
 * upcoming fixture has appeared (via `checkNewFixtures`). Persisted like the other
 * local preferences (theme, AI provider).
 */
import { useCallback, useState } from "react";

const KEY = "golavo-fixtures-autorefresh";

export function keepFixturesFreshEnabled(): boolean {
  try {
    return localStorage.getItem(KEY) === "on";
  } catch {
    return false;
  }
}

export function useKeepFixturesFresh(): [boolean, (on: boolean) => void] {
  const [enabled, setEnabledState] = useState<boolean>(keepFixturesFreshEnabled);
  const setEnabled = useCallback((next: boolean) => {
    setEnabledState(next);
    try {
      localStorage.setItem(KEY, next ? "on" : "off");
    } catch {
      /* ignore — a private-mode storage failure just means the setting won't persist */
    }
  }, []);
  return [enabled, setEnabled];
}
