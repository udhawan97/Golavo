import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { beginActivity, endActivity } from "./activity";
import {
  cancelOpenLigaDBJob,
  configureOpenLigaDB,
  deleteOpenLigaDB,
  fetchOpenLigaDBJob,
  fetchOpenLigaDBMatches,
  fetchOpenLigaDBStatus,
  rollbackOpenLigaDB,
  startOpenLigaDBRefresh,
} from "./openligadb";
import type {
  OpenLigaDBJob,
  OpenLigaDBMatch,
  OpenLigaDBRefreshPolicy,
  OpenLigaDBShortcut,
  OpenLigaDBStatus,
} from "./openligadb";

const LAUNCH_DELAY_MS = 8_000;
const PERIODIC_WAKE_MS = 60 * 60 * 1000;

export interface OpenLigaDBController {
  status: OpenLigaDBStatus | null;
  job: OpenLigaDBJob | null;
  matches: OpenLigaDBMatch[];
  error: Error | null;
  reload: () => Promise<void>;
  enable: (accepted: boolean) => Promise<void>;
  disable: () => Promise<void>;
  setPolicy: (policy: OpenLigaDBRefreshPolicy) => Promise<void>;
  setCompetitions: (shortcuts: OpenLigaDBShortcut[]) => Promise<void>;
  refreshNow: () => Promise<void>;
  cancel: () => Promise<void>;
  rollback: () => Promise<void>;
  deleteAll: () => Promise<void>;
}

export const OpenLigaDBContext = createContext<OpenLigaDBController | null>(null);

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export function useOpenLigaDBController(backendReady: boolean): OpenLigaDBController {
  const [status, setStatus] = useState<OpenLigaDBStatus | null>(null);
  const [job, setJob] = useState<OpenLigaDBJob | null>(null);
  const [matches, setMatches] = useState<OpenLigaDBMatch[]>([]);
  const [error, setError] = useState<Error | null>(null);
  const running = useRef<Promise<void> | null>(null);

  const reload = useCallback(async () => {
    if (!backendReady) return;
    const next = await fetchOpenLigaDBStatus();
    setStatus(next);
    if (next.job) setJob(next.job);
    if (next.enabled && next.active_generation) {
      const response = await fetchOpenLigaDBMatches(12);
      setMatches(response.matches);
    } else {
      setMatches([]);
    }
  }, [backendReady]);

  const runRefresh = useCallback(async (trigger: "manual" | "launch" | "periodic") => {
    if (!backendReady || running.current) return running.current ?? Promise.resolve();
    const work = (async () => {
      setError(null);
      beginActivity("openligadb-refresh", "Refreshing the optional OpenLigaDB overlay…");
      try {
        let current = await startOpenLigaDBRefresh(trigger);
        setJob(current);
        const deadline = Date.now() + 20 * 60 * 1000;
        while (current.state === "queued" || current.state === "running") {
          if (Date.now() > deadline) throw new Error("OpenLigaDB refresh did not finish within 20 minutes");
          await delay(1_000);
          current = await fetchOpenLigaDBJob(current.job_id);
          setJob(current);
        }
        if (current.state === "failed") {
          throw new Error(current.error?.message ?? "OpenLigaDB refresh failed");
        }
        await reload();
      } catch (cause) {
        setError(cause instanceof Error ? cause : new Error(String(cause)));
        await reload().catch(() => undefined);
      } finally {
        endActivity("openligadb-refresh");
      }
    })();
    running.current = work;
    try {
      await work;
    } finally {
      running.current = null;
    }
  }, [backendReady, reload]);

  useEffect(() => {
    if (!backendReady) return;
    void reload().catch((cause) => setError(cause instanceof Error ? cause : new Error(String(cause))));
    const poll = window.setInterval(() => void reload().catch(() => undefined), 30_000);
    return () => window.clearInterval(poll);
  }, [backendReady, reload]);

  useEffect(() => {
    if (!backendReady || !status?.enabled || status.refresh_policy !== "while_open") return;
    const launch = window.setTimeout(() => {
      if (document.visibilityState === "visible") void runRefresh("launch");
    }, LAUNCH_DELAY_MS);
    const periodic = window.setInterval(() => {
      if (document.visibilityState === "visible") void runRefresh("periodic");
    }, PERIODIC_WAKE_MS);
    return () => {
      window.clearTimeout(launch);
      window.clearInterval(periodic);
    };
  }, [backendReady, runRefresh, status?.enabled, status?.refresh_policy]);

  const apply = useCallback(async (input: Parameters<typeof configureOpenLigaDB>[0]) => {
    setError(null);
    try {
      setStatus(await configureOpenLigaDB(input));
      await reload();
    } catch (cause) {
      const resolved = cause instanceof Error ? cause : new Error(String(cause));
      setError(resolved);
    }
  }, [reload]);

  const cancel = useCallback(async () => {
    if (!job || (job.state !== "queued" && job.state !== "running")) return;
    setJob(await cancelOpenLigaDBJob(job.job_id));
  }, [job]);

  const rollback = useCallback(async () => {
    setError(null);
    try {
      await rollbackOpenLigaDB();
      await reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause : new Error(String(cause)));
    }
  }, [reload]);

  const deleteAll = useCallback(async () => {
    setError(null);
    try {
      await deleteOpenLigaDB();
      setJob(null);
      setMatches([]);
      await reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause : new Error(String(cause)));
    }
  }, [reload]);

  return {
    status,
    job,
    matches,
    error,
    reload,
    enable: (accepted) => apply({ enabled: true, accept_odbl: accepted }),
    disable: () => apply({ enabled: false }),
    setPolicy: (refresh_policy) => apply({ refresh_policy }),
    setCompetitions: (selected_competitions) => apply({ selected_competitions }),
    refreshNow: () => runRefresh("manual"),
    cancel,
    rollback,
    deleteAll,
  };
}

export function useOpenLigaDB(): OpenLigaDBController {
  const value = useContext(OpenLigaDBContext);
  if (!value) throw new Error("useOpenLigaDB must be used inside OpenLigaDBContext.Provider");
  return value;
}
