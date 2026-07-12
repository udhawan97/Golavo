import { useCallback, useEffect, useState } from "react";
import { HAS_BACKEND, fetchForecastSource, pingHealth } from "./api";
import type { ForecastSource } from "./api";

/** After this long with no healthy /health, tell the user rather than easing a
 *  progress bar toward 94% forever. Polling continues in the background, so a
 *  slow-but-alive engine still recovers on its own. */
const STALL_AFTER_MS = 30_000;

export interface BackendStatus {
  /** True once the local engine answers (or immediately in mock mode). */
  ready: boolean;
  /** True when startup has taken long enough to warrant an escape hatch. */
  stalled: boolean;
  /** Restart the wait from zero (clears `stalled`, kicks a fresh poll). */
  retry: () => void;
}

/** Readiness of the local engine.
 *
 *  The desktop sidecar is a onefile Python bundle that self-extracts on every
 *  launch (~30-40s the first time), so the window opens well before the backend
 *  answers. This gates the app behind a splash until then. Two signals, either
 *  wins: the shell's `backend://ready` event (fast) and a `/health` poll
 *  (fallback for a missed event / source-web mode). Mock mode is ready at once.
 *  If neither signal arrives within STALL_AFTER_MS, `stalled` flips so the
 *  splash can offer a retry instead of a permanent 94%. */
export function useBackendReady(): BackendStatus {
  const [ready, setReady] = useState(() => !HAS_BACKEND);
  const [stalled, setStalled] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!HAS_BACKEND) return;
    let alive = true;
    let timer: number | undefined;
    let unlisten: (() => void) | undefined;
    const startedAt = performance.now();
    const markReady = () => {
      if (alive) {
        setReady(true);
        setStalled(false);
      }
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
      if (alive && performance.now() - startedAt > STALL_AFTER_MS) setStalled(true);
      timer = window.setTimeout(poll, 1500);
    };
    void poll();

    return () => {
      alive = false;
      unlisten?.();
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [attempt]);

  const retry = useCallback(() => {
    setStalled(false);
    setAttempt((n) => n + 1);
  }, []);

  return { ready, stalled, retry };
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
