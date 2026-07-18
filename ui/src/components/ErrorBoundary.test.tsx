// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ErrorBoundary } from "./ErrorBoundary";

// Error boundaries only engage on a client render — `renderToStaticMarkup`,
// which the other component tests use, lets the throw escape instead of
// catching it. Hence jsdom and a real root for this file.

function Boom({ explode }: { explode: boolean }) {
  if (explode) throw new Error("render exploded");
  return <p>all good</p>;
}

let container: HTMLDivElement;
let root: Root;
let consoleError: ReturnType<typeof vi.spyOn>;

beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  // React re-throws caught render errors to the console, and componentDidCatch
  // logs its own line. Silenced so a passing run stays readable.
  consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
  consoleError.mockRestore();
});

describe("ErrorBoundary", () => {
  it("renders its children untouched while nothing throws", () => {
    act(() => {
      root.render(
        <ErrorBoundary>
          <Boom explode={false} />
        </ErrorBoundary>,
      );
    });

    expect(container.textContent).toContain("all good");
    expect(container.querySelector('[role="alert"]')).toBeNull();
  });

  it("catches a render throw and shows the recoverable panel instead of a blank page", () => {
    act(() => {
      root.render(
        <ErrorBoundary>
          <Boom explode={true} />
        </ErrorBoundary>,
      );
    });

    const alert = container.querySelector('[role="alert"]');
    expect(alert).not.toBeNull();
    expect(alert?.textContent).toContain("This view hit a snag");
    // The whole tree surviving is the point — a blank container would mean the
    // boundary unmounted the app rather than degrading to a panel.
    expect(container.textContent).not.toContain("all good");
    expect(container.innerHTML).not.toBe("");
  });

  it("keeps a route back out of the failed view", () => {
    act(() => {
      root.render(
        <ErrorBoundary>
          <Boom explode={true} />
        </ErrorBoundary>,
      );
    });

    expect(container.querySelector('a[href="#/"]')).not.toBeNull();
  });

  it("reports the caught error to the console for the desktop logs", () => {
    act(() => {
      root.render(
        <ErrorBoundary>
          <Boom explode={true} />
        </ErrorBoundary>,
      );
    });

    expect(
      consoleError.mock.calls.some((call) => String(call[0]).includes("Golavo render error:")),
    ).toBe(true);
  });

  it("clears the error when resetKey changes, so navigating away recovers", () => {
    act(() => {
      root.render(
        <ErrorBoundary resetKey="/crashed">
          <Boom explode={true} />
        </ErrorBoundary>,
      );
    });
    expect(container.querySelector('[role="alert"]')).not.toBeNull();

    act(() => {
      root.render(
        <ErrorBoundary resetKey="/somewhere-else">
          <Boom explode={false} />
        </ErrorBoundary>,
      );
    });

    expect(container.querySelector('[role="alert"]')).toBeNull();
    expect(container.textContent).toContain("all good");
  });

  it("stays in the error state while resetKey is unchanged", () => {
    act(() => {
      root.render(
        <ErrorBoundary resetKey="/crashed">
          <Boom explode={true} />
        </ErrorBoundary>,
      );
    });

    // Re-render on the same route with a child that would now succeed. The
    // boundary must not clear on its own: only a resetKey change means the user
    // actually went somewhere else.
    act(() => {
      root.render(
        <ErrorBoundary resetKey="/crashed">
          <Boom explode={false} />
        </ErrorBoundary>,
      );
    });

    expect(container.querySelector('[role="alert"]')).not.toBeNull();
    expect(container.textContent).not.toContain("all good");
  });

  it("recovers from a second, later crash on a new route", () => {
    act(() => {
      root.render(
        <ErrorBoundary resetKey="/first">
          <Boom explode={true} />
        </ErrorBoundary>,
      );
    });
    act(() => {
      root.render(
        <ErrorBoundary resetKey="/second">
          <Boom explode={false} />
        </ErrorBoundary>,
      );
    });
    expect(container.querySelector('[role="alert"]')).toBeNull();

    // A boundary that only reset once would strand the user here.
    act(() => {
      root.render(
        <ErrorBoundary resetKey="/third">
          <Boom explode={true} />
        </ErrorBoundary>,
      );
    });
    expect(container.querySelector('[role="alert"]')).not.toBeNull();

    act(() => {
      root.render(
        <ErrorBoundary resetKey="/fourth">
          <Boom explode={false} />
        </ErrorBoundary>,
      );
    });
    expect(container.querySelector('[role="alert"]')).toBeNull();
    expect(container.textContent).toContain("all good");
  });
});
