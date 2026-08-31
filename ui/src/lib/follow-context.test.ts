// @vitest-environment jsdom
import { act, createElement, createRef, forwardRef, useImperativeHandle } from "react";
import { createRoot } from "react-dom/client";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  claimFollowNotifications,
  fetchFollowSettings,
  fetchFollows,
  followMatch,
  markFollowEventsRead,
  reconcileFollows,
} from "./api";
import { localNotificationPermission } from "./notifications";
import type { FollowedMatch } from "./contract";
import {
  fetchAllActiveFollows,
  type FollowController,
  useFollowController,
} from "./follow-context";

vi.mock("./api", () => ({
  fetchFollows: vi.fn(),
  claimFollowNotifications: vi.fn(),
  fetchFollowSettings: vi.fn(),
  followMatch: vi.fn(),
  markFollowEventsRead: vi.fn(),
  reconcileFollows: vi.fn(),
  removeFollowHistory: vi.fn(),
  unfollowMatch: vi.fn(),
  updateFollowNotification: vi.fn(),
  updateFollowSettings: vi.fn(),
  HAS_BACKEND: true,
}));

vi.mock("./notifications", () => ({
  localNotificationPermission: vi.fn(),
  requestLocalNotificationPermission: vi.fn(),
  submitFollowNotification: vi.fn(),
}));

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(fetchFollows).mockResolvedValue({
    schema_version: "0.1.0",
    items: [],
    total: 0,
    unread_event_count: 0,
    calendar_exportable_count: 0,
    calendar_omitted_count: 0,
  });
  vi.mocked(fetchFollowSettings).mockResolvedValue({
    schema_version: "0.1.0",
    notifications_opt_in: false,
    notifications_supported: false,
  });
  vi.mocked(localNotificationPermission).mockResolvedValue("unsupported");
  vi.mocked(reconcileFollows).mockResolvedValue({} as never);
  vi.mocked(claimFollowNotifications).mockResolvedValue({ events: [] } as never);
  vi.mocked(followMatch).mockResolvedValue({
    follow_id: "follow-1",
    canonical_match_id: "match-1",
    subscription_state: "active",
  } as never);
});

const ControllerHarness = forwardRef<FollowController, { backendReady: boolean }>(
  function ControllerHarness({ backendReady }, ref) {
    const controller = useFollowController(backendReady);
    useImperativeHandle(ref, () => controller, [controller]);
    return createElement("span", null, controller.error?.message ?? controller.listStatus);
  },
);

describe("fetchAllActiveFollows", () => {
  it("paginates the shared live set and preserves global counters", async () => {
    vi.mocked(fetchFollows)
      .mockResolvedValueOnce({
        schema_version: "0.1.0", total: 201, unread_event_count: 3,
        calendar_exportable_count: 199, calendar_omitted_count: 2,
        items: Array.from({ length: 200 }, (_, index) => ({
          canonical_match_id: `match-${index}`,
        })),
      } as never)
      .mockResolvedValueOnce({
        schema_version: "0.1.0", total: 201, unread_event_count: 3,
        calendar_exportable_count: 199, calendar_omitted_count: 2,
        items: [{ canonical_match_id: "match-200" }],
      } as never);

    const result = await fetchAllActiveFollows();

    expect(fetchFollows).toHaveBeenNthCalledWith(1, "active", 20, 200, 0);
    expect(fetchFollows).toHaveBeenNthCalledWith(2, "active", 20, 200, 200);
    expect(result.items).toHaveLength(201);
    expect(result.unread_event_count).toBe(3);
    expect(result.calendar_exportable_count).toBe(199);
  });

  it("reports mark-read failure and resolves without an unhandled rejection", async () => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
    vi.mocked(markFollowEventsRead).mockRejectedValue(new Error("write failed"));
    const controller = createRef<FollowController>();
    const container = document.createElement("div");
    document.body.appendChild(container);
    const root = createRoot(container);
    await act(async () => root.render(
      createElement(ControllerHarness, { backendReady: false, ref: controller }),
    ));

    await act(async () => controller.current?.markRead(["event-1"]));

    expect(container.textContent).toBe("write failed");
    expect(controller.current?.markingRead).toBe(false);
    expect(controller.current?.markReadError?.message).toBe("write failed");
    act(() => root.unmount());
    container.remove();
  });

  it("fails follow state closed when a successful write cannot be read back", async () => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
    const controller = createRef<FollowController>();
    const container = document.createElement("div");
    document.body.appendChild(container);
    const root = createRoot(container);
    await act(async () => root.render(
      createElement(ControllerHarness, { backendReady: true, ref: controller }),
    ));
    await act(async () => {
      await vi.waitFor(() => expect(controller.current?.listStatus).toBe("ready"));
    });
    vi.mocked(fetchFollows).mockRejectedValueOnce(new Error("read-back failed"));

    await act(async () => controller.current?.follow("match-1"));

    expect(followMatch).toHaveBeenCalledWith("match-1");
    expect(controller.current?.listStatus).toBe("error");
    expect(controller.current?.error?.message).toBe("read-back failed");
    act(() => root.unmount());
    container.remove();
  });

  it("serializes follow writes so overlapping buttons cannot race reloads", async () => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
    const controller = createRef<FollowController>();
    const container = document.createElement("div");
    document.body.appendChild(container);
    const root = createRoot(container);
    await act(async () => root.render(
      createElement(ControllerHarness, { backendReady: true, ref: controller }),
    ));
    await act(async () => {
      await vi.waitFor(() => expect(controller.current?.listStatus).toBe("ready"));
    });
    let releaseWrite: ((value: FollowedMatch) => void) | undefined;
    vi.mocked(followMatch).mockReturnValueOnce(new Promise<FollowedMatch>((resolve) => { releaseWrite = resolve; }));

    let first: Promise<void> | undefined;
    act(() => {
      first = controller.current?.follow("match-1");
      void controller.current?.follow("match-2");
    });
    expect(followMatch).toHaveBeenCalledTimes(1);
    expect(followMatch).toHaveBeenCalledWith("match-1");
    await act(async () => {
      releaseWrite?.({
        follow_id: "follow-1",
        canonical_match_id: "match-1",
        subscription_state: "active",
      } as FollowedMatch);
      await first;
    });

    expect(controller.current?.listStatus).toBe("ready");
    act(() => root.unmount());
    container.remove();
  });
});
