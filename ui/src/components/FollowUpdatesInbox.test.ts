// @vitest-environment jsdom
import { act, createElement } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it } from "vitest";
import type { FollowedMatch } from "../lib/contract";
import { FollowUpdatesInbox, recentFollowUpdates } from "./FollowUpdatesInbox";
import { FollowContext, type FollowController } from "../lib/follow-context";

function match(id: string, events: Array<{ event_id: string; event_type: string; detected_at_utc: string }>) {
  return {
    canonical_match_id: id,
    events: events.map((event) => ({ ...event, read_at_utc: null })),
  } as unknown as FollowedMatch;
}

describe("recentFollowUpdates", () => {
  it("omits subscription bookkeeping and sorts equal timestamps by event id", () => {
    const result = recentFollowUpdates([
      match("m1", [
        { event_id: "a", event_type: "followed", detected_at_utc: "2026-08-29T10:00:00Z" },
        { event_id: "u", event_type: "unfollowed", detected_at_utc: "2026-08-29T10:30:00Z" },
        { event_id: "r", event_type: "refollowed", detected_at_utc: "2026-08-29T10:45:00Z" },
        { event_id: "b", event_type: "kickoff_changed", detected_at_utc: "2026-08-29T11:00:00Z" },
      ]),
      match("m2", [
        { event_id: "c", event_type: "score_published", detected_at_utc: "2026-08-29T11:00:00Z" },
      ]),
    ]);
    expect(result.map(({ event }) => event.event_id)).toEqual(["c", "b"]);
  });

  it("applies the disclosed recent-item cap", () => {
    const result = recentFollowUpdates([
      match("m1", Array.from({ length: 4 }, (_, index) => ({
        event_id: String(index), event_type: "source_revision_available",
        detected_at_utc: `2026-08-29T1${index}:00:00Z`,
      }))),
    ], 2);
    expect(result).toHaveLength(2);
  });

  it("labels only a mark-read-specific failure as a mark-read error", async () => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
    const followed = match("m1", [{
      event_id: "event-1",
      event_type: "score_published",
      detected_at_utc: "2026-08-29T11:00:00Z",
    }]);
    followed.current = { home_team: "Home", away_team: "Away" } as never;
    followed.events[0].source = { source_id: "test" } as never;
    const base = {
      list: { items: [followed] },
      error: new Error("unrelated reconcile failure"),
      markReadError: null,
      markingRead: false,
      markRead: async () => undefined,
    } as unknown as FollowController;
    const container = document.createElement("div");
    document.body.appendChild(container);
    const root = createRoot(container);
    await act(async () => root.render(createElement(
      FollowContext.Provider,
      { value: base },
      createElement(FollowUpdatesInbox),
    )));
    expect(container.textContent).not.toContain("Updates could not be marked read");

    await act(async () => root.render(createElement(
      FollowContext.Provider,
      { value: { ...base, markReadError: new Error("write failed") } },
      createElement(FollowUpdatesInbox),
    )));
    expect(container.textContent).toContain("Updates could not be marked read: write failed");
    act(() => root.unmount());
    container.remove();
  });
});
