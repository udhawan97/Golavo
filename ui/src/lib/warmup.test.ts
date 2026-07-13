import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { EngineStatus } from "./api";

// The store reads HAS_BACKEND at module init; force the "has a backend" branch so
// the state machine is exercised, and hand it a controllable status feed. Defined
// via vi.hoisted so it's initialized before the hoisted vi.mock factory runs.
const { queue, fetchEngineStatus } = vi.hoisted(() => {
  const q: unknown[] = [];
  const fn = vi.fn(async () =>
    q.length
      ? q.shift()
      : { index_ready: true, index_state: "ready", index_rows: null, warming_since: null },
  );
  return { queue: q as (EngineStatus | "unsupported" | null)[], fetchEngineStatus: fn };
});
vi.mock("./api", () => ({ HAS_BACKEND: true, fetchEngineStatus }));

import { __peekWarmupForTests, __resetWarmupForTests, startWarmupPolling } from "./warmup";

function status(patch: Partial<EngineStatus>): EngineStatus {
  return { index_ready: false, index_state: "warming", index_rows: 75079, warming_since: null, ...patch };
}

/** Advance fake time to run the next poll AND flush its awaits. */
async function tick(ms = 1000): Promise<void> {
  await vi.advanceTimersByTimeAsync(ms);
}

beforeEach(() => {
  vi.useFakeTimers();
  queue.length = 0;
  fetchEngineStatus.mockClear();
  __resetWarmupForTests();
});

afterEach(() => {
  __resetWarmupForTests();
  vi.useRealTimers();
});

describe("warmup store", () => {
  it("goes warming -> ready and stops polling", async () => {
    queue.push(status({ index_state: "warming" }));
    queue.push(status({ index_state: "warming" }));
    queue.push(status({ index_ready: true, index_state: "ready", index_rows: 42 }));

    startWarmupPolling();
    await tick(0); // first poll (fires immediately)
    expect(__peekWarmupForTests().phase).toBe("warming");
    await tick(1000);
    expect(__peekWarmupForTests().phase).toBe("warming");
    await tick(1000);
    expect(__peekWarmupForTests().phase).toBe("ready");
    expect(__peekWarmupForTests().rows).toBe(42);

    const before = fetchEngineStatus.mock.calls.length;
    await tick(5000);
    expect(fetchEngineStatus.mock.calls.length).toBe(before); // no more polling after ready
  });

  it("treats a 404 as unavailable and stops", async () => {
    queue.push("unsupported");
    startWarmupPolling();
    await tick(0);
    expect(__peekWarmupForTests().phase).toBe("unavailable");
    const before = fetchEngineStatus.mock.calls.length;
    await tick(5000);
    expect(fetchEngineStatus.mock.calls.length).toBe(before);
  });

  it("keeps polling through a network blip (null)", async () => {
    queue.push(null);
    queue.push(status({ index_state: "warming" }));
    queue.push(status({ index_ready: true }));
    startWarmupPolling();
    await tick(0);
    expect(fetchEngineStatus.mock.calls.length).toBe(1);
    await tick(1000);
    await tick(1000);
    expect(__peekWarmupForTests().phase).toBe("ready");
    expect(fetchEngineStatus.mock.calls.length).toBeGreaterThanOrEqual(3);
  });

  it("applies the cold-grace rule: cold beyond the grace count becomes ready", async () => {
    for (let i = 0; i < 6; i++) queue.push(status({ index_state: "cold" }));
    startWarmupPolling();
    await tick(0); // poll 1: cold -> warming
    expect(__peekWarmupForTests().phase).toBe("warming");
    await tick(1000); // 2
    await tick(1000); // 3
    await tick(1000); // 4 -> exceeds grace -> ready
    expect(__peekWarmupForTests().phase).toBe("ready");
    const before = fetchEngineStatus.mock.calls.length;
    await tick(5000);
    expect(fetchEngineStatus.mock.calls.length).toBe(before);
  });

  it("is idempotent — a second start does not double-poll", async () => {
    queue.push(status({ index_state: "warming" }));
    startWarmupPolling();
    startWarmupPolling();
    await tick(0);
    expect(fetchEngineStatus.mock.calls.length).toBe(1);
  });
});
