// @vitest-environment jsdom
import { act, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  type RouteAnnouncement,
  useHashRoute,
  useRouteArrival,
} from "./hooks";

let container: HTMLDivElement;
let root: Root;
let scrollY = 0;
let originalScrollY: PropertyDescriptor | undefined;

function Harness() {
  const [route] = useHashRoute();
  const [announcement, setAnnouncement] = useState<RouteAnnouncement>({ entryKey: "", text: "" });
  useRouteArrival(route, setAnnouncement);
  return (
    <>
      <div role="status"><span key={announcement.entryKey}>{announcement.text}</span></div>
      <button type="button">Keep focus</button>
      <main id="main" tabIndex={-1}>
        {route.path}|{route.arrival}|{route.restoreScrollY}
      </main>
    </>
  );
}

beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  window.history.replaceState(null, "", "/#/");
  scrollY = 0;
  originalScrollY = Object.getOwnPropertyDescriptor(window, "scrollY");
  Object.defineProperty(window, "scrollY", { configurable: true, get: () => scrollY });
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
  if (originalScrollY) Object.defineProperty(window, "scrollY", originalScrollY);
  vi.restoreAllMocks();
});

describe("hash route arrival", () => {
  it("focuses and announces only new entries while preserving history focus and exact scroll", async () => {
    await act(async () => root.render(<Harness />));
    const main = container.querySelector<HTMLElement>("main")!;
    const keepFocus = container.querySelector<HTMLButtonElement>("button")!;
    const focus = vi.spyOn(main, "focus");
    const homeState = window.history.state;

    expect(main.textContent).toBe("/|initial|0");
    expect(document.title).toBe("Matchday · Golavo");
    expect(container.querySelector('[role="status"]')?.textContent).toBe("");

    scrollY = 420;
    await act(async () => {
      window.history.pushState(null, "", "/#/leagues");
      window.dispatchEvent(new HashChangeEvent("hashchange"));
    });

    expect(main.textContent).toBe("/leagues|new|0");
    expect(document.title).toBe("Leagues & Europe · Golavo");
    expect(container.querySelector('[role="status"]')?.textContent).toBe("Leagues & Europe");
    expect(document.activeElement).toBe(main);
    expect(focus).toHaveBeenCalledWith({ preventScroll: true });

    scrollY = 18;
    keepFocus.focus();
    await act(async () => {
      window.history.replaceState(homeState, "", "/#/");
      window.dispatchEvent(new HashChangeEvent("hashchange"));
    });

    expect(main.textContent).toBe("/|history|420");
    expect(document.title).toBe("Matchday · Golavo");
    expect(document.activeElement).toBe(keepFocus);
    expect(focus).toHaveBeenCalledTimes(1);

    await act(async () => {
      window.history.pushState(null, "", "/#/team/england-premier-league/Exact%20Club");
      window.dispatchEvent(new HashChangeEvent("hashchange"));
    });

    expect(document.title).toBe("Exact Club · Team dossier · Golavo");
    expect(container.querySelector('[role="status"]')?.textContent)
      .toBe("Exact Club · Team dossier");
    expect(document.activeElement).toBe(main);
    expect(focus).toHaveBeenCalledTimes(2);
  });
});
