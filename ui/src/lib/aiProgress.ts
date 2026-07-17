/**
 * Live progress for an in-flight AI read.
 *
 * The narrative POST carries a client-generated job id; while it's in flight the
 * sidecar records coarse stage progress against it, and this module polls
 * `GET /ai/jobs/{id}` to drive a live pipeline. It degrades gracefully: an old
 * sidecar (404 the moment we ask) latches to "unsupported" and the pipeline falls
 * back to its honest simulated stages; a transient error keeps the last live
 * state and keeps polling.
 */
import { useEffect, useRef, useState } from "react";
import { API_BASE, apiHeaders } from "./api";

export type AiProgressStage =
  | "assembling_evidence" | "researching" | "writing" | "verifying" | "done";

export interface AiProgress {
  state: "running" | "done" | "failed" | "cancelled";
  stage: AiProgressStage;
  detail: string | null;
  counts: { fetched?: number; planned?: number; tokens?: number } | null;
  elapsed_s: number;
}

/** A job id the sidecar accepts (`^[A-Za-z0-9][A-Za-z0-9_-]{7,63}$`). */
/** A fresh job id in one lane's own id space.
 *
 *  The prefix is the lane, and the server checks it: a retrospective's cancel
 *  door will not stop an AI read, and vice versa. Callers name their lane rather
 *  than minting an AI id and rewriting its prefix. */
export function newJobId(prefix: JobLanePrefix = "cl"): string {
  const uuid =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now().toString(36)}-${Math.floor(Math.random() * 1e9).toString(36)}`;
  return `${prefix}-${uuid}`.slice(0, 60);
}

/** The lanes the sidecar tracks work in (golavo_server/jobs.py). */
export type JobLanePrefix = "cl" | "rt" | "dl";

export type ProgressResult =
  | { kind: "progress"; progress: AiProgress }
  | { kind: "unsupported" }
  | { kind: "error" };

export async function fetchJobProgress(jobId: string, signal?: AbortSignal): Promise<ProgressResult> {
  if (!API_BASE) return { kind: "unsupported" };
  try {
    const res = await fetch(`${API_BASE}/api/v1/ai/jobs/${encodeURIComponent(jobId)}`, {
      headers: apiHeaders(),
      signal,
    });
    if (res.status === 404 || res.status === 400) return { kind: "unsupported" };
    if (!res.ok) return { kind: "error" };
    return { kind: "progress", progress: (await res.json()) as AiProgress };
  } catch {
    return { kind: "error" };
  }
}

export type ProgressState =
  | { kind: "unsupported" }
  | { kind: "waiting" }
  | { kind: "live"; progress: AiProgress };

/** Pure reducer (unit-tested): fold one poll result into the current state.
 *  Once "unsupported", stay there for the run; a transient error keeps the last
 *  live state; a live sample replaces it. */
export function nextProgressState(prev: ProgressState, result: ProgressResult): ProgressState {
  if (prev.kind === "unsupported") return prev;
  if (result.kind === "unsupported") return { kind: "unsupported" };
  if (result.kind === "error") return prev;
  return { kind: "live", progress: result.progress };
}

/** Poll a job's progress while `active`. setTimeout chain (never overlapping),
 *  AbortController per request, both torn down on unmount / job change. */
export function usePolledProgress(
  jobId: string | null,
  active: boolean,
  intervalMs = 1200,
): ProgressState {
  const [state, setState] = useState<ProgressState>({ kind: "waiting" });
  const stateRef = useRef<ProgressState>(state);
  stateRef.current = state;

  useEffect(() => {
    if (!active || !jobId) {
      setState({ kind: "waiting" });
      return;
    }
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let controller: AbortController | undefined;

    const tick = async () => {
      controller = new AbortController();
      const result = await fetchJobProgress(jobId, controller.signal);
      if (cancelled) return;
      const next = nextProgressState(stateRef.current, result);
      stateRef.current = next;
      setState(next);
      const done =
        next.kind === "unsupported" ||
        (next.kind === "live" && next.progress.state !== "running");
      if (!done) timer = setTimeout(tick, intervalMs);
    };
    tick();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
      controller?.abort();
    };
  }, [jobId, active, intervalMs]);

  return state;
}
