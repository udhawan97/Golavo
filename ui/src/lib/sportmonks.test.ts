// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("./api", () => ({
  API_BASE: "http://127.0.0.1:9999",
  apiHeaders: () => ({}),
}));

import {
  fetchOutsideSignals,
  resetSportmonksClientState,
  SPORTMONKS_RESET_EVENT,
} from "./sportmonks";

afterEach(() => {
  resetSportmonksClientState();
  vi.unstubAllGlobals();
});

describe("Sportmonks client request cleanup", () => {
  it("aborts every live provider request and announces one state reset", async () => {
    const signals: AbortSignal[] = [];
    vi.stubGlobal("fetch", vi.fn((_url: string, init?: RequestInit) => new Promise<Response>(
      (_resolve, reject) => {
        const signal = init?.signal;
        if (!(signal instanceof AbortSignal)) throw new Error("missing AbortSignal");
        signals.push(signal);
        signal.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")), {
          once: true,
        });
      },
    )));
    let resets = 0;
    window.addEventListener(SPORTMONKS_RESET_EVENT, () => { resets += 1; }, { once: true });

    const first = fetchOutsideSignals("m_first");
    const second = fetchOutsideSignals("m_second");
    expect(signals).toHaveLength(2);
    expect(signals.every((signal) => !signal.aborted)).toBe(true);

    resetSportmonksClientState();

    expect(signals.every((signal) => signal.aborted)).toBe(true);
    expect(resets).toBe(1);
    const settled = await Promise.allSettled([first, second]);
    expect(settled.map((result) => result.status)).toEqual(["rejected", "rejected"]);
  });
});
