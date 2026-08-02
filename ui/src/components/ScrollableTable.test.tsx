// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { ScrollableTable } from "./ScrollableTable";

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  Object.defineProperty(window, "innerWidth", { configurable: true, value: 375, writable: true });
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
  Object.defineProperty(window, "innerWidth", { configurable: true, value: 1024, writable: true });
});

describe("ScrollableTable", () => {
  it("shows a cue while columns remain and clears it at the right edge", () => {
    act(() => {
      root.render(
        <ScrollableTable label="Track record" cue="More: sealed date, outcome and scores">
          <table><tbody><tr><td>Fixture</td><td>Log loss</td></tr></tbody></table>
        </ScrollableTable>,
      );
    });
    const scroller = container.querySelector<HTMLDivElement>(".table-wrap")!;
    Object.defineProperties(scroller, {
      clientWidth: { configurable: true, value: 320 },
      scrollWidth: { configurable: true, value: 900 },
      scrollLeft: { configurable: true, value: 0, writable: true },
    });
    act(() => window.dispatchEvent(new Event("resize")));

    const shell = container.querySelector<HTMLElement>(".table-scroll-shell")!;
    expect(shell.dataset.overflow).toBe("true");
    expect(shell.dataset.atEnd).toBe("false");
    expect(scroller.tabIndex).toBe(0);
    expect(container.querySelector(".table-scroll__hint")?.getAttribute("aria-hidden")).toBe("false");
    expect(container.textContent).toContain("More: sealed date, outcome and scores");

    act(() => {
      scroller.scrollLeft = 580;
      scroller.dispatchEvent(new Event("scroll", { bubbles: true }));
    });
    expect(shell.dataset.atEnd).toBe("true");
    expect(container.querySelector(".table-scroll__hint")?.getAttribute("aria-hidden")).toBe("true");

    act(() => {
      Object.defineProperty(window, "innerWidth", { configurable: true, value: 1440, writable: true });
      scroller.scrollLeft = 0;
      window.dispatchEvent(new Event("resize"));
    });
    expect(shell.dataset.compact).toBe("false");
    expect(shell.dataset.atEnd).toBe("false");
    expect(container.querySelector(".table-scroll__hint")?.getAttribute("aria-hidden")).toBe("true");
  });
});
