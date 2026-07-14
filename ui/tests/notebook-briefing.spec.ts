import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const FORECAST = "/#/forecast/fa_b44892255616a50d59bb";

async function openNotebook(page: import("@playwright/test").Page, width = 1280) {
  await page.setViewportSize({ width, height: 900 });
  await page.goto(FORECAST);
  await page.locator("h1, .state__title").first().waitFor();
  await page.locator(".nb-panel").waitFor();
}

test("briefing and deep notebook are one progressive panel", async ({ page }) => {
  await openNotebook(page);
  const notebook = page.locator(".nb-panel");

  await expect(notebook.getByRole("heading", { name: "Commentator’s Notebook" })).toBeVisible();
  await expect(notebook.getByRole("heading", { name: "Three things to know" })).toBeVisible();
  await expect(notebook.locator(".nb-brief-card")).toHaveCount(3);
  await expect(page.locator(".insight-card")).toHaveCount(0);

  const provenance = notebook.locator(".nb-provenance");
  await expect(provenance).not.toHaveAttribute("open", "");
  await provenance.locator("summary").click();
  await expect(provenance.locator(".nb-provenance__body")).toBeVisible();
});

test("notebook stays accessible and contained at narrow width", async ({ page }) => {
  await openNotebook(page, 375);
  const notebook = page.locator(".nb-panel");
  const results = await new AxeBuilder({ page })
    .include(".nb-panel")
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  const serious = results.violations.filter(
    (violation) => violation.impact === "serious" || violation.impact === "critical",
  );
  expect(serious).toEqual([]);

  const overflow = await notebook.evaluate((element) => ({
    scroll: element.scrollWidth,
    client: element.clientWidth,
  }));
  expect(overflow.scroll).toBeLessThanOrEqual(overflow.client);
});
