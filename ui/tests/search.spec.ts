import { expect, test } from "@playwright/test";

test("status filters browse the directory without requiring search text", async ({ page }) => {
  await page.goto("/#/matches");
  await expect(page.getByText("Search the match directory", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Upcoming", exact: true }).click();

  await expect(page.getByText("Search the match directory", { exact: true })).toBeHidden();
  await expect(page.getByRole("status").filter({ hasText: /Showing \d+ of \d+ upcoming/ })).toBeVisible();
});

test("a one-character query explains the search threshold", async ({ page }) => {
  await page.goto("/#/matches");
  await page.getByRole("searchbox", { name: "Search matches" }).fill("a");
  await expect(page.getByText("Type one more character", { exact: true })).toBeVisible();
});
