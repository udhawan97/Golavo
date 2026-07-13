/**
 * Shared engine warm-up store.
 *
 * The desktop backend warms in two stages the UI can't see from /health alone:
 * the sidecar answers /health while the (heavy) match index is still loading in
 * the background (~25s more). This one module-level store polls GET
 * /api/v1/status so the splash, the home warming card, and the header activity
 * center all read ONE source of truth from ONE poll.
 *
 * Mock/web mode has no backend to wait for, so the store reports "ready" from the
 * start and polling is a no-op — every warm-up surface simply never appears.
 */
import { useSyncExternalStore } from "react";
import { HAS_BACKEND, fetchEngineStatus } from "./api";

export type WarmupPhase = "unknown" | "warming" | "ready" | "unavailable";

export interface WarmupState {
  phase: WarmupPhase;
  /** Total rows in the index (from meta.json), for honest "seating N matches" copy. */
  rows: number | null;
  /** ISO timestamp the current warm-up began, or null. */
  since: string | null;
}

const POLL_MS = 1000;
/** A hard stop so a wedged sidecar can never poll forever. */
const MAX_POLL_MS = 5 * 60_000;
/** Source-mode uvicorn has no background warm thread, so the index sits "cold"
 *  until something reads it. After this many cold polls we treat it as ready and
 *  let the home fetch warm it (fast, unfrozen) — otherwise the hero would wait
 *  forever for a warm that only our own request can trigger. */
const COLD_GRACE_POLLS = 3;

// Mock mode: ready immediately, nothing to poll.
let state: WarmupState = HAS_BACKEND
  ? { phase: "unknown", rows: null, since: null }
  : { phase: "ready", rows: null, since: null };

const listeners = new Set<() => void>();
let polling = false;
let timer: ReturnType<typeof setTimeout> | undefined;
let startedAt = 0;
let coldPolls = 0;

function emit(next: WarmupState): void {
  // Keep a stable reference when nothing changed so useSyncExternalStore doesn't
  // re-render on every identical poll.
  if (
    next.phase === state.phase &&
    next.rows === state.rows &&
    next.since === state.since
  ) {
    return;
  }
  state = next;
  for (const l of listeners) l();
}

function stop(): void {
  polling = false;
  if (timer !== undefined) {
    clearTimeout(timer);
    timer = undefined;
  }
}

async function poll(): Promise<void> {
  if (!polling) return;
  const result = await fetchEngineStatus();
  if (!polling) return;

  if (result === "unsupported") {
    // Older sidecar without the route — behave exactly as before this feature.
    emit({ phase: "unavailable", rows: null, since: null });
    stop();
    return;
  }
  if (result === null) {
    // Network blip — keep the current phase and try again.
    scheduleNext();
    return;
  }

  if (result.index_ready || result.index_state === "ready") {
    emit({ phase: "ready", rows: result.index_rows, since: result.warming_since });
    stop();
    return;
  }
  if (result.index_state === "error") {
    // The index is genuinely broken; the home's own fetch will surface the honest
    // 503 error state. Stop holding a warming card up.
    emit({ phase: "unavailable", rows: result.index_rows, since: result.warming_since });
    stop();
    return;
  }
  if (result.index_state === "cold") {
    coldPolls += 1;
    if (coldPolls > COLD_GRACE_POLLS) {
      emit({ phase: "ready", rows: result.index_rows, since: result.warming_since });
      stop();
      return;
    }
    // Still in the boot race before the warm thread reaches the load — show it as
    // warming so the user sees motion, not a blank.
    emit({ phase: "warming", rows: result.index_rows, since: result.warming_since });
    scheduleNext();
    return;
  }

  // "warming"
  emit({ phase: "warming", rows: result.index_rows, since: result.warming_since });
  scheduleNext();
}

function scheduleNext(): void {
  if (!polling) return;
  if (Date.now() - startedAt > MAX_POLL_MS) {
    stop();
    return;
  }
  timer = setTimeout(() => void poll(), POLL_MS);
}

/** Begin polling engine status. Idempotent, and a no-op in mock mode or once the
 *  store has already reached a terminal phase. App calls this once the backend's
 *  /health answers. */
export function startWarmupPolling(): void {
  if (!HAS_BACKEND) return;
  if (polling) return;
  if (state.phase === "ready" || state.phase === "unavailable") return;
  polling = true;
  startedAt = Date.now();
  coldPolls = 0;
  void poll();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function getSnapshot(): WarmupState {
  return state;
}

/** Subscribe to the shared warm-up state. Read-only: call startWarmupPolling()
 *  (once, from App) to drive it. */
export function useWarmupStatus(): WarmupState {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
}

/** Test-only: read the current phase without a React render. */
export function __peekWarmupForTests(): WarmupState {
  return state;
}

/** Test-only: reset the module store to its initial (pre-poll) state. */
export function __resetWarmupForTests(): void {
  stop();
  coldPolls = 0;
  startedAt = 0;
  state = HAS_BACKEND
    ? { phase: "unknown", rows: null, since: null }
    : { phase: "ready", rows: null, since: null };
}
