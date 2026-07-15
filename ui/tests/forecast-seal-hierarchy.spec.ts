import { expect, test } from "@playwright/test";

const SCORED_GOAL_FORECAST = "/#/forecast/fa_831ed103a95e335e676c";
const UPCOMING_MATCH = "/#/match/m_synthetic_01";

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

test("the match keeps the score picker and sealed model call together beneath the verdict", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("golavo-forecast-mode", "expert"));
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto(UPCOMING_MATCH);

  const cluster = page.locator(".pick-decision-grid--paired");
  const picker = cluster.locator(".pick-ticket");
  const seal = cluster.getByRole("region", { name: "Sealed forecast" });
  await expect(picker.getByRole("heading", { name: "What’s your score?" })).toBeVisible();
  await expect(seal).toBeVisible();

  const [pickerBox, sealBox, councilBox, verdictBox] = await Promise.all([
    picker.boundingBox(),
    seal.boundingBox(),
    page.locator('[data-tour="cockpit-council"]').boundingBox(),
    page.locator(".programme-verdict").boundingBox(),
  ]);
  expect(pickerBox).not.toBeNull();
  expect(sealBox).not.toBeNull();
  expect(councilBox).not.toBeNull();
  expect(verdictBox).not.toBeNull();
  expect(Math.abs(pickerBox!.y - sealBox!.y)).toBeLessThanOrEqual(2);
  expect(verdictBox!.y).toBeGreaterThan(councilBox!.y + councilBox!.height);
  expect(pickerBox!.y).toBeGreaterThanOrEqual(verdictBox!.y + verdictBox!.height - 1);

  await page.setViewportSize({ width: 375, height: 812 });
  const [mobilePicker, mobileSeal, rivals] = await Promise.all([
    picker.boundingBox(),
    seal.boundingBox(),
    page.locator(".rivals").boundingBox(),
  ]);
  expect(mobilePicker).not.toBeNull();
  expect(mobileSeal).not.toBeNull();
  expect(rivals).not.toBeNull();
  expect(mobileSeal!.y).toBeGreaterThanOrEqual(mobilePicker!.y + mobilePicker!.height - 1);
  expect(rivals!.y).toBeGreaterThanOrEqual(mobileSeal!.y + mobileSeal!.height - 1);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(375);
});
