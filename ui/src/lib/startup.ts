import { useCallback, useEffect, useRef, useState } from "react";
import { HAS_BACKEND, fetchForecastSource, pingHealth } from "./api";
import type { ForecastSource } from "./api";

/** How long the splash waits before it softens into a calm "still working" note
 *  (never a failure — the shell owns that verdict via `backend://failed`). Wider
 *  on a first launch, where the onefile engine self-extracts and antivirus
 *  rescans the fresh binaries; tighter once the app has started before. */
const REASSURE_FIRST_MS = 120_000;
const REASSURE_RETURNING_MS = 45_000;

/** Safety net: if the shell somehow never reports ready OR failed and /health
 *  never answers, surface a manual retry anyway rather than reassure forever.
 *  Set beyond the shell's own worst-case budget (first wait + one silent retry). */
const BACKSTOP_MS = 6 * 60_000;

/** Per-version flag: a fresh install (or a just-updated binary that re-triggers
 *  extraction/AV cost) is treated as a first launch. Version-stamped so an update
 *  gets first-launch patience once, then tightens. */
function launchFlagKey(): string {
  const version =
    (globalThis as { __GOLAVO_RUNTIME__?: { appVersion?: string } }).__GOLAVO_RUNTIME__
      ?.appVersion ?? "dev";
  return `golavo-launched-ok:${version}`;
}

function isFirstLaunch(): boolean {
  try {
    return localStorage.getItem(launchFlagKey()) !== "1";
  } catch {
    return true; // no storage (private mode): be generous, treat as first.
  }
}

function recordLaunched(): void {
  try {
    localStorage.setItem(launchFlagKey(), "1");
  } catch {
    /* private mode — it just won't persist; harmless */
  }
}

/** The Tauri bridge, if this is the desktop shell (source/web builds return
 *  undefined and every desktop-only path becomes a no-op). */
function bridge(): Window["__TAURI__"] {
  return typeof window !== "undefined" ? window.__TAURI__ : undefined;
}

/** Ask the shell to restart the local engine (fresh generation, same port). A
 *  no-op with no bridge. Never throws to the caller. */
async function invokeRestart(): Promise<void> {
  try {
    await bridge()?.core.invoke("restart_sidecar");
  } catch {
    /* the health poll / next failed event still governs what the user sees */
  }
}

/** The two real, observable startup stages (plus the terminal "done").
 *  - extracting: the onefile sidecar is self-extracting; /health not answering.
 *  - index:      /health answers, but the heavy match index is still loading. */
export type SplashStage = "extracting" | "index" | "done";

/** Per-stage eased progress. Each stage eases toward a ceiling and never claims
 *  completion until the real signal arrives, so the bar is honest within a stage
 *  and honest at the boundary. */
export function stageProgress(stage: SplashStage, secondsInStage: number): number {
  const t = Math.max(0, secondsInStage);
  if (stage === "extracting") return 70 * (1 - Math.exp(-t / 12)); // 0 -> ~70
  if (stage === "index") return 72 + 25 * (1 - Math.exp(-t / 9)); //  72 -> ~97
  return 100;
}

export interface BackendStatus {
  /** True once the local engine answers (or immediately in mock mode). */
  ready: boolean;
  /** True once startup has run long enough to warrant a calm "still working"
   *  note. Cosmetic only — it never means anything is wrong. */
  reassure: boolean;
  /** True only when the SHELL reported the engine failed AND the automatic
   *  single retry has already been spent — i.e. time to offer a manual retry. */
  failed: boolean;
  /** Milliseconds since the current attempt began (for honest elapsed copy). */
  elapsedMs: number;
  /** Manually restart the engine and wait again (clears `failed`). */
  retry: () => void;
}

export type BackendFailureAction = "ignore" | "silent-retry" | "show";

/** Once the app has already reached a healthy backend, stale shell/backstop
 *  failures must not throw the user back to the startup screen. */
export function backendFailureAction(ready: boolean, alreadyAutoRetried: boolean): BackendFailureAction {
  if (ready) return "ignore";
  return alreadyAutoRetried ? "show" : "silent-retry";
}

/** Readiness of the local engine, and the one owner of the launch verdict.
 *
 *  Two ready signals, either wins: the shell's `backend://ready` event and a
 *  `/health` poll (fallback for a missed event / source-web mode). FAILURE is
 *  never guessed from a timer — it comes only from the shell's `backend://failed`
 *  event, so the UI and shell can never contradict each other. The first failure
 *  is absorbed by ONE silent restart; only a second failure surfaces to the user.
 *  A generous backstop covers the (shouldn't-happen) case of total silence. */
export function useBackendReady(): BackendStatus {
  const [ready, setReady] = useState(() => !HAS_BACKEND);
  const [reassure, setReassure] = useState(false);
  const [failed, setFailed] = useState(false);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [attempt, setAttempt] = useState(0);
  const autoRetried = useRef(false);
  const readyRef = useRef(ready);

  useEffect(() => {
    readyRef.current = ready;
  }, [ready]);

  useEffect(() => {
    if (!HAS_BACKEND) return;
    let alive = true;
    let poll: number | undefined;
    let tick: number | undefined;
    const unlisten: Array<() => void> = [];
    const startedAt = performance.now();
    const reassureAfter = isFirstLaunch() ? REASSURE_FIRST_MS : REASSURE_RETURNING_MS;

    const stopTimers = () => {
      if (poll !== undefined) {
        window.clearTimeout(poll);
        poll = undefined;
      }
      if (tick !== undefined) {
        window.clearInterval(tick);
        tick = undefined;
      }
    };

    const markReady = () => {
      if (!alive) return;
      readyRef.current = true;
      recordLaunched();
      setReady(true);
      setReassure(false);
      setFailed(false);
      stopTimers();
    };

    const onFailed = () => {
      if (!alive) return;
      const action = backendFailureAction(readyRef.current, autoRetried.current);
      if (action === "ignore") return;
      if (action === "silent-retry") {
        // Absorb the first failure with one silent restart — most first-launch
        // stumbles (an AV scan, a transient port clash) clear on a second try.
        autoRetried.current = true;
        setReassure(true);
        void invokeRestart();
        return;
      }
      setFailed(true);
    };

    const b = bridge();
    b?.event.listen("backend://ready", markReady).then(
      (un) => (alive ? unlisten.push(un) : un()),
      () => {},
    );
    b?.event.listen("backend://failed", onFailed).then(
      (un) => (alive ? unlisten.push(un) : un()),
      () => {},
    );

    const runPoll = async () => {
      if (!alive) return;
      if (await pingHealth()) {
        markReady();
        return;
      }
      if (readyRef.current) return;
      poll = window.setTimeout(runPoll, 1500);
    };
    void runPoll();

    tick = window.setInterval(() => {
      if (!alive) return;
      const ms = performance.now() - startedAt;
      setElapsedMs(ms);
      if (ms > reassureAfter) setReassure(true);
      // Backstop only — the shell should have emitted failed long before this.
      if (ms > BACKSTOP_MS && !readyRef.current) setFailed(true);
    }, 1000);

    return () => {
      alive = false;
      unlisten.forEach((un) => un());
      stopTimers();
    };
  }, [attempt]);

  const retry = useCallback(() => {
    setFailed(false);
    setReassure(true);
    setElapsedMs(0);
    void invokeRestart();
    // Re-run the effect (fresh listeners + poll + elapsed clock). autoRetried is
    // intentionally left true: a manual attempt that fails again shows `failed`
    // immediately rather than silently restarting once more.
    setAttempt((n) => n + 1);
  }, []);

  return { ready, reassure, failed, elapsedMs, retry };
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
