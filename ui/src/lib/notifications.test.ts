import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  isPermissionGranted: vi.fn<() => Promise<boolean>>(),
  requestPermission: vi.fn<() => Promise<"granted" | "denied" | "prompt">>(),
  sendNotification: vi.fn(),
}));

vi.mock("@tauri-apps/plugin-notification", () => mocks);

import {
  localNotificationPermission,
  requestLocalNotificationPermission,
  submitFollowNotification,
} from "./notifications";

describe("local followed-match notifications", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.defineProperty(globalThis, "__TAURI_INTERNALS__", {
      value: {},
      configurable: true,
    });
  });

  it("checks permission without ever prompting", async () => {
    mocks.isPermissionGranted.mockResolvedValue(false);
    await expect(localNotificationPermission()).resolves.toBe("not_granted");
    expect(mocks.requestPermission).not.toHaveBeenCalled();
  });

  it("requests permission only through the explicit request function", async () => {
    mocks.isPermissionGranted.mockResolvedValue(false);
    mocks.requestPermission.mockResolvedValue("granted");
    await expect(requestLocalNotificationPermission()).resolves.toBe("granted");
    expect(mocks.requestPermission).toHaveBeenCalledOnce();
  });

  it("submits only generic privacy-preserving copy", () => {
    submitFollowNotification();
    expect(mocks.sendNotification).toHaveBeenCalledWith({
      title: "Golavo match update",
      body: "Open Golavo to review a source-backed change.",
    });
  });
});
