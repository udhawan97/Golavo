import { useEffect, useState } from "react";
import { HAS_BACKEND, fetchForecastSource, pingHealth } from "./api";
import type { ForecastSource } from "./api";

/** True once the local engine is ready to serve.
 *
 *  The desktop sidecar is a onefile Python bundle that self-extracts on every
 *  launch (~30-40s the first time), so the window opens well before the backend
 *  answers. This gates the app behind a splash until then. Two signals, either
 *  wins: the shell's `backend://ready` event (fast) and a `/health` poll
 *  (fallback for a missed event / source-web mode). Mock mode is ready at once. */
export function useBackendReady(): boolean {
  const [ready, setReady] = useState(() => !HAS_BACKEND);

  useEffect(() => {
    if (!HAS_BACKEND) return;
    let alive = true;
    let timer: number | undefined;
    let unlisten: (() => void) | undefined;
    const markReady = () => {
      if (alive) setReady(true);
    };

    const bridge = typeof window !== "undefined" ? window.__TAURI__ : undefined;
    bridge?.event
      .listen("backend://ready", markReady)
      .then((un) => {
        if (alive) unlisten = un;
        else un();
      })
      .catch(() => {
        /* no bridge (source-web mode) — the poll below covers it */
      });

    const poll = async () => {
      if (!alive) return;
      if (await pingHealth()) {
        markReady();
        return;
      }
      timer = window.setTimeout(poll, 1500);
    };
    void poll();

    return () => {
      alive = false;
      unlisten?.();
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, []);

  return ready;
}

/** The forecast data source once the backend is ready — drives the honest
 *  data-source badge and the first-run "these are samples" banner. Null until
 *  known. Re-resolves whenever `ready` flips true. */
export function useForecastSource(ready: boolean): ForecastSource | null {
  const [source, setSource] = useState<ForecastSource | null>(null);
  useEffect(() => {
    if (!ready) return;
    let alive = true;
    fetchForecastSource().then((s) => {
      if (alive) setSource(s);
    });
    return () => {
      alive = false;
    };
  }, [ready]);
  return source;
}
