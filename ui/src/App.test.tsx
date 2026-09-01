// @vitest-environment jsdom
import { Suspense, useState } from "react";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ResolvedRoute } from "./App";
import type { HashRouteState, RouteAnnouncement } from "./lib/hooks";

function ThrowRoute(): never {
  throw new Error("route render failed");
}

const route: HashRouteState = {
  path: "/settings",
  entryKey: "throwing-settings-entry",
  restoreScrollY: 0,
  arrival: "new",
};

function Harness() {
  const [announcement, setAnnouncement] = useState<RouteAnnouncement>({ entryKey: "", text: "" });
  return (
    <>
      <div role="status"><span key={announcement.entryKey}>{announcement.text}</span></div>
      <main id="main" tabIndex={-1}>
        <Suspense fallback={<p>Loading route…</p>}>
          <ResolvedRoute route={route} announce={setAnnouncement}>
            <ThrowRoute />
          </ResolvedRoute>
        </Suspense>
      </main>
    </>
  );
}

let container: HTMLDivElement;
let root: Root;
let consoleError: ReturnType<typeof vi.spyOn>;

beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  document.title = "Previous route · Golavo";
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
  consoleError.mockRestore();
});

describe("resolved route ownership", () => {
  it("orients the error fallback after a destination route throws", async () => {
    await act(async () => root.render(<Harness />));

    expect(container.querySelector('[role="alert"]')?.textContent)
      .toContain("This view hit a snag");
    expect(document.title).toBe("Settings · Golavo");
    expect(container.querySelector('[role="status"]')?.textContent).toBe("Settings");
    expect(document.activeElement).toBe(container.querySelector("main"));
  });
});
