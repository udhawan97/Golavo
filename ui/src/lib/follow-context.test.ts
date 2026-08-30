// @vitest-environment jsdom
import { act, createElement } from "react";
import { createRoot } from "react-dom/client";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fetchFollows, markFollowEventsRead } from "./api";
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

beforeEach(() => vi.clearAllMocks());

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
    const controller: { current: FollowController | null } = { current: null };
    function Harness() {
      controller.current = useFollowController(false);
      return createElement("span", null, controller.current.error?.message ?? "ready");
    }
    const container = document.createElement("div");
    document.body.appendChild(container);
    const root = createRoot(container);
    await act(async () => root.render(createElement(Harness)));

    await act(async () => controller.current?.markRead(["event-1"]));

    expect(container.textContent).toBe("write failed");
    expect(controller.current?.markingRead).toBe(false);
    expect(controller.current?.markReadError?.message).toBe("write failed");
    act(() => root.unmount());
    container.remove();
  });
});
