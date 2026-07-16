/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Optional base URL of a local golavo-server. When unset, the UI runs
   *  entirely on bundled mock artifacts. */
  readonly VITE_GOLAVO_API?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

/** Injected by the desktop shell (Tauri) before the app scripts run: the
 *  sidecar's ephemeral base URL, per-launch token, and the shell's version.
 *  Absent in browser dev. */
interface Window {
  __GOLAVO_RUNTIME__?: {
    apiBase?: string;
    token?: string;
    appVersion?: string;
    buildSha?: string;
  };
  /** Global Tauri bridge (withGlobalTauri) — desktop shell only. Typed to the
   *  two surfaces the updater uses; absent in browser/source mode. */
  __TAURI__?: {
    core: {
      invoke: <T>(cmd: string, args?: Record<string, unknown>) => Promise<T>;
    };
    event: {
      listen: (
        event: string,
        handler: (e: { payload: unknown }) => void,
      ) => Promise<() => void>;
    };
  };
}
