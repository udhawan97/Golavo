import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  COCKPIT_TOUR,
  HOME_TOUR,
  isTourDone,
  markTourDone,
  seedExistingUser,
} from "./tour";

// The lib reaches localStorage through `window.localStorage`; this project runs
// vitest in node (no jsdom), so provide a tiny in-memory window + Storage.
function makeStorage(): Storage {
  const map = new Map<string, string>();
  return {
    get length() { return map.size; },
    clear: () => map.clear(),
    getItem: (k: string) => (map.has(k) ? map.get(k)! : null),
    setItem: (k: string, v: string) => void map.set(k, String(v)),
    removeItem: (k: string) => void map.delete(k),
    key: (i: number) => [...map.keys()][i] ?? null,
  };
}

beforeEach(() => {
  vi.stubGlobal("window", { localStorage: makeStorage() });
});
afterEach(() => vi.unstubAllGlobals());

describe("tour definitions", () => {
  it("pins the deliberate home and cockpit step order", () => {
    expect(HOME_TOUR.steps.map((s) => s.target)).toEqual([
      "match-card",
      "nav-season",
      "nav-lab",
      "nav-settings",
    ]);
    expect(COCKPIT_TOUR.steps.map((s) => s.target)).toEqual([
      "cockpit-pick",
      "cockpit-council",
      "cockpit-notebook",
      "cockpit-ai",
    ]);
  });

  it("every step has a title and body", () => {
    for (const def of [HOME_TOUR, COCKPIT_TOUR]) {
      for (const step of def.steps) {
        expect(step.title.length).toBeGreaterThan(0);
        expect(step.body.length).toBeGreaterThan(0);
      }
    }
  });
});

describe("done persistence", () => {
  it("round-trips per tour id, independently", () => {
    expect(isTourDone("home")).toBe(false);
    markTourDone("home");
    expect(isTourDone("home")).toBe(true);
    expect(isTourDone("cockpit")).toBe(false);
  });
});

describe("seedExistingUser", () => {
  it("marks tours done for a returning user (prior-use signal present)", () => {
    window.localStorage.setItem("golavo-welcome-dismissed", "1");
    seedExistingUser();
    expect(isTourDone("home")).toBe(true);
    expect(isTourDone("cockpit")).toBe(true);
  });

  it("leaves a fresh install eligible (no prior-use signal)", () => {
    seedExistingUser();
    expect(isTourDone("home")).toBe(false);
    expect(isTourDone("cockpit")).toBe(false);
  });

  it("is idempotent: does not retroactively seed after later interaction", () => {
    seedExistingUser(); // fresh run sets the seeded flag without marking anything
    window.localStorage.setItem("golavo-ai-provider", "ollama");
    seedExistingUser();
    expect(isTourDone("home")).toBe(false);
  });

  it("treats a chosen AI provider as prior use", () => {
    window.localStorage.setItem("golavo-ai-provider", "ollama");
    seedExistingUser();
    expect(isTourDone("home")).toBe(true);
  });
});
