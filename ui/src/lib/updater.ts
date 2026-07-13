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
    | "bad_manifest" | "install_failed" | "install_stalled" | "cancelled" | "other";
  message: string;
}

// ---- GitHub-release FALLBACK updater (unsigned/dev builds) -------------------
// Mirrors desktop/src-tauri/src/fallback_update.rs. This path works in EVERY
// build; the UI shows it only when the signed updater is unavailable.

export interface FallbackRelease {
  version: string;
  available: boolean;
  notes: string | null;
  assetName: string | null;
  assetUrl: string | null;
  assetSize: number | null;
  releasesUrl: string;
}

export type FallbackPhase =
  | { kind: "idle" }
  | { kind: "checking" }
  | { kind: "upToDate"; version: string }
  | { kind: "available"; rel: FallbackRelease }
  | { kind: "downloading"; rel: FallbackRelease; downloaded: number; total: number | null }
  // `openError` lets a failed "Open installer" keep the downloaded file (and the
  // Open button) instead of throwing the whole download away.
  | { kind: "ready"; rel: FallbackRelease; path: string; openError?: UpdateErrorInfo }
  // `retry` records WHICH action failed so "Try again" repeats that exact action
  // (a failed re-check re-checks; a failed download re-downloads) rather than
  // guessing from whatever rel happens to be remembered.
  | { kind: "error"; error: UpdateErrorInfo; rel: FallbackRelease | null; retry: "check" | "download" };

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
  cancelled: "Download cancelled", // handled inline; never surfaced as an error
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
  cancelled: "",
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

  // -- GitHub-release fallback (only meaningful when !status.enabled) ----------
  fallbackPhase: FallbackPhase;
  fallbackCheck: () => Promise<void>;
  fallbackDownload: () => Promise<void>;
  fallbackCancel: () => Promise<void>;
  fallbackOpen: () => Promise<void>;
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
    const n = raw ? Number(raw) : NaN;
    // Guard the one unvalidated persisted read: a corrupt value must not render
    // "Last checked Invalid Date".
    return Number.isFinite(n) ? n : null;
  });
  const [freshUpdateToast, setFreshUpdateToast] = useState<JustUpdated | null>(null);

  // Fallback (GitHub-release) updater state — independent of the signed path.
  const [fallbackPhase, setFallbackPhase] = useState<FallbackPhase>({ kind: "idle" });
  const fallbackRelRef = useRef<FallbackRelease | null>(null);
  const fallbackPhaseRef = useRef(fallbackPhase);
  useEffect(() => { fallbackPhaseRef.current = fallbackPhase; }, [fallbackPhase]);

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

    const refreshStatus = () => {
      invoke<UpdaterStatus>("updater_status").then((s) => {
        if (!alive) return;
        setStatus(s);
        if (s.justUpdated) {
          const stamp = `${s.justUpdated.to}:${s.justUpdated.atEpoch}`;
          if (readStore(TOAST_SEEN_KEY) !== stamp) setFreshUpdateToast(s.justUpdated);
        }
      }).catch(() => { /* status is best-effort; the UI just stays quiet */ });
    };
    refreshStatus();

    const bridge = tauri();
    if (bridge) {
      // finalize_update_if_pending now runs on the shell's background health
      // thread (after the ~30-40s sidecar warm-up), so the just-updated record
      // may not exist at first mount. Re-read status once the backend signals
      // ready, otherwise the one-time "Updated to X" toast is missed.
      bridge.event.listen("backend://ready", () => {
        if (alive) refreshStatus();
      }).then((un) => unlistens.push(un));

      bridge.event.listen("updater://progress", (e) => {
        if (!alive) return;
        const p = e.payload as { downloaded: number; total: number | null };
        setPhase((prev) =>
          prev.kind === "downloading"
            ? { ...prev, downloaded: p.downloaded, total: p.total }
            : prev,
        );
      }).then((un) => unlistens.push(un));

      bridge.event.listen("updater://fallback-progress", (e) => {
        if (!alive) return;
        const p = e.payload as { downloaded: number; total: number | null };
        setFallbackPhase((prev) =>
          prev.kind === "downloading"
            ? { ...prev, downloaded: p.downloaded, total: p.total ?? prev.total }
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
          // A download/install error can arrive while the user hid the sheet
          // mid-download. Re-surface it — a silently vanishing "Downloading…"
          // pill would leave them believing an update is still in flight.
          setSheetOpen(true);
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
      if (manual) {
        setPhase({ kind: "error", error, info: offeredRef.current });
      } else if (phaseRef.current.kind !== "available") {
        // A background check that fails on a transient blip must NOT erase an
        // update already surfaced to the user; only clear a non-offer phase.
        setPhase({ kind: "idle" });
      }
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

  // -- GitHub-release fallback actions -----------------------------------------
  // Used only by unsigned/dev builds. Each is a plain command call; the download
  // reports progress via `updater://fallback-progress` and resolves with a path.
  const fallbackCheck = useCallback(async () => {
    if (!isDesktop) return;
    // Never clobber an in-flight download/ready — mirrors the signed check guard.
    const active = fallbackPhaseRef.current.kind;
    if (active === "checking" || active === "downloading" || active === "ready") return;
    setFallbackPhase({ kind: "checking" });
    try {
      const rel = await invoke<FallbackRelease>("fallback_check");
      fallbackRelRef.current = rel;
      const now = Date.now();
      setLastCheckedAt(now);
      writeStore(LAST_CHECK_KEY, String(now));
      setFallbackPhase(
        rel.available ? { kind: "available", rel } : { kind: "upToDate", version: rel.version },
      );
    } catch (raw) {
      setFallbackPhase({
        kind: "error",
        error: asUpdateError(raw),
        rel: fallbackRelRef.current,
        retry: "check",
      });
    }
  }, [isDesktop]);

  const fallbackDownload = useCallback(async () => {
    const rel = fallbackRelRef.current;
    if (!rel || !rel.assetUrl) return;
    // Guard double-clicks: a second call while downloading would draw a "busy"
    // error over a healthy download and strand its progress events.
    if (fallbackPhaseRef.current.kind === "downloading") return;
    setFallbackPhase({ kind: "downloading", rel, downloaded: 0, total: rel.assetSize });
    try {
      // The backend re-derives the target itself; no URL is passed from the UI.
      const path = await invoke<string>("fallback_download");
      setFallbackPhase({ kind: "ready", rel, path });
    } catch (raw) {
      const error = asUpdateError(raw);
      // Cancel is a user choice, not a failure — return to the offer, never a
      // red error card. "busy" means a download is already running (a stray
      // double-invoke); leave the live phase untouched.
      if (error.kind === "cancelled") setFallbackPhase({ kind: "available", rel });
      else if (error.kind !== "busy")
        setFallbackPhase({ kind: "error", error, rel, retry: "download" });
    }
  }, []);

  const fallbackCancel = useCallback(async () => {
    // The in-flight fallback_download promise rejects with kind:"cancelled",
    // which fallbackDownload's catch turns back into the "available" phase.
    try { await invoke("fallback_cancel"); } catch { /* nothing else to do */ }
  }, []);

  const fallbackOpen = useCallback(async () => {
    const phase = fallbackPhaseRef.current;
    if (phase.kind !== "ready") return;
    try {
      await invoke("fallback_open", { path: phase.path });
    } catch (raw) {
      // Keep the downloaded file and the Open button — a launch failure (e.g. a
      // Gatekeeper prompt dismissed) must not discard a good ~100 MB download.
      setFallbackPhase({ ...phase, openError: asUpdateError(raw) });
    }
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
    fallbackPhase,
    fallbackCheck,
    fallbackDownload,
    fallbackCancel,
    fallbackOpen,
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
