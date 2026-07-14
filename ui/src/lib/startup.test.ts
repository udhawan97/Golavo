import { describe, expect, it } from "vitest";
import { backendFailureAction, stageProgress } from "./startup";
import {
  buildLaunchDeck,
  buildWaitDeck,
  APP_GEMS,
  FACTS,
  LAUNCH_NOTES,
  WAIT_WHY,
} from "./waitContent";

describe("stageProgress", () => {
  it("eases upward within a stage, never backward", () => {
    let prev = -1;
    for (let t = 0; t <= 60; t += 2) {
      const p = stageProgress("extracting", t);
      expect(p).toBeGreaterThanOrEqual(prev);
      prev = p;
    }
  });

  it("starts each stage at its floor and stays under its ceiling", () => {
    expect(stageProgress("extracting", 0)).toBe(0);
    expect(stageProgress("extracting", 1e6)).toBeLessThan(71);
    // stage 2 floors above stage 1's ceiling so the boundary is a step forward.
    expect(stageProgress("index", 0)).toBe(72);
    expect(stageProgress("index", 1e6)).toBeLessThan(98);
  });

  it("reports 100 only when done", () => {
    expect(stageProgress("done", 0)).toBe(100);
    expect(stageProgress("index", 1e6)).toBeLessThan(100);
  });

  it("clamps negative time to the stage floor", () => {
    expect(stageProgress("index", -5)).toBe(72);
  });
});

describe("backendFailureAction", () => {
  it("ignores stale failures after the backend is already ready", () => {
    expect(backendFailureAction(true, false)).toBe("ignore");
    expect(backendFailureAction(true, true)).toBe("ignore");
  });

  it("silently retries once before surfacing a real startup failure", () => {
    expect(backendFailureAction(false, false)).toBe("silent-retry");
    expect(backendFailureAction(false, true)).toBe("show");
  });
});

describe("buildWaitDeck", () => {
  it("interleaves the three decks so consecutive cards differ in kind", () => {
    const deck = buildWaitDeck(0);
    expect(deck.length).toBeGreaterThan(0);
    for (let i = 1; i < Math.min(deck.length, 6); i++) {
      expect(deck[i].label).not.toBe(deck[i - 1].label);
    }
  });

  it("covers every entry of every deck", () => {
    const texts = new Set(buildWaitDeck(0).map((c) => c.text));
    for (const item of [...WAIT_WHY, ...APP_GEMS, ...FACTS]) {
      expect(texts.has(item)).toBe(true);
    }
  });

  it("keeps each card to a single, reasonably short sentence", () => {
    for (const card of buildWaitDeck(3)) {
      expect(card.text.length).toBeLessThanOrEqual(200);
      expect(card.text.trim().length).toBeGreaterThan(0);
    }
  });

  it("is deterministic per seed and shifts with the seed", () => {
    expect(buildWaitDeck(0)).toEqual(buildWaitDeck(0));
    expect(buildWaitDeck(0)[0].text).not.toBe(buildWaitDeck(1)[0].text);
  });
});

describe("buildLaunchDeck", () => {
  it("keeps the splash deck compact while mixing football and product context", () => {
    const deck = buildLaunchDeck(2);
    expect(deck).toHaveLength(LAUNCH_NOTES.length);
    expect(deck.some((card) => card.label === "Football fact")).toBe(true);
    expect(deck.some((card) => card.label !== "Football fact")).toBe(true);
    expect(deck.every((card) => card.text.length <= 100)).toBe(true);
  });

  it("rotates deterministically without dropping a note", () => {
    expect(buildLaunchDeck(0)).toEqual(buildLaunchDeck(0));
    expect(buildLaunchDeck(1)[0]).not.toEqual(buildLaunchDeck(0)[0]);
    expect(new Set(buildLaunchDeck(9).map((card) => card.text))).toEqual(
      new Set(LAUNCH_NOTES.map((card) => card.text)),
    );
  });
});
