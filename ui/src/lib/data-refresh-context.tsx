import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import type { DataRefreshJob, DataRefreshStatus } from "./contract";
import {
  cancelDataRefresh,
  clearApiCache,
  fetchDataRefreshJob,
  fetchDataRefreshStatus,
  fetchFollows,
  rollbackDataRefresh,
  startDataRefresh,
} from "./api";
import { beginActivity, endActivity } from "./activity";
import { useDataRefreshPolicy } from "./fixtures";

export const DATA_GENERATION_CHANGED_EVENT = "golavo-data-generation-changed";
const PERIODIC_WAKE_MS = 30 * 60 * 1000;
const LAUNCH_DELAY_MS = 5_000;

export interface DataRefreshController {
  policy: ReturnType<typeof useDataRefreshPolicy>[0];
  setPolicy: ReturnType<typeof useDataRefreshPolicy>[1];
  status: DataRefreshStatus | null;
  job: DataRefreshJob | null;
  error: Error | null;
  checkNow: () => Promise<void>;
  refreshNow: () => Promise<void>;
  refreshFollowedNow: () => Promise<void>;
  cancel: () => Promise<void>;
  rollback: () => Promise<void>;
  reloadStatus: () => Promise<void>;
}

export const DataRefreshContext = createContext<DataRefreshController | null>(null);

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export function useDataRefreshController(backendReady: boolean): DataRefreshController {
  const [policy, setPolicy] = useDataRefreshPolicy();
  const [status, setStatus] = useState<DataRefreshStatus | null>(null);
  const [job, setJob] = useState<DataRefreshJob | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const running = useRef<Promise<void> | null>(null);

  const reloadStatus = useCallback(async () => {
    if (!backendReady) return;
    const next = await fetchDataRefreshStatus();
    setStatus(next);
    if (next?.job) setJob(next.job);
  }, [backendReady]);

  const run = useCallback(async (
    mode: "check" | "refresh",
    trigger: "manual" | "launch" | "periodic",
    requestedScope?: "all" | "followed",
  ) => {
    if (!backendReady || running.current) return running.current ?? Promise.resolve();
    const work = (async () => {
      setError(null);
      beginActivity("data-refresh", mode === "check" ? "Checking approved data sources…" : "Refreshing approved data…");
      try {
        const scope = requestedScope ?? (
          trigger === "manual"
            ? "all"
            : (await fetchFollows("active", 0)).total > 0 ? "followed" : "all"
        );
        let current = await startDataRefresh(mode, trigger, scope);
        setJob(current);
        const deadline = Date.now() + 20 * 60 * 1000;
        while (current.state === "queued" || current.state === "running") {
          if (Date.now() > deadline) throw new Error("Data refresh did not finish within 20 minutes");
          await delay(1_000);
          current = await fetchDataRefreshJob(current.job_id);
          setJob(current);
        }
        if (current.state === "failed") {
          throw new Error(current.error?.message ?? "Approved-source refresh failed");
        }
        if (current.state === "done" && current.result?.activated === true) {
          clearApiCache();
          window.dispatchEvent(new Event(DATA_GENERATION_CHANGED_EVENT));
        }
        await reloadStatus();
      } catch (cause) {
        setError(cause instanceof Error ? cause : new Error(String(cause)));
        await reloadStatus().catch(() => undefined);
      } finally {
        endActivity("data-refresh");
      }
    })();
    running.current = work;
    try {
      await work;
    } finally {
      running.current = null;
    }
  }, [backendReady, reloadStatus]);

  useEffect(() => {
    if (!backendReady) return;
    void reloadStatus();
    const poll = window.setInterval(() => void reloadStatus(), 30_000);
    return () => window.clearInterval(poll);
  }, [backendReady, reloadStatus]);

  useEffect(() => {
    if (!backendReady || policy === "off") return;
    const mode = policy === "auto_refresh" ? "refresh" : "check";
    let lastWake = Date.now();
    const wake = (trigger: "launch" | "periodic") => {
      if (document.visibilityState !== "visible") return;
      lastWake = Date.now();
      void run(mode, trigger);
    };
    const launch = window.setTimeout(() => {
      wake("launch");
    }, LAUNCH_DELAY_MS);
    const periodic = window.setInterval(() => {
      wake("periodic");
    }, PERIODIC_WAKE_MS);
    const resume = () => {
      if (Date.now() - lastWake >= PERIODIC_WAKE_MS) wake("periodic");
    };
    document.addEventListener("visibilitychange", resume);
    window.addEventListener("focus", resume);
    return () => {
      window.clearTimeout(launch);
      window.clearInterval(periodic);
      document.removeEventListener("visibilitychange", resume);
      window.removeEventListener("focus", resume);
    };
  }, [backendReady, policy, run]);

  const cancel = useCallback(async () => {
    if (!job || (job.state !== "queued" && job.state !== "running")) return;
    setJob(await cancelDataRefresh(job.job_id));
  }, [job]);

  const rollback = useCallback(async () => {
    setError(null);
    try {
      await rollbackDataRefresh();
      window.dispatchEvent(new Event(DATA_GENERATION_CHANGED_EVENT));
      await reloadStatus();
    } catch (cause) {
      setError(cause instanceof Error ? cause : new Error(String(cause)));
    }
  }, [reloadStatus]);

  return {
    policy,
    setPolicy,
    status,
    job,
    error,
    checkNow: () => run("check", "manual"),
    refreshNow: () => run("refresh", "manual"),
    refreshFollowedNow: () => run("refresh", "manual", "followed"),
    cancel,
    rollback,
    reloadStatus,
  };
}

export function useDataRefresh(): DataRefreshController {
  const value = useContext(DataRefreshContext);
  if (!value) throw new Error("useDataRefresh must be used inside DataRefreshContext.Provider");
  return value;
}

export function useDataGenerationRevision(): number {
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const advance = () => setRevision((value) => value + 1);
    window.addEventListener(DATA_GENERATION_CHANGED_EVENT, advance);
    return () => window.removeEventListener(DATA_GENERATION_CHANGED_EVENT, advance);
  }, []);
  return revision;
}
