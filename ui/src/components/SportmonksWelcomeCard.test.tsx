// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  SPORTMONKS_WELCOME_DECISION_KEY,
  SportmonksWelcomeCard,
} from "./SportmonksWelcomeCard";
import { configureSportmonks, fetchSportmonksStatus } from "../lib/sportmonks";

vi.mock("../lib/updater", () => ({ IS_DESKTOP_SHELL: true }));
vi.mock("../lib/sportmonks", () => ({
  configureSportmonks: vi.fn(),
  fetchSportmonksStatus: vi.fn(),
  deleteSportmonksCredential: vi.fn(),
  saveSportmonksCredential: vi.fn(),
}));

let container: HTMLDivElement;
let root: Root;

function memoryStorage(): Storage {
  const values = new Map<string, string>();
  return {
    get length() { return values.size; },
    clear: () => values.clear(),
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => { values.set(key, String(value)); },
    removeItem: (key) => { values.delete(key); },
    key: (index) => [...values.keys()][index] ?? null,
  };
}

beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  Object.defineProperty(window, "localStorage", { value: memoryStorage(), configurable: true });
  vi.stubGlobal("localStorage", window.localStorage);
  window.location.hash = "#/";
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  vi.mocked(fetchSportmonksStatus).mockResolvedValue({
    terms_acceptance_version: null,
    provider: { terms_acceptance_version: "sportmonks-terms-reviewed-2026-08-29" },
  } as never);
  vi.mocked(configureSportmonks).mockResolvedValue({} as never);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

async function renderCard() {
  await act(async () => {
    root.render(<SportmonksWelcomeCard eligible onVisibilityChange={vi.fn()} />);
  });
}

describe("SportmonksWelcomeCard", () => {
  it("keeps the current app without enabling or contacting the provider", async () => {
    await renderCard();
    const keep = [...container.querySelectorAll("button")].find(
      (button) => button.textContent === "Keep current setup",
    );
    act(() => keep?.click());

    expect(configureSportmonks).not.toHaveBeenCalled();
    expect(localStorage.getItem(SPORTMONKS_WELCOME_DECISION_KEY)).toBe("local");
    expect(container.innerHTML).toBe("");
  });

  it("records explicit acceptance and routes to credential setup", async () => {
    await renderCard();
    const accept = [...container.querySelectorAll("button")].find(
      (button) => button.textContent === "Accept & set up",
    );
    await act(async () => accept?.click());

    expect(configureSportmonks).toHaveBeenCalledWith({
      enabled: true,
      capabilities: ["external_prediction", "external_odds", "player_lens"],
      accept_terms: true,
    });
    expect(localStorage.getItem(SPORTMONKS_WELCOME_DECISION_KEY)).toBe("setup");
    expect(window.location.hash).toBe("#/settings");
  });
});
