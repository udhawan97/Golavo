/**
 * First-launch spotlight tour — engine, definitions, and gating.
 *
 * Design constraints (learned from an adversarial review of the plan):
 *  - DESKTOP ONLY by default: the tour never fires in the web/sample build, so it
 *    can't disrupt the mock-mode Playwright/axe suite or a demo visitor. A test
 *    can opt in with the `golavo-tour-test` flag.
 *  - NEVER FIRE OVER AN ABSENT ANCHOR: a tour only starts once its first step's
 *    target actually exists in the DOM, so a still-warming/empty home can't burn
 *    the once-per-install shot on a broken 1-stop tour. Per step, a missing target
 *    is skipped; if a whole tour has no live targets it simply doesn't start.
 *  - EXISTING USERS ARE SEEDED DONE: anyone with prior-use signals (a dismissed
 *    welcome card, a chosen AI provider) is marked done on upgrade, so an update
 *    never re-runs the newcomer tour.
 *  - ONE TOUR AT A TIME, and it yields to higher-priority surfaces (the update
 *    consent card) via the `eligible` gate the caller passes in.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { IS_DESKTOP_SHELL } from "./updater";

export interface TourStep {
  /** Value of the target's `data-tour` attribute. */
  target: string;
  title: string;
  body: string;
}

export interface TourDef {
  id: "home" | "cockpit";
  steps: TourStep[];
}

export const HOME_TOUR: TourDef = {
  id: "home",
  steps: [
    {
      target: "match-card",
      title: "Open any match",
      body: "Past or upcoming — every match opens a deep analytics read: two deterministic voices, disclosed references, team style, and source-backed facts. No averaging into false certainty.",
    },
    {
      target: "nav-season",
      title: "Your season vs the machines",
      body: "Pick a score on any upcoming match — it locks at kickoff — and compare your points with five deterministic model families here.",
    },
    {
      target: "nav-lab",
      title: "The honesty surface",
      body: "The Model Lab holds the track record and backtests — how the methods have actually done, kept in the open.",
    },
    {
      target: "nav-settings",
      title: "Local AI lives here",
      body: "Turn on an optional local AI read and pick your Fast and Deep models in Settings. Everything runs on your machine.",
    },
  ],
};

export const COCKPIT_TOUR: TourDef = {
  id: "cockpit",
  steps: [
    {
      target: "cockpit-mode",
      title: "Choose your reading depth",
      body: "Casual keeps the essential story concise. Expert reveals full model values, market detail, sources and audit context. Switch anytime — the forecast itself never changes.",
    },
    {
      target: "cockpit-pick",
      title: "Make your call",
      body: "Pick the score you believe. Change it any time before kickoff; at kickoff it locks, and the result decides your points.",
    },
    {
      target: "cockpit-council",
      title: "The model council",
      body: "Two independent model voices forecast the match. The baseline and goal-model variants are disclosed separately, so extra methods never masquerade as extra votes.",
    },
    {
      target: "cockpit-notebook",
      title: "Source-backed facts",
      body: "The Commentator's Notebook lists the concrete facts behind the numbers — each tied to its source, never invented.",
    },
    {
      target: "cockpit-ai",
      title: "An optional AI read",
      body: "If you enable local AI, it explains and connects these numbers — Fast for a quick take, Deep for a fuller synthesis. It can never change a number.",
    },
  ],
};

const DONE_PREFIX = "golavo-tour-";
const SEEDED_KEY = "golavo-tour-seeded";
const TEST_KEY = "golavo-tour-test";
/** localStorage keys that indicate the person has used Golavo before. */
const PRIOR_USE_KEYS = ["golavo-welcome-dismissed", "golavo-ai-provider", "golavo-ai-last-provider"];

function ls(): Storage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function testForced(): boolean {
  return ls()?.getItem(TEST_KEY) === "1";
}

/** The tour may run at all: real desktop app, or a test that opted in. */
export function tourEnabled(): boolean {
  return IS_DESKTOP_SHELL || testForced();
}

export function isTourDone(id: TourDef["id"]): boolean {
  return ls()?.getItem(`${DONE_PREFIX}${id}-done`) === "1";
}

export function markTourDone(id: TourDef["id"]): void {
  ls()?.setItem(`${DONE_PREFIX}${id}-done`, "1");
}

/** One-time migration: if the person has prior-use signals, mark every tour done
 *  so an update never shows a returning user the newcomer tour. Fresh installs
 *  (no signals) stay eligible. Idempotent. */
export function seedExistingUser(): void {
  const store = ls();
  if (!store || store.getItem(SEEDED_KEY) === "1") return;
  const returning = PRIOR_USE_KEYS.some((k) => store.getItem(k) != null);
  if (returning) {
    markTourDone("home");
    markTourDone("cockpit");
  }
  store.setItem(SEEDED_KEY, "1");
}

/** Reset every tour so it can be replayed (from Settings). */
const REPLAY_EVENT = "golavo-tour-replay";
export function replayTours(): void {
  const store = ls();
  if (!store) return;
  store.removeItem(`${DONE_PREFIX}home-done`);
  store.removeItem(`${DONE_PREFIX}cockpit-done`);
  window.dispatchEvent(new Event(REPLAY_EVENT));
}

function targetEl(step: TourStep | undefined): HTMLElement | null {
  if (!step) return null;
  return document.querySelector<HTMLElement>(`[data-tour="${step.target}"]`);
}

export interface TourController {
  /** The active step, or null when the tour isn't showing. */
  step: TourStep | null;
  index: number;
  total: number;
  targetEl: HTMLElement | null;
  next: () => void;
  back: () => void;
  skip: () => void;
}

/**
 * Drive one tour. It activates only when `eligible` is true, the tour is enabled,
 * not already done, and its FIRST live target exists — polled briefly so a
 * just-rendered surface is caught without firing over an empty one. A step whose
 * target has vanished is skipped; if none remain the tour completes cleanly.
 *
 * `eligible` lets the caller sequence priority (e.g. wait out the consent card)
 * and scope the tour to the right route.
 */
export function useTour(def: TourDef, eligible: boolean): TourController {
  const [active, setActive] = useState(false);
  const [index, setIndex] = useState(0);
  const [replayNonce, setReplayNonce] = useState(0);
  const replayed = useRef(false);

  // Re-arm on a replay request from Settings. Bumping `replayNonce` re-runs the
  // activation effect below — its own deps wouldn't otherwise change, since the
  // tour was already inactive.
  useEffect(() => {
    const onReplay = () => {
      replayed.current = true;
      setIndex(0);
      setActive(false);
      setReplayNonce((n) => n + 1);
    };
    window.addEventListener(REPLAY_EVENT, onReplay);
    return () => window.removeEventListener(REPLAY_EVENT, onReplay);
  }, []);

  // Decide whether to activate. Polls for the first live target so a
  // just-mounted surface is caught, but never fires over an absent anchor.
  useEffect(() => {
    if (active) return;
    if (!eligible || !tourEnabled()) return;
    if (isTourDone(def.id) && !replayed.current) return;

    let tries = 0;
    const timer = window.setInterval(() => {
      tries += 1;
      // Activate as soon as ANY step has a live target; start at the first live one.
      const firstLive = def.steps.findIndex((s) => targetEl(s) != null);
      if (firstLive !== -1) {
        window.clearInterval(timer);
        setIndex(firstLive);
        setActive(true);
      } else if (tries > 40) {
        // ~10s of no targets: give up WITHOUT marking done, so a later eligible
        // moment (data finished loading) still gets a chance.
        window.clearInterval(timer);
      }
    }, 250);
    return () => window.clearInterval(timer);
  }, [active, eligible, def, replayNonce]);

  const finish = useCallback(() => {
    setActive(false);
    replayed.current = false;
    markTourDone(def.id);
  }, [def.id]);

  const goToNextLive = useCallback(
    (from: number, dir: 1 | -1) => {
      let i = from;
      while (i >= 0 && i < def.steps.length) {
        if (targetEl(def.steps[i]) != null) {
          setIndex(i);
          return;
        }
        i += dir;
      }
      finish();
    },
    [def.steps, finish],
  );

  const next = useCallback(() => goToNextLive(index + 1, 1), [index, goToNextLive]);
  const back = useCallback(() => goToNextLive(index - 1, -1), [index, goToNextLive]);
  const skip = useCallback(() => finish(), [finish]);

  const step = active ? (def.steps[index] ?? null) : null;
  return {
    step,
    index,
    total: def.steps.length,
    targetEl: targetEl(step ?? undefined),
    next,
    back,
    skip,
  };
}
