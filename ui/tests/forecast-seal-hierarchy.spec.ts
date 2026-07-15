import { expect, test } from "@playwright/test";

const SCORED_GOAL_FORECAST = "/#/forecast/fa_831ed103a95e335e676c";

test("sealed forecast separates the outcome call from one exact scoreline", async ({ page }) => {
  await page.goto(SCORED_GOAL_FORECAST);

  const forecast = page.getByRole("region", { name: "Sealed forecast" });
  await expect(forecast.getByText("Sealed outcome · 90 minutes")).toBeVisible();
  await expect(forecast.getByText("Example Home 4 to win")).toBeVisible();
  await expect(forecast.locator(".seal-call__prob")).toHaveText("48%");

  await expect(forecast.getByText("Most likely individual scoreline")).toBeVisible();
  await expect(forecast.locator(".seal-call__scoreline strong")).toHaveText("1–1");
  await expect(forecast.getByText(/12% for this one exact score/)).toBeVisible();
  await expect(forecast.getByText(/it is not the overall outcome call/)).toBeVisible();

  // The old separate Seal Stamp card is gone: scan-level metadata belongs to
  // the forecast commitment, while technical identifiers stay available on demand.
  await expect(page.getByRole("region", { name: "Seal stamp" })).toHaveCount(0);
  await expect(forecast.getByText("Sealed at")).toBeVisible();
  await expect(forecast.getByText("Poisson (independent) · v0.1.0")).toBeVisible();

  const audit = forecast.locator(".seal-audit");
  await expect(audit).not.toHaveAttribute("open", "");
  await forecast.getByText("Seal verification details").click();
  await expect(audit).toHaveAttribute("open", "");
  await expect(audit.getByText("Payload sha256")).toBeVisible();
});
