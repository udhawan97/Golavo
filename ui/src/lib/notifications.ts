import {
  isPermissionGranted,
  requestPermission,
  sendNotification,
} from "@tauri-apps/plugin-notification";

export type LocalNotificationPermission = "granted" | "not_granted" | "denied" | "unsupported";

function isDesktopRuntime(): boolean {
  return "__TAURI_INTERNALS__" in globalThis;
}

export async function localNotificationPermission(): Promise<LocalNotificationPermission> {
  if (!isDesktopRuntime()) return "unsupported";
  try {
    return (await isPermissionGranted()) ? "granted" : "not_granted";
  } catch {
    return "unsupported";
  }
}

/** Called only from the explicit Settings button click. */
export async function requestLocalNotificationPermission(): Promise<LocalNotificationPermission> {
  if (!isDesktopRuntime()) return "unsupported";
  try {
    if (await isPermissionGranted()) return "granted";
    const result = await requestPermission();
    return result === "granted" ? "granted" : "denied";
  } catch {
    return "unsupported";
  }
}

export function submitFollowNotification(): void {
  sendNotification({
    title: "Golavo match update",
    body: "Open Golavo to review a source-backed change.",
  });
}
