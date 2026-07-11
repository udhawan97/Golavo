/**
 * In-app updates — frontend controller.
 *
 * Talks to the desktop shell's staged Rust commands over the global Tauri
 * bridge (withGlobalTauri; no @tauri-apps/api dependency):
 *
 *   updater_status / updater_check / updater_download / updater_cancel /
 *   updater_install_and_restart / updater_relaunch
 *
 * plus the events `updater://progress` and `updater://state`.
 *
 * Honesty rules mirrored from the backend:
 *   - source/web builds (no __TAURI__) are a graceful no-op: nothing renders;
 *   - auto-checking is CONSENT-FIRST (unset until the user answers the one-time
 *     card) because the app promises "no network unless you opt in";
 *   - "Skip this version" silences the passive pill ONLY — a manual check still
 *     tells the truth about what is available;
 *   - the post-update toast comes from the shell's just-updated record, so it
 *     can never claim a backup that was never taken.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

// ---- shapes shared with desktop/src-tauri/src/updater.rs (camelCase) -------

export interface UpdateInfo {
  version: string;
  notes: string | null;
  date: string | null;
}

export interface UpdateErrorInfo {
  kind:
    | "disabled" | "busy" | "needs_move" | "unreachable" | "rate_limited"
    | "bad_manifest" | "install_failed" | "install_stalled" | "other";
  message: string;
}

export interface JustUpdated {
  from: string;
  to: string;
  atEpoch: number;
  backupTaken: boolean;
}

export interface UpdaterStatus {
  appVersion: string;
  enabled: boolean;
  platform: "macos" | "windows" | "other";
  pendingUpdate: { from: string; to: string; atEpoch: number; backupTaken: boolean } | null;
  justUpdated: JustUpdated | null;
}

interface CheckOutcome {
  available: boolean;
  version: string | null;
  notes: string | null;
  date: string | null;
}

export type UpdaterPhase =
  | { kind: "idle" }
  | { kind: "checking" }
  | { kind: "upToDate" }
  | { kind: "available"; info: UpdateInfo; skipped: boolean }
  | { kind: "downloading"; info: UpdateInfo; downloaded: number; total: number | null }
  | { kind: "ready"; info: UpdateInfo }
  | { kind: "installing"; info: UpdateInfo }
  | { kind: "error"; error: UpdateErrorInfo; info: UpdateInfo | null };

// ---- Tauri bridge (loose-typed; absent in browser/source mode) --------------

function tauri(): Window["__TAURI__"] {
  return typeof window !== "undefined" ? window.__TAURI__ : undefined;
}

export const IS_DESKTOP_SHELL = typeof window !== "undefined" && !!window.__TAURI__;

async function invoke<T>(cmd: string, args?: Record<string, unknown>): Promise<T> {
  const bridge = tauri();
  if (!bridge) throw new Error("not running in the desktop shell");
  return bridge.core.invoke<T>(cmd, args);
}

/** Commands reject with the Rust UpdateError (already shaped) or a string. */
function asUpdateError(raw: unknown): UpdateErrorInfo {
  if (raw && typeof raw === "object" && "kind" in raw && "message" in raw) {
    return raw as UpdateErrorInfo;
  }
  return { kind: "other", message: String(raw) };
}

// ---- persisted preferences ---------------------------------------------------

const AUTOCHECK_KEY = "golavo-updates-autocheck"; // "on" | "off" | unset (=ask)
const SKIP_KEY = "golavo-updates-skip";           // version string
const LAST_CHECK_KEY = "golavo-updates-last-check"; // epoch ms
const TOAST_SEEN_KEY = "golavo-updates-toast-seen"; // "<to>:<atEpoch>"

function readStore(key: string): string | null {
  try { return localStorage.getItem(key); } catch { return null; }
}
function writeStore(key: string, value: string | null): void {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch { /* ignore */ }
}

export type AutoCheckChoice = "on" | "off" | "unset";

const INITIAL_CHECK_DELAY_MS = 20_000;       // shortly after boot, off the critical path
const RECHECK_INTERVAL_MS = 24 * 3600_000;   // once a day while the app stays open
const INSTALL_STALL_MS = 90_000;             // give up waiting on a hung install after 90s

// ---- copy for error kinds (releases link is appended by the sheet) ----------

export const ERROR_TITLES: Record<UpdateErrorInfo["kind"], string> = {
  disabled: "Updates are managed outside the app",
  busy: "Already working on it",
  needs_move: "Move Golavo to Applications first",
  unreachable: "Couldn’t reach GitHub",
  rate_limited: "GitHub is rate-limiting update checks",
  bad_manifest: "Update information looks incomplete",
  install_failed: "The update couldn’t be installed",
  install_stalled: "The update is taking longer than expected",
  other: "Update check failed",
};

export const ERROR_HINTS: Record<UpdateErrorInfo["kind"], string> = {
  disabled: "This build updates via git pull or a fresh download.",
  busy: "An update step is already running — give it a moment.",
  needs_move: "", // the message itself carries the instructions
  unreachable:
    "You may be offline, or a firewall/proxy is blocking github.com. Your data is untouched.",
  rate_limited: "Try again in a little while — nothing is wrong with your install.",
  bad_manifest:
    "A release may be publishing right now — try again in a minute, or use the releases page.",
  install_failed:
    "Nothing was changed — your current version keeps working and your ledger is untouched.",
  install_stalled:
    "Golavo should restart on its own to finish installing. If it doesn’t, restart it manually.",
  other: "You can always update manually from the releases page.",
};

export const RELEASES_URL = "https://github.com/udhawan97/Golavo/releases";

// ---- the controller ----------------------------------------------------------

export interface UpdaterController {
  isDesktop: boolean;
  status: UpdaterStatus | null;
  phase: UpdaterPhase;
  sheetOpen: boolean;
  autoCheck: AutoCheckChoice;
  consentNeeded: boolean;
  lastCheckedAt: number | null;
  /** Update available and not skipped — drives the passive header pill. */
  pillVisible: boolean;
  /** The version the user chose to skip (persisted), or null. Drives Settings. */
  skippedVersion: string | null;
  /** just-updated record not yet toasted this boot (null once acknowledged). */
  freshUpdateToast: JustUpdated | null;

  openSheet: () => void;
  closeSheet: () => void;
  setAutoCheck: (choice: "on" | "off") => void;
  check: (opts?: { manual?: boolean }) => Promise<void>;
  download: () => Promise<void>;
  cancel: () => Promise<void>;
  installAndRestart: () => Promise<void>;
  relaunch: () => Promise<void>;
  skipOffered: () => void;
  unskip: () => void;
  dismissError: () => void;
  ackToast: () => void;
}

/** Mount ONCE (App-level); share via UpdaterContext. */
export function useUpdaterController(): UpdaterController {
  const isDesktop = IS_DESKTOP_SHELL;
  const [status, setStatus] = useState<UpdaterStatus | null>(null);
  const [phase, setPhase] = useState<UpdaterPhase>({ kind: "idle" });
  const [sheetOpen, setSheetOpen] = useState(false);
  const [autoCheck, setAutoCheckState] = useState<AutoCheckChoice>(() => {
    const stored = readStore(AUTOCHECK_KEY);
    return stored === "on" || stored === "off" ? stored : "unset";
  });
  const [skippedVersion, setSkippedVersion] = useState<string | null>(() => readStore(SKIP_KEY));
  const [lastCheckedAt, setLastCheckedAt] = useState<number | null>(() => {
    const raw = readStore(LAST_CHECK_KEY);
    return raw ? Number(raw) : null;
  });
  const [freshUpdateToast, setFreshUpdateToast] = useState<JustUpdated | null>(null);

  // The offered update survives phase transitions (cancel -> available again).
  const offeredRef = useRef<UpdateInfo | null>(null);
  // Mirror of `phase` for reads inside stable callbacks (check guard) without
  // rebinding those callbacks on every phase change.
  const phaseRef = useRef(phase);
  useEffect(() => { phaseRef.current = phase; }, [phase]);

  // -- boot: status + just-updated toast + event subscriptions ----------------
  useEffect(() => {
    if (!isDesktop) return;
    let alive = true;
    const unlistens: Array<() => void> = [];

    invoke<UpdaterStatus>("updater_status").then((s) => {
      if (!alive) return;
      setStatus(s);
      if (s.justUpdated) {
        const stamp = `${s.justUpdated.to}:${s.justUpdated.atEpoch}`;
        if (readStore(TOAST_SEEN_KEY) !== stamp) setFreshUpdateToast(s.justUpdated);
      }
    }).catch(() => { /* status is best-effort; the UI just stays quiet */ });

    const bridge = tauri();
    if (bridge) {
      bridge.event.listen("updater://progress", (e) => {
        if (!alive) return;
        const p = e.payload as { downloaded: number; total: number | null };
        setPhase((prev) =>
          prev.kind === "downloading"
            ? { ...prev, downloaded: p.downloaded, total: p.total }
            : prev,
        );
      }).then((un) => unlistens.push(un));

      bridge.event.listen("updater://state", (e) => {
        if (!alive) return;
        const s = e.payload as { phase: string; error?: UpdateErrorInfo; version?: string };
        // A terminal "ready"/"installing" event may arrive after the JS ref was
        // wiped (webview reload, or a concurrent check that cleared it). The
        // event carries the version, so reconstruct minimal info rather than
        // dropping a fully downloaded, installable update on the floor.
        const info =
          offeredRef.current ??
          (s.version ? { version: s.version, notes: null, date: null } : null);
        if (info) offeredRef.current = info;
        if (s.phase === "ready" && info) setPhase({ kind: "ready", info });
        else if (s.phase === "installing" && info) setPhase({ kind: "installing", info });
        else if (s.phase === "error") {
          setPhase({ kind: "error", error: s.error ?? { kind: "other", message: "Unknown updater error" }, info });
        } else if (s.phase === "idle") {
          // Cancel: recompute skipped from the persisted store so the sheet body
          // stays truthful (never re-offers "Skip" for a version already skipped).
          setPhase(
            info
              ? { kind: "available", info, skipped: readStore(SKIP_KEY) === info.version }
              : { kind: "idle" },
          );
        }
      }).then((un) => unlistens.push(un));
    }

    return () => {
      alive = false;
      for (const un of unlistens) un();
    };
  }, [isDesktop]);

  const enabled = status?.enabled ?? false;

  // -- checking ----------------------------------------------------------------
  const check = useCallback(async (opts?: { manual?: boolean }) => {
    const manual = opts?.manual ?? false;
    if (!isDesktop || !enabled) return;
    // Never clobber a live download / staged / installing update — the Rust
    // engine owns those phases and drives them via events. A background daily
    // check (or an over-eager manual one) landing mid-download would otherwise
    // flip the UI back to "available", strand the progress bar, and let the user
    // trigger a spurious "already working on it" error.
    const active = phaseRef.current.kind;
    if (active === "downloading" || active === "ready" || active === "installing") {
      return;
    }
    if (manual) setPhase({ kind: "checking" });
    try {
      const outcome = await invoke<CheckOutcome>("updater_check");
      const now = Date.now();
      setLastCheckedAt(now);
      writeStore(LAST_CHECK_KEY, String(now));
      if (outcome.available && outcome.version) {
        const info: UpdateInfo = {
          version: outcome.version,
          notes: outcome.notes,
          date: outcome.date,
        };
        offeredRef.current = info;
        const skipped = readStore(SKIP_KEY) === info.version;
        // A silently skipped version still surfaces on a MANUAL check — the
        // sheet says "you skipped this" instead of lying with "up to date".
        setPhase({ kind: "available", info, skipped });
      } else {
        offeredRef.current = null;
        setPhase({ kind: "upToDate" });
      }
    } catch (raw) {
      const error = asUpdateError(raw);
      // Passive checks fail silently (no nagging when a laptop is offline);
      // manual checks explain themselves.
      if (manual) setPhase({ kind: "error", error, info: offeredRef.current });
      else setPhase({ kind: "idle" });
    }
  }, [isDesktop, enabled]);

  // -- auto-check scheduling ----------------------------------------------------
  useEffect(() => {
    if (!isDesktop || !enabled || autoCheck !== "on") return;
    const initial = window.setTimeout(() => void check(), INITIAL_CHECK_DELAY_MS);
    const interval = window.setInterval(() => void check(), RECHECK_INTERVAL_MS);
    return () => { window.clearTimeout(initial); window.clearInterval(interval); };
  }, [isDesktop, enabled, autoCheck, check]);

  // -- installing watchdog ------------------------------------------------------
  // The "installing" sheet is intentionally non-closable — but if the backend
  // hangs after emitting "installing" (a stalled install, or a restart that
  // never comes), the user would be trapped on a frozen sheet with the sidecar
  // already stopped. This surfaces a recoverable state so they can relaunch.
  useEffect(() => {
    if (phase.kind !== "installing") return;
    const timer = window.setTimeout(() => {
      setPhase({
        kind: "error",
        error: {
          kind: "install_stalled",
          message: "The install didn’t finish restarting Golavo on its own.",
        },
        info: offeredRef.current,
      });
    }, INSTALL_STALL_MS);
    return () => window.clearTimeout(timer);
  }, [phase.kind]);

  // -- actions -------------------------------------------------------------------
  const setAutoCheck = useCallback((choice: "on" | "off") => {
    setAutoCheckState(choice);
    writeStore(AUTOCHECK_KEY, choice);
  }, []);

  const download = useCallback(async () => {
    const info = offeredRef.current;
    if (!info) return;
    setPhase({ kind: "downloading", info, downloaded: 0, total: null });
    try {
      await invoke("updater_download");
      // completion arrives via updater://state ("ready" | "error")
    } catch (raw) {
      setPhase({ kind: "error", error: asUpdateError(raw), info });
    }
  }, []);

  const cancel = useCallback(async () => {
    try { await invoke("updater_cancel"); } catch { /* state event resets us anyway */ }
  }, []);

  const installAndRestart = useCallback(async () => {
    const info = offeredRef.current;
    if (info) setPhase({ kind: "installing", info });
    try {
      await invoke("updater_install_and_restart");
      // On success this process is gone (restart / installer exit).
    } catch (raw) {
      setPhase({ kind: "error", error: asUpdateError(raw), info: offeredRef.current });
    }
  }, []);

  const relaunch = useCallback(async () => {
    try { await invoke("updater_relaunch"); } catch { /* nothing sensible left to do */ }
  }, []);

  const skipOffered = useCallback(() => {
    const info = offeredRef.current;
    if (!info) return;
    setSkippedVersion(info.version);
    writeStore(SKIP_KEY, info.version);
    setPhase({ kind: "available", info, skipped: true });
    setSheetOpen(false);
  }, []);

  const unskip = useCallback(() => {
    setSkippedVersion(null);
    writeStore(SKIP_KEY, null);
    setPhase((prev) => (prev.kind === "available" ? { ...prev, skipped: false } : prev));
  }, []);

  const ackToast = useCallback(() => {
    if (freshUpdateToast) {
      writeStore(TOAST_SEEN_KEY, `${freshUpdateToast.to}:${freshUpdateToast.atEpoch}`);
    }
    setFreshUpdateToast(null);
  }, [freshUpdateToast]);

  // Closing an error sheet: if an update is still offered, fall back to
  // "available" (not the error phase) so the passive pill returns and the user
  // isn't forced through Settings to retry a still-valid update.
  const dismissError = useCallback(() => {
    const info = offeredRef.current;
    setPhase(
      info
        ? { kind: "available", info, skipped: readStore(SKIP_KEY) === info.version }
        : { kind: "idle" },
    );
    setSheetOpen(false);
  }, []);

  const openSheet = useCallback(() => setSheetOpen(true), []);
  const closeSheet = useCallback(() => setSheetOpen(false), []);

  // The pill survives the whole offered->staged lifecycle: a user who hid the
  // sheet mid-download or clicked "Later" on a downloaded update still has a
  // visible way back (not just Settings).
  const pillVisible = useMemo(() => {
    if (sheetOpen) return false;
    if (phase.kind === "available") {
      return !phase.skipped && phase.info.version !== skippedVersion;
    }
    return phase.kind === "downloading" || phase.kind === "ready";
  }, [phase, skippedVersion, sheetOpen]);

  const consentNeeded = isDesktop && enabled && autoCheck === "unset";

  return {
    isDesktop,
    status,
    phase,
    sheetOpen,
    autoCheck,
    consentNeeded,
    lastCheckedAt,
    pillVisible,
    skippedVersion,
    freshUpdateToast,
    openSheet,
    closeSheet,
    setAutoCheck,
    check,
    download,
    cancel,
    installAndRestart,
    relaunch,
    skipOffered,
    unskip,
    dismissError,
    ackToast,
  };
}

// ---- small formatting helpers used by the components -------------------------

export function formatBytes(n: number): string {
  if (n >= 1024 * 1024) return `${(n / (1024 * 1024)).toFixed(1)} MB`;
  if (n >= 1024) return `${Math.round(n / 1024)} KB`;
  return `${n} B`;
}

export function formatWhen(epochMs: number): string {
  return new Date(epochMs).toLocaleString(undefined, {
    year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}
