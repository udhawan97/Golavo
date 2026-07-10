/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Optional base URL of a local golavo-server. When unset, the UI runs
   *  entirely on bundled mock artifacts. */
  readonly VITE_GOLAVO_API?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
