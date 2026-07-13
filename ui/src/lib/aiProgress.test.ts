import { describe, expect, it } from "vitest";
import { nextProgressState } from "./aiProgress";
import type { AiProgress, ProgressState } from "./aiProgress";

const running: AiProgress = {
  state: "running", stage: "writing", detail: "Reading: X — Wikipedia",
  counts: { fetched: 2, planned: 5 }, elapsed_s: 3,
};

describe("nextProgressState", () => {
  it("adopts a live sample", () => {
    const s = nextProgressState({ kind: "waiting" }, { kind: "progress", progress: running });
    expect(s).toEqual({ kind: "live", progress: running });
  });

  it("latches to unsupported and never leaves it", () => {
    const s = nextProgressState({ kind: "waiting" }, { kind: "unsupported" });
    expect(s.kind).toBe("unsupported");
    // A later live sample cannot revive it.
    const s2 = nextProgressState(s, { kind: "progress", progress: running });
    expect(s2.kind).toBe("unsupported");
  });

  it("keeps the last live state on a transient error", () => {
    const prev: ProgressState = { kind: "live", progress: running };
    expect(nextProgressState(prev, { kind: "error" })).toBe(prev);
  });

  it("waits through an error before any live sample", () => {
    expect(nextProgressState({ kind: "waiting" }, { kind: "error" })).toEqual({ kind: "waiting" });
  });
});
