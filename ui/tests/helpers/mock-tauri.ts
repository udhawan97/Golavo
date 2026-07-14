/**
 * A scriptable fake of the global Tauri bridge (withGlobalTauri) for Playwright.
 *
 * Installed via addInitScript so `window.__TAURI__` exists BEFORE the app
 * bundle evaluates — `IS_DESKTOP_SHELL` in ui/src/lib/updater.ts is computed at
 * module load, so late injection would leave every updater surface hidden.
 *
 * Shapes mirror desktop/src-tauri/src/updater.rs (camelCase serde) and the
 * interfaces in ui/src/lib/updater.ts. Commands the UI never calls reject, so
 * a renamed command on either side fails these tests instead of passing
 * silently. Tests drive download/install progress themselves through
 * `window.__TAURI_MOCK__.emit(...)` — the same event names and payloads the
 * Rust engine emits.
 */
import type { Page } from "@playwright/test";

export interface MockJustUpdated {
  from: string;
  to: string;
  atEpoch: number;
  backupTaken: boolean;
}

export type MockCheckBehavior =
  | { outcome: "available"; version: string; notes?: string | null; date?: string | null }
  | { outcome: "upToDate" }
  | { outcome: "error"; kind: string; message: string };

/** Behaviour of the GitHub-release fallback path (unsigned builds). */
export type MockFallbackCheck =
  | {
      outcome: "available";
      version: string;
      notes?: string | null;
      assetName?: string;
      assetUrl?: string;
      assetSize?: number | null;
    }
  | { outcome: "noAsset"; version: string; notes?: string | null }
  | { outcome: "upToDate"; version: string }
  | { outcome: "error"; kind: string; message: string };

export interface MockFallbackScenario {
  /** What fallback_check resolves/rejects with. Default: available 9.9.9 dmg. */
  check?: MockFallbackCheck;
  /** If set, fallback_open rejects with this. */
  openError?: { kind: string; message: string };
}

export interface MockUpdaterScenario {
  /** Reported by updater_status. Defaults: 0.2.6 / enabled / macos. */
  appVersion?: string;
  enabled?: boolean;
  platform?: "macos" | "windows" | "other";
  justUpdated?: MockJustUpdated | null;
  /** What updater_check resolves/rejects with. Default: upToDate. */
  check?: MockCheckBehavior;
  /** GitHub-release fallback behaviour (only reached when enabled === false). */
  fallback?: MockFallbackScenario;
  /** Seeded before the app scripts run (e.g. golavo-updates-autocheck). */
  localStorage?: Record<string, string>;
}

/** Test-side handle, reachable via page.evaluate(). */
export interface MockTauriHandle {
  /** Dispatch an event to the app exactly as the Rust engine would. */
  emit: (event: string, payload: unknown) => void;
  /** Every command name the app invoked, in order. */
  invoked: string[];
  /** Resolve the pending fallback_download promise (the Rust command returns a
   *  path on success). No-op if nothing is downloading. */
  resolveDownload: (path: string) => void;
}

declare global {
  interface Window {
    __TAURI_MOCK__: MockTauriHandle;
  }
}

export async function installMockTauri(
  page: Page,
  scenario: MockUpdaterScenario = {},
): Promise<void> {
  await page.addInitScript((sc: MockUpdaterScenario) => {
    for (const [key, value] of Object.entries(sc.localStorage ?? {})) {
      window.localStorage.setItem(key, value);
    }

    const listeners = new Map<string, Set<(e: { payload: unknown }) => void>>();
    const invoked: string[] = [];

    const emit = (event: string, payload: unknown) => {
      for (const handler of listeners.get(event) ?? []) handler({ payload });
    };

    const status = {
      appVersion: sc.appVersion ?? "0.2.6",
      enabled: sc.enabled ?? true,
      platform: sc.platform ?? "macos",
      pendingUpdate: null,
      justUpdated: sc.justUpdated ?? null,
    };
    const check: MockCheckBehavior = sc.check ?? { outcome: "upToDate" };

    const RELEASES = "https://github.com/udhawan97/Golavo/releases";
    const DOWNLOAD_PREFIX = "https://github.com/udhawan97/Golavo/releases/download/";
    // The fallback download command doesn't resolve until the test says so, so
    // the "downloading" UI (and cancel) can be exercised — mirroring the real
    // command that only returns once the stream finishes.
    let pendingDownload: { resolve: (p: string) => void; reject: (e: unknown) => void } | null =
      null;

    window.__TAURI_MOCK__ = {
      emit,
      invoked,
      resolveDownload: (path: string) => {
        if (pendingDownload) {
          pendingDownload.resolve(path);
          pendingDownload = null;
        }
      },
    };
    window.__TAURI__ = {
      core: {
        invoke: <T>(cmd: string): Promise<T> => {
          invoked.push(cmd);
          switch (cmd) {
            case "updater_status":
              return Promise.resolve(status as T);
            case "updater_check":
              if (!status.enabled) {
                return Promise.reject({
                  kind: "disabled",
                  message: "this build was produced without the updater",
                });
              }
              if (check.outcome === "error") {
                return Promise.reject({ kind: check.kind, message: check.message });
              }
              if (check.outcome === "available") {
                return Promise.resolve({
                  available: true,
                  version: check.version,
                  notes: check.notes ?? null,
                  date: check.date ?? null,
                } as T);
              }
              return Promise.resolve(
                { available: false, version: null, notes: null, date: null } as T,
              );
            case "updater_download":
              // Completion arrives via updater://progress + updater://state,
              // emitted by the test — mirroring the real background task.
              return Promise.resolve(null as T);
            case "updater_cancel":
              // The Rust engine resets to Idle and announces it.
              emit("updater://state", { phase: "idle" });
              return Promise.resolve(null as T);
            case "updater_install_and_restart":
              // Real install never resolves into a running UI (the process
              // restarts); emitting "installing" matches the engine's last word.
              emit("updater://state", { phase: "installing" });
              return Promise.resolve(null as T);
            case "updater_relaunch":
              return Promise.resolve(null as T);

            // -- GitHub-release fallback (unsigned builds) --------------------
            case "fallback_check": {
              const fb = sc.fallback?.check ?? { outcome: "available", version: "9.9.9" };
              if (fb.outcome === "error") {
                return Promise.reject({ kind: fb.kind, message: fb.message });
              }
              if (fb.outcome === "upToDate") {
                return Promise.resolve({
                  version: fb.version,
                  available: false,
                  notes: null,
                  assetName: null,
                  assetUrl: null,
                  assetSize: null,
                  releasesUrl: RELEASES,
                } as T);
              }
              if (fb.outcome === "noAsset") {
                return Promise.resolve({
                  version: fb.version,
                  available: true,
                  notes: fb.notes ?? null,
                  assetName: null,
                  assetUrl: null,
                  assetSize: null,
                  releasesUrl: RELEASES,
                } as T);
              }
              return Promise.resolve({
                version: fb.version,
                available: true,
                notes: fb.notes ?? null,
                assetName: fb.assetName ?? `Golavo_${fb.version}_aarch64.dmg`,
                assetUrl:
                  fb.assetUrl ??
                  `${DOWNLOAD_PREFIX}v${fb.version}/Golavo_${fb.version}_aarch64.dmg`,
                assetSize: fb.assetSize ?? 100 * 1024 * 1024,
                releasesUrl: RELEASES,
              } as T);
            }
            case "fallback_download":
              // Held open until the test resolves it (or fallback_cancel rejects).
              return new Promise<T>((resolve, reject) => {
                pendingDownload = {
                  resolve: (p: string) => resolve(p as T),
                  reject,
                };
              });
            case "fallback_cancel":
              if (pendingDownload) {
                pendingDownload.reject({ kind: "cancelled", message: "Download cancelled." });
                pendingDownload = null;
              }
              return Promise.resolve(null as T);
            case "fallback_open":
              if (sc.fallback?.openError) return Promise.reject(sc.fallback.openError);
              return Promise.resolve(null as T);

            case "plugin:opener|open_url":
              return Promise.resolve(null as T);

            default:
              return Promise.reject(new Error(`mock-tauri: unknown command ${cmd}`));
          }
        },
      },
      event: {
        listen: (event: string, handler: (e: { payload: unknown }) => void) => {
          let set = listeners.get(event);
          if (!set) {
            set = new Set();
            listeners.set(event, set);
          }
          set.add(handler);
          return Promise.resolve(() => {
            set.delete(handler);
          });
        },
      },
    };
  }, scenario);
}
