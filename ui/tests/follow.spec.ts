import { expect, test } from "@playwright/test";

test("match cards keep navigation and follow as sibling controls", async ({ page }) => {
  await page.goto("/#/");
  const shell = page.locator(".game-card-shell").first();
  await shell.waitFor();
  await expect(shell.locator(":scope > a.game-card")).toHaveCount(1);
  await expect(shell.locator(":scope > .game-card-shell__follow > button")).toHaveCount(1);
  await expect(shell.locator("a button")).toHaveCount(0);
});

test("browser preview labels following as desktop-only without prompting", async ({ page }) => {
  await page.goto("/#/");
  const button = page.getByRole("button", {
    name: "Follow match — available in the local desktop app",
  }).first();
  await expect(button).toBeDisabled();
});

test("settings states the exact while-open lifecycle boundary", async ({ page }) => {
  await page.goto("/#/settings");
  await expect(page.getByText(/Closing Golavo stops checks/)).toBeVisible();
  await expect(page.getByText(/No helper, Login Item, or LaunchAgent is installed/)).toBeVisible();
  await expect(page.getByText(/They do not monitor matches after you quit/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Enable local notifications" })).toBeDisabled();
});
