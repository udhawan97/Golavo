import { expect, test } from "@playwright/test";

test("Trust Center exposes bounded local verification tools", async ({ page }) => {
  await page.goto("/#/trust");
  await expect(page.getByRole("heading", { level: 1, name: "Trust Center" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Verify a forecast proof" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Forecast-ledger archive" })).toBeVisible();
  await expect(page.getByText(/verified linked checkpoint chain when one exists/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Ledger checkpoints" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Data application receipts" })).toBeVisible();
  const restoreInput = page.locator('label.file-picker input[type="file"]');
  await restoreInput.focus();
  await expect(restoreInput.locator("..")).toHaveCSS("outline-style", "solid");
  await expect(restoreInput.locator("..")).toHaveCSS("outline-width", "3px");
});

test("My Teams fails closed when the local outlook engine is not connected", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("golavo.favorite-teams.v1", JSON.stringify([{
    competitionId: "england-premier-league", leagueSlug: "premier-league",
    leagueName: "Premier League", team: "Exact Club",
  }])));
  await page.goto("/#/teams");
  await expect(page.getByRole("heading", { level: 1, name: "My Teams" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 3, name: "Exact Club" })).toBeVisible();
  await expect(page.getByText("Season outlook unavailable")).toBeVisible();
  await expect(page.getByText(/exact saved club identity was preserved/)).toBeVisible();
  await expect(page.getByText("Exact team identity not present")).toHaveCount(0);
  const importInput = page.locator('label.file-picker input[type="file"]');
  await importInput.focus();
  await expect(importInput.locator("..")).toHaveCSS("outline-style", "solid");
  await expect(importInput.locator("..")).toHaveCSS("outline-width", "3px");
});
