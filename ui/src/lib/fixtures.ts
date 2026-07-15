/** Versioned consent policy for approved-source network access. */
import { useCallback, useEffect, useState } from "react";

export type DataRefreshPolicy = "off" | "check_only" | "auto_refresh";

const KEY = "golavo-data-refresh-policy-v2";
const LEGACY_KEY = "golavo-fixtures-autorefresh";
export const DATA_REFRESH_POLICY_EVENT = "golavo-data-refresh-policy-changed";

function valid(value: string | null): value is DataRefreshPolicy {
  return value === "off" || value === "check_only" || value === "auto_refresh";
}

export function dataRefreshPolicy(): DataRefreshPolicy {
  try {
    const current = localStorage.getItem(KEY);
    if (valid(current)) return current;
    // The old toggle consented to awareness/result checks, not automatic pack
    // downloads and activation. Preserve it as the narrower check-only state.
    const migrated: DataRefreshPolicy =
      localStorage.getItem(LEGACY_KEY) === "on" ? "check_only" : "off";
    localStorage.setItem(KEY, migrated);
    localStorage.removeItem(LEGACY_KEY);
    return migrated;
  } catch {
    return "off";
  }
}

export function setDataRefreshPolicy(policy: DataRefreshPolicy): void {
  try {
    localStorage.setItem(KEY, policy);
  } catch {
    /* private-mode storage failure leaves the safe default on the next launch */
  }
  window.dispatchEvent(new CustomEvent(DATA_REFRESH_POLICY_EVENT, { detail: policy }));
}

export function useDataRefreshPolicy(): [DataRefreshPolicy, (policy: DataRefreshPolicy) => void] {
  const [policy, setPolicyState] = useState<DataRefreshPolicy>(dataRefreshPolicy);
  useEffect(() => {
    const update = () => setPolicyState(dataRefreshPolicy());
    window.addEventListener(DATA_REFRESH_POLICY_EVENT, update);
    window.addEventListener("storage", update);
    return () => {
      window.removeEventListener(DATA_REFRESH_POLICY_EVENT, update);
      window.removeEventListener("storage", update);
    };
  }, []);
  const setPolicy = useCallback((next: DataRefreshPolicy) => {
    setDataRefreshPolicy(next);
    setPolicyState(next);
  }, []);
  return [policy, setPolicy];
}

// Compatibility for code outside the refresh controller during the migration.
export function keepFixturesFreshEnabled(): boolean {
  return dataRefreshPolicy() !== "off";
}

export function useKeepFixturesFresh(): [boolean, (on: boolean) => void] {
  const [policy, setPolicy] = useDataRefreshPolicy();
  return [policy !== "off", (on) => setPolicy(on ? "check_only" : "off")];
}
