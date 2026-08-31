import { useCallback, useEffect, useRef, useState } from "react";
import { parseTeamDossierPath } from "./team-route";

const ROUTE_ENTRY_KEY = "__golavoRouteEntry";
let routeEntrySequence = 0;

export interface HashRouteState {
  path: string;
  entryKey: string;
  restoreScrollY: number;
  arrival: "initial" | "new" | "history";
}

export interface RouteAnnouncement {
  entryKey: string;
  text: string;
}

function routeEntryKey(): string {
  const state = window.history.state as Record<string, unknown> | null;
  return typeof state?.[ROUTE_ENTRY_KEY] === "string" ? state[ROUTE_ENTRY_KEY] : "";
}

function newRouteEntryKey(): string {
  routeEntrySequence += 1;
  return `golavo-${Date.now().toString(36)}-${routeEntrySequence.toString(36)}`;
}

function markRouteEntry(key: string): void {
  const state = window.history.state;
  const base = typeof state === "object" && state !== null ? state : {};
  window.history.replaceState({ ...base, [ROUTE_ENTRY_KEY]: key }, "");
}

/** Hash router with per-history-entry scroll memory. New links start at the
 *  destination heading; Back/Forward restore the exact entry they revisit. */
export function useHashRoute(): [HashRouteState, (to: string) => void] {
  const read = () => {
    const h = window.location.hash.replace(/^#/, "");
    return h.length ? h : "/";
  };
  const initial = useRef<HashRouteState | null>(null);
  if (initial.current === null) {
    const entryKey = routeEntryKey() || newRouteEntryKey();
    initial.current = {
      path: read(),
      entryKey,
      restoreScrollY: 0,
      arrival: "initial",
    };
  }
  const [route, setRoute] = useState<HashRouteState>(initial.current);
  const current = useRef(route);
  const knownEntries = useRef(new Set([route.entryKey]));
  const scrollByEntry = useRef(new Map<string, number>());

  useEffect(() => {
    markRouteEntry(current.current.entryKey);
    const previousRestoration = window.history.scrollRestoration;
    window.history.scrollRestoration = "manual";
    const onHash = () => {
      scrollByEntry.current.set(current.current.entryKey, window.scrollY);
      const stateKey = routeEntryKey();
      const revisiting = stateKey !== "" && stateKey !== current.current.entryKey && knownEntries.current.has(stateKey);
      const entryKey = revisiting ? stateKey : newRouteEntryKey();
      if (!revisiting) markRouteEntry(entryKey);
      knownEntries.current.add(entryKey);
      const next: HashRouteState = {
        path: read(),
        entryKey,
        restoreScrollY: revisiting ? (scrollByEntry.current.get(entryKey) ?? 0) : 0,
        arrival: revisiting ? "history" : "new",
      };
      current.current = next;
      setRoute(next);
    };
    window.addEventListener("hashchange", onHash);
    return () => {
      scrollByEntry.current.set(current.current.entryKey, window.scrollY);
      window.history.scrollRestoration = previousRestoration;
      window.removeEventListener("hashchange", onHash);
    };
  }, []);
  const navigate = useCallback((to: string) => {
    window.location.hash = to.startsWith("/") ? to : `/${to}`;
  }, []);
  return [route, navigate];
}

/** Stable, user-facing route names for the document title and live arrival
 *  announcement. Dynamic ids remain private; exact team identity is safe and
 *  useful orientation on the dossier route. */
export function routePageTitle(path: string): string {
  if (path === "/" || path === "" || path === "/games") return "Matchday";
  if (path === "/matches") return "Search matches";
  if (path.startsWith("/match/")) return "Match cockpit";
  if (path === "/corrections") return "Corrections queue";
  if (path.startsWith("/corrections/")) return "Correction review";
  if (path.startsWith("/forecast/")) return "Forecast evidence";
  if (path === "/leagues") return "Leagues & Europe";
  if (path.startsWith("/league/")) return "League dossier";
  const teamDossier = parseTeamDossierPath(path);
  if (teamDossier) return `${teamDossier.team} · Team dossier`;
  if (path === "/season") return "My Season";
  if (path === "/teams") return "My Teams";
  if (path === "/transfers") return "Transfer Desk";
  if (path === "/lab") return "Model Lab";
  if (path === "/lab/track-record" || path === "/ledger") return "Prediction ledger";
  if (path === "/lab/backtests" || path === "/eval") return "Backtests";
  if (path === "/lab/methods") return "Model methods";
  if (path === "/lab/forecasts") return "Forecast archive";
  if (path === "/lab/worldcup-2026") return "World Cup 2026 archive";
  if (path === "/lab/ratings") return "Golavo Ratings";
  if (path === "/trust") return "Trust Center";
  if (path === "/settings") return "Settings";
  if (path === "/guide/sealing") return "Sealing guide";
  if (path === "/guide/picks") return "Picks guide";
  return "Page not found";
}

/** Run after a Suspense-backed route resolves. New entries receive an explicit
 *  content focus and live announcement; history entries keep their existing
 *  focus while App restores the exact remembered scroll position. */
export function useRouteArrival(
  route: HashRouteState,
  announce: (value: RouteAnnouncement) => void,
): void {
  useEffect(() => {
    const title = routePageTitle(route.path);
    document.title = `${title} · Golavo`;
    if (route.arrival !== "new") return;
    announce({ entryKey: route.entryKey, text: title });
    document.getElementById("main")?.focus({ preventScroll: true });
  }, [announce, route.arrival, route.entryKey, route.path]);
}

export type AsyncState<T> =
  | { status: "loading" }
  | { status: "error"; error: Error }
  | { status: "ready"; data: T };

/** Runs an async loader, re-running when `deps` change. Guards against setting
 *  state after unmount or after a superseding run. */
export function useAsync<T>(loader: () => Promise<T>, deps: unknown[]): AsyncState<T> {
  const [state, setState] = useState<AsyncState<T>>({ status: "loading" });
  // `deps` is the caller's array, so it cannot be verified statically. The
  // linter reads that as "no dep list" and warns about the setState below.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    let alive = true;
    setState({ status: "loading" });
    loader().then(
      (data) => { if (alive) setState({ status: "ready", data }); },
      (error) => { if (alive) setState({ status: "error", error: error instanceof Error ? error : new Error(String(error)) }); },
    );
    return () => { alive = false; };
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
