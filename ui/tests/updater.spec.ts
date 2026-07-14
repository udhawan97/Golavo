import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { installMockTauri } from "./helpers/mock-tauri";

/** In-app updater UI, driven end to end against the mock Tauri bridge
 *  (helpers/mock-tauri.ts). Covers what a desktop user actually walks:
 *  consent → pill → sheet → progress → install, plus skip/cancel/error paths
 *  and the honesty notes in Settings. The vite mock server has no __TAURI__,
 *  so without the injected bridge none of these surfaces would render. */

const AVAILABLE = {
  outcome: "available" as const,
  version: "9.9.9",
  notes: "Highlights:\n- Fixes bug A\n- Adds feature B",
  date: "2026-07-12T09:00:00Z",
};

/** Consent already answered "off": no card, no auto-check — each test drives
 *  checks manually through Settings, avoiding the 20s auto-check delay. */
const CONSENT_ANSWERED = { "golavo-updates-autocheck": "off" };

async function gotoSettings(page: Page) {
  await page.goto("/#/settings");
  await page.getByRole("heading", { name: "Settings" }).waitFor();
}

function sheet(page: Page) {
  return page.getByRole("dialog", { name: "Software Update" });
}

function emit(page: Page, event: string, payload: unknown) {
  return page.evaluate(
    (msg) => window.__TAURI_MOCK__.emit(msg.event, msg.payload),
    { event, payload },
  );
}

test("Settings external links open through the desktop system browser", async ({ page }) => {
  await installMockTauri(page, { enabled: false, localStorage: CONSENT_ANSWERED });
  await gotoSettings(page);

  await page.getByRole("link", { name: "Releases", exact: true }).click();
  await page.getByRole("link", { name: "Documentation", exact: true }).click();

  const invoked = await page.evaluate(() => window.__TAURI_MOCK__.invoked);
  expect(invoked.filter((command) => command === "open_external_url")).toHaveLength(2);
  await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
});

test("first boot: consent card, Enable checks runs a check, pill appears", async ({ page }) => {
  await installMockTauri(page, { check: AVAILABLE });
  await page.goto("/#/");

  const card = page.getByRole("region", { name: "Automatic update checks" });
  await expect(card).toContainText("Keep Golavo up to date?");
  await card.getByRole("button", { name: "Enable checks" }).click();

  await expect(card).toBeHidden();
  await expect(page.getByRole("button", { name: /Update available/ })).toBeVisible();
  const invoked = await page.evaluate(() => window.__TAURI_MOCK__.invoked);
  expect(invoked).toContain("updater_check");
});

test("first boot: Not now dismisses the card and stays quiet", async ({ page }) => {
  await installMockTauri(page, { check: AVAILABLE });
  await page.goto("/#/");

  const card = page.getByRole("region", { name: "Automatic update checks" });
  await card.getByRole("button", { name: "Not now" }).click();
  await expect(card).toBeHidden();

  await expect(page.getByRole("button", { name: /Update available/ })).toHaveCount(0);
  const invoked = await page.evaluate(() => window.__TAURI_MOCK__.invoked);
  expect(invoked).not.toContain("updater_check");
});

test("full flow: offer → download progress → ready → install", async ({ page }) => {
  await installMockTauri(page, { check: AVAILABLE, localStorage: CONSENT_ANSWERED });
  await gotoSettings(page);
  await page.getByRole("button", { name: "Check now" }).click();

  // Offer: version, safe-rendered notes, verified-download honesty line.
  await expect(sheet(page)).toContainText("Golavo 9.9.9 is available");
  await expect(sheet(page).getByRole("listitem").first()).toHaveText("Fixes bug A");
  await expect(sheet(page)).toContainText("verified before anything installs");

  await sheet(page).getByRole("button", { name: "Update now" }).click();
  await expect(sheet(page)).toContainText("Downloading Golavo 9.9.9");

  // Hiding the sheet mid-download must keep a way back (the pill).
  await sheet(page).getByRole("button", { name: "Hide" }).click();
  const pill = page.getByRole("button", { name: /Downloading update/ });
  await expect(pill).toBeVisible();
  await pill.click();

  await emit(page, "updater://progress", { downloaded: 1048576, total: 4194304 });
  const bar = sheet(page).getByRole("progressbar", { name: "Download progress" });
  await expect(bar).toHaveAttribute("aria-valuenow", "25");
  await expect(sheet(page)).toContainText("1.0 MB of 4.0 MB");

  await emit(page, "updater://state", { phase: "ready", version: "9.9.9" });
  await expect(sheet(page)).toContainText("downloaded and verified");
  await sheet(page).getByRole("button", { name: "Restart Golavo" }).click();

  await expect(sheet(page)).toContainText("Installing Golavo 9.9.9");
  const invoked = await page.evaluate(() => window.__TAURI_MOCK__.invoked);
  expect(invoked).toContain("updater_install_and_restart");
});

test("cancel mid-download returns cleanly to the offer", async ({ page }) => {
  await installMockTauri(page, { check: AVAILABLE, localStorage: CONSENT_ANSWERED });
  await gotoSettings(page);
  await page.getByRole("button", { name: "Check now" }).click();
  await sheet(page).getByRole("button", { name: "Update now" }).click();
  await expect(sheet(page)).toContainText("Downloading Golavo 9.9.9");

  await sheet(page).getByRole("button", { name: "Cancel" }).click();
  await expect(sheet(page)).toContainText("Golavo 9.9.9 is available");
  await expect(sheet(page).getByRole("button", { name: "Update now" })).toBeVisible();
});

test("skip silences the pill; a manual check still tells the truth", async ({ page }) => {
  await installMockTauri(page, { check: AVAILABLE, localStorage: CONSENT_ANSWERED });
  await gotoSettings(page);
  await page.getByRole("button", { name: "Check now" }).click();
  await sheet(page).getByRole("button", { name: "Skip this version" }).click();

  await expect(sheet(page)).toBeHidden();
  await expect(page.getByRole("button", { name: /Update available/ })).toHaveCount(0);
  await expect(page.getByText("Skipping reminders for Golavo 9.9.9")).toBeVisible();

  await page.getByRole("button", { name: "Check now" }).click();
  await expect(sheet(page)).toContainText("You previously skipped this version");

  await sheet(page).getByRole("button", { name: "Show reminders again" }).click();
  await expect(sheet(page)).not.toContainText("previously skipped");
});

test("up to date: honest confirmation with last-checked time", async ({ page }) => {
  await installMockTauri(page, { localStorage: CONSENT_ANSWERED });
  await gotoSettings(page);
  await page.getByRole("button", { name: "Check now" }).click();

  await expect(sheet(page)).toContainText("You’re on the latest version — Golavo 0.2.6");
  await expect(sheet(page)).toContainText("Last checked");
  await expect(sheet(page).getByRole("button", { name: "Check again" })).toBeVisible();
});

test("manual check error: named copy, raw detail, releases fallback", async ({ page }) => {
  await installMockTauri(page, {
    check: { outcome: "error", kind: "unreachable", message: "dns lookup failed" },
    localStorage: CONSENT_ANSWERED,
  });
  await gotoSettings(page);
  await page.getByRole("button", { name: "Check now" }).click();

  await expect(sheet(page)).toContainText("Couldn’t reach GitHub");
  await expect(sheet(page)).toContainText("You may be offline");
  await expect(sheet(page)).toContainText("dns lookup failed");
  await expect(sheet(page).getByRole("link", { name: "releases page" })).toHaveAttribute(
    "href",
    "https://github.com/udhawan97/Golavo/releases",
  );
  await expect(sheet(page).getByRole("button", { name: "Try again" })).toBeVisible();

  await sheet(page).getByRole("button", { name: "Close" }).click();
  await expect(sheet(page)).toBeHidden();
});

test("post-update toast shows once, then never again", async ({ page }) => {
  const justUpdated = { from: "0.2.5", to: "0.2.6", atEpoch: 1752300000, backupTaken: true };
  await installMockTauri(page, { justUpdated, localStorage: CONSENT_ANSWERED });
  await page.goto("/#/");

  const toast = page.getByRole("status").filter({ hasText: "Updated to Golavo 0.2.6" });
  await expect(toast).toContainText("your ledger was backed up before installing");
  await toast.getByRole("button", { name: "Dismiss" }).click();
  await expect(toast).toBeHidden();

  // The seen-stamp persists; a reload (same install, same record) stays quiet.
  await page.reload();
  await page.getByRole("heading").first().waitFor();
  await expect(page.getByText("Updated to Golavo 0.2.6")).toHaveCount(0);

  // Settings keeps the honest record instead.
  await gotoSettings(page);
  await expect(page.getByText(/Updated 0\.2\.5 → 0\.2\.6/)).toBeVisible();
});

test("Settings honesty: enabled build shows the controls", async ({ page }) => {
  await installMockTauri(page, { localStorage: CONSENT_ANSWERED });
  await gotoSettings(page);
  await expect(page.getByLabel("Check for updates automatically")).toBeVisible();
  await expect(page.getByRole("button", { name: "Check now" })).toBeVisible();
  await expect(page.getByText("cryptographically verified")).toBeVisible();
});

test("Settings honesty: unsigned dev build offers the GitHub-release fallback", async ({ page }) => {
  await installMockTauri(page, { enabled: false });
  await gotoSettings(page);
  // No signed-path controls or consent (there is no signed updater here)…
  await expect(page.getByRole("button", { name: "Check now" })).toHaveCount(0);
  await expect(page.getByRole("region", { name: "Automatic update checks" })).toHaveCount(0);
  // …but a real, honest fallback: fetch the latest release + download it.
  await expect(page.getByText(/fetch the latest release from GitHub/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Check for updates" })).toBeVisible();
});

test("fallback: check → available → download → ready → open", async ({ page }) => {
  await installMockTauri(page, {
    enabled: false,
    appVersion: "0.5.1",
    fallback: {
      check: { outcome: "available", version: "9.9.9", notes: "- Fixes bug A", assetSize: 100 * 1024 * 1024 },
    },
  });
  await gotoSettings(page);

  await page.getByRole("button", { name: "Check for updates" }).click();
  await expect(page.getByText(/9\.9\.9 is available/)).toBeVisible();
  await expect(page.getByRole("listitem").filter({ hasText: "Fixes bug A" })).toBeVisible();

  await page.getByRole("button", { name: /Download 9\.9\.9/ }).click();

  // Downloading UI + live progress driven by the fallback-progress event.
  const bar = page.getByRole("progressbar", { name: "Download progress" });
  await expect(bar).toBeVisible();
  await emit(page, "updater://fallback-progress", { downloaded: 50 * 1024 * 1024, total: 100 * 1024 * 1024 });
  await expect(bar).toHaveAttribute("aria-valuenow", "50");

  // Rust resolves the command with the saved path → "ready".
  await page.evaluate(() => window.__TAURI_MOCK__.resolveDownload("/tmp/Golavo_9.9.9.dmg"));
  await expect(page.getByText(/9\.9\.9 is downloaded/)).toBeVisible();

  await page.getByRole("button", { name: "Open installer" }).click();
  const invoked = await page.evaluate(() => window.__TAURI_MOCK__.invoked);
  expect(invoked).toContain("fallback_open");
});

test("fallback: open failure keeps the downloaded file, not a dead-end", async ({ page }) => {
  await installMockTauri(page, {
    enabled: false,
    fallback: {
      check: { outcome: "available", version: "9.9.9" },
      openError: { kind: "other", message: "no default app" },
    },
  });
  await gotoSettings(page);
  await page.getByRole("button", { name: "Check for updates" }).click();
  await page.getByRole("button", { name: /Download 9\.9\.9/ }).click();
  await page.evaluate(() => window.__TAURI_MOCK__.resolveDownload("/tmp/Golavo_9.9.9.dmg"));
  await page.getByRole("button", { name: "Open installer" }).click();

  // The download is preserved: the error explains, the saved path shows, and
  // Open installer is still there to retry.
  await expect(page.getByText(/Couldn’t open it automatically/)).toBeVisible();
  await expect(page.getByText("/tmp/Golavo_9.9.9.dmg")).toBeVisible();
  await expect(page.getByRole("button", { name: "Open installer" })).toBeVisible();
});

test("fallback: cancel mid-download returns cleanly to the offer", async ({ page }) => {
  await installMockTauri(page, { enabled: false, fallback: { check: { outcome: "available", version: "9.9.9" } } });
  await gotoSettings(page);
  await page.getByRole("button", { name: "Check for updates" }).click();
  await page.getByRole("button", { name: /Download 9\.9\.9/ }).click();
  await expect(page.getByRole("progressbar", { name: "Download progress" })).toBeVisible();

  await page.getByRole("button", { name: "Cancel" }).click();
  // Back to the offer — the download button is clickable again, no error card.
  await expect(page.getByRole("button", { name: /Download 9\.9\.9/ })).toBeVisible();
});

test("fallback: up to date is an honest confirmation", async ({ page }) => {
  await installMockTauri(page, { enabled: false, fallback: { check: { outcome: "upToDate", version: "0.5.1" } } });
  await gotoSettings(page);
  await page.getByRole("button", { name: "Check for updates" }).click();
  await expect(page.getByText(/on the latest version.*Golavo 0\.5\.1/)).toBeVisible();
});

test("fallback: check error shows named copy + releases fallback", async ({ page }) => {
  await installMockTauri(page, {
    enabled: false,
    fallback: { check: { outcome: "error", kind: "unreachable", message: "dns error" } },
  });
  await gotoSettings(page);
  await page.getByRole("button", { name: "Check for updates" }).click();
  await expect(page.getByText("Couldn’t reach GitHub")).toBeVisible();
  await expect(page.getByText("dns error")).toBeVisible();
  await expect(page.getByRole("link", { name: "releases page" })).toBeVisible();

  // A failed CHECK must retry the check (not download a stale rel).
  await page.getByRole("button", { name: "Try again" }).click();
  const invoked = await page.evaluate(() => window.__TAURI_MOCK__.invoked);
  expect(invoked.filter((c) => c === "fallback_check").length).toBeGreaterThanOrEqual(2);
  expect(invoked).not.toContain("fallback_download");
});

test("fallback: newer release with no installer for this platform points at releases", async ({ page }) => {
  await installMockTauri(page, {
    enabled: false,
    fallback: { check: { outcome: "noAsset", version: "9.9.9" } },
  });
  await gotoSettings(page);
  await page.getByRole("button", { name: "Check for updates" }).click();
  await expect(page.getByText(/no installer for your platform/)).toBeVisible();
  const updates = page.getByRole("region", { name: "Updates" });
  await expect(updates.getByRole("button", { name: /Download/ })).toHaveCount(0);
});

test("Settings honesty: source build (no Tauri) points at git pull", async ({ page }) => {
  await gotoSettings(page);
  await expect(page.getByText(/running Golavo from source/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Check now" })).toHaveCount(0);
  await expect(page.getByRole("region", { name: "Automatic update checks" })).toHaveCount(0);
});
