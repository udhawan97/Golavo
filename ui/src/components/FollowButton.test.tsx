// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { FollowButton } from "./FollowButton";

const { useFollowsMock } = vi.hoisted(() => ({ useFollowsMock: vi.fn() }));

vi.mock("../lib/follow-context", () => ({ useFollows: useFollowsMock }));

function controller(patch: Record<string, unknown> = {}) {
  return {
    supported: true,
    loading: false,
    error: null,
    changingMatchId: null,
    byMatchId: new Map(),
    follow: vi.fn(),
    unfollow: vi.fn(),
    ...patch,
  };
}

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
  vi.clearAllMocks();
});

describe("FollowButton", () => {
  it("does not present an unresolved follow as available", () => {
    useFollowsMock.mockReturnValue(controller({ loading: true }));

    act(() => root.render(<FollowButton matchId="m1" />));

    const button = container.querySelector("button");
    expect(button?.disabled).toBe(true);
    expect(button?.getAttribute("aria-label")).toBe("Checking follow state");
    expect(button?.textContent).toContain("Checking follow…");
  });

  it("disables the action when follow state could not be loaded", () => {
    useFollowsMock.mockReturnValue(controller({ error: new Error("offline") }));

    act(() => root.render(<FollowButton matchId="m1" />));

    const button = container.querySelector("button");
    expect(button?.disabled).toBe(true);
    expect(button?.getAttribute("aria-label")).toBe("Follow state unavailable");
    expect(button?.textContent).toContain("Follow unavailable");
  });
});
