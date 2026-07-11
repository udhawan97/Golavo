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
 *  sidecar's ephemeral base URL and per-launch token. Absent in browser dev. */
interface Window {
  __GOLAVO_RUNTIME__?: {
    apiBase?: string;
    token?: string;
  };
}
