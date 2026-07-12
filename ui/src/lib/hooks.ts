import { useCallback, useEffect, useRef, useState } from "react";

/** Hash router. Returns the current path (without the leading '#') and a
 *  navigate helper. Defaults to "/". */
export function useHashRoute(): [string, (to: string) => void] {
  const read = () => {
    const h = window.location.hash.replace(/^#/, "");
    return h.length ? h : "/";
  };
  const [path, setPath] = useState(read);
  useEffect(() => {
    const onHash = () => setPath(read());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  const navigate = useCallback((to: string) => {
    window.location.hash = to.startsWith("/") ? to : `/${to}`;
  }, []);
  return [path, navigate];
}

export type AsyncState<T> =
  | { status: "loading" }
  | { status: "error"; error: Error }
  | { status: "ready"; data: T };

/** Runs an async loader, re-running when `deps` change. Guards against setting
 *  state after unmount or after a superseding run. */
export function useAsync<T>(loader: () => Promise<T>, deps: unknown[]): AsyncState<T> {
  const [state, setState] = useState<AsyncState<T>>({ status: "loading" });
  useEffect(() => {
    let alive = true;
    setState({ status: "loading" });
    loader().then(
      (data) => { if (alive) setState({ status: "ready", data }); },
      (error) => { if (alive) setState({ status: "error", error: error instanceof Error ? error : new Error(String(error)) }); },
    );
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return state;
}

/** Returns `value` delayed by `delayMs`, resetting the timer on every change.
 *  Used to debounce a fast-changing input (e.g. a search box) before it drives
 *  a fetch, so we query on a pause rather than on every keystroke. */
export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = window.setTimeout(() => setDebounced(value), delayMs);
    return () => window.clearTimeout(t);
  }, [value, delayMs]);
  return debounced;
}

export type Theme = "dark" | "light" | "warm";
export type TextSize = "sm" | "md" | "lg" | "xl";
export type Leading = "normal" | "relaxed";
export type Contrast = "normal" | "high";

export interface ReadingPrefs {
  theme: Theme;
  textSize: TextSize;
  leading: Leading;
  contrast: Contrast;
}

const RP_KEY = {
  theme: "golavo-theme",
  textSize: "golavo-text-size",
  leading: "golavo-leading",
  contrast: "golavo-contrast",
} as const;

function readPref<T extends string>(key: string, allowed: readonly T[], fallback: T): T {
  try {
    const v = localStorage.getItem(key);
    if (v && (allowed as readonly string[]).includes(v)) return v as T;
  } catch { /* ignore */ }
  return fallback;
}

function prefersMoreContrast(): boolean {
  try { return window.matchMedia?.("(prefers-contrast: more)").matches ?? false; } catch { return false; }
}

/** Reading-comfort preferences — theme (incl. a warm, low-blue palette), text
 *  size, line spacing, and contrast. They change how the page reads, never a
 *  number. Persisted in localStorage and applied as data-* on <html>; an inline
 *  script in index.html applies them before first paint so nothing flashes.
 *  Theme defaults to dark; contrast defaults on when the OS asks for more. */
export function useReadingPrefs(): [ReadingPrefs, (patch: Partial<ReadingPrefs>) => void] {
  const [prefs, setPrefs] = useState<ReadingPrefs>(() => ({
    theme: readPref(RP_KEY.theme, ["dark", "light", "warm"] as const, "dark"),
    textSize: readPref(RP_KEY.textSize, ["sm", "md", "lg", "xl"] as const, "md"),
    leading: readPref(RP_KEY.leading, ["normal", "relaxed"] as const, "normal"),
    contrast: readPref(RP_KEY.contrast, ["normal", "high"] as const, prefersMoreContrast() ? "high" : "normal"),
  }));
  useEffect(() => {
    const el = document.documentElement;
    el.dataset.theme = prefs.theme;
    el.dataset.textSize = prefs.textSize;
    el.dataset.leading = prefs.leading;
    el.dataset.contrast = prefs.contrast;
    try {
      localStorage.setItem(RP_KEY.theme, prefs.theme);
      localStorage.setItem(RP_KEY.textSize, prefs.textSize);
      localStorage.setItem(RP_KEY.leading, prefs.leading);
      localStorage.setItem(RP_KEY.contrast, prefs.contrast);
    } catch { /* ignore */ }
  }, [prefs]);
  const update = useCallback((patch: Partial<ReadingPrefs>) => setPrefs((p) => ({ ...p, ...patch })), []);
  return [prefs, update];
}

export type ForecastMode = "casual" | "expert";
const MODE_KEY = "golavo-forecast-mode";

/** Casual vs Expert presentation depth over the SAME sealed numbers. Casual by
 *  default; the choice persists in localStorage. The mode only changes how much
 *  detail is shown — never the displayed probabilities. */
export function useForecastMode(): [ForecastMode, (m: ForecastMode) => void] {
  const [mode, setMode] = useState<ForecastMode>(() => {
    try {
      const stored = localStorage.getItem(MODE_KEY);
      if (stored === "casual" || stored === "expert") return stored;
    } catch { /* ignore */ }
    return "casual";
  });
  const set = useCallback((m: ForecastMode) => {
    setMode(m);
    try { localStorage.setItem(MODE_KEY, m); } catch { /* ignore */ }
  }, []);
  return [mode, set];
}

/** Copy-to-clipboard with a transient "copied" flag keyed by an id.
 *  Failed writes deliberately leave the flag unset: the UI must never claim a
 *  value reached the clipboard when the browser rejected it. */
export function useCopy(resetMs = 1400): [string | null, (text: string, id: string) => void] {
  const [copied, setCopied] = useState<string | null>(null);
  const timer = useRef<number | undefined>(undefined);
  const copy = useCallback((text: string, id: string) => {
    const done = () => {
      setCopied(id);
      window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => setCopied(null), resetMs);
    };
    setCopied(null);
    if (!navigator.clipboard?.writeText) return;
    navigator.clipboard.writeText(text).then(done, () => {
      // Clipboard access can be denied by permissions or an insecure context.
      // Keep the neutral copy affordance instead of reporting false success.
      setCopied(null);
    });
  }, [resetMs]);
  useEffect(() => () => window.clearTimeout(timer.current), []);
  return [copied, copy];
}
