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

type Theme = "dark" | "light";
const THEME_KEY = "golavo-theme";

/** Theme is dark by default; the choice persists in localStorage. */
export function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(() => {
    try {
      const stored = localStorage.getItem(THEME_KEY);
      if (stored === "light" || stored === "dark") return stored;
    } catch { /* ignore */ }
    return "dark";
  });
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem(THEME_KEY, theme); } catch { /* ignore */ }
  }, [theme]);
  const toggle = useCallback(() => setTheme((t) => (t === "dark" ? "light" : "dark")), []);
  return [theme, toggle];
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
