/**
 * Ad-hoc background-activity registry.
 *
 * A tiny pub/sub for transient "something is running" states the header activity
 * center should surface — e.g. an on-demand fixtures freshness check. The warm-up
 * and updater states have their own stores; this covers everything else. A caller
 * wraps its async work in beginActivity(id, label) / endActivity(id).
 */
import { useSyncExternalStore } from "react";

export interface Activity {
  id: string;
  label: string;
}

const active = new Map<string, string>();
const listeners = new Set<() => void>();
let snapshot: Activity[] = [];

function recompute(): void {
  snapshot = Array.from(active, ([id, label]) => ({ id, label }));
  for (const l of listeners) l();
}

/** Mark a background activity as running. Idempotent per id. */
export function beginActivity(id: string, label: string): void {
  if (active.get(id) === label) return;
  active.set(id, label);
  recompute();
}

/** Clear a background activity. No-op if it wasn't running. */
export function endActivity(id: string): void {
  if (active.delete(id)) recompute();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function getSnapshot(): Activity[] {
  return snapshot;
}

/** Subscribe to the current set of ad-hoc activities. */
export function useActivities(): Activity[] {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
}
