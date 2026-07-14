import { expect, test } from "@playwright/test";

/** The acceptance check from the redesign plan: the page body never scrolls
 *  horizontally at desktop, tablet, or mobile widths. Tables may scroll inside
 *  their own overflow-x container, but the document must not. */

const ROUTES = [
  { name: "matchday", path: "/#/" },
  { name: "sealing-guide", path: "/#/guide/sealing" },
  { name: "search", path: "/#/matches" },
  { name: "leagues", path: "/#/leagues" },
  { name: "league", path: "/#/league/premier-league" },
  { name: "match-cockpit", path: "/#/match/m_synthetic_played_01" },
  { name: "club-half-time", path: "/#/match/m_synthetic_played_05" },
  { name: "world-cup-pedigree", path: "/#/match/m_4c107c1bc7e11203" },
  { name: "forecast-outcome", path: "/#/forecast/fa_b44892255616a50d59bb" },
  { name: "forecast-goal", path: "/#/forecast/fa_5cb65a59b038d9586aea" },
  { name: "lab", path: "/#/lab" },
  { name: "track-record", path: "/#/lab/track-record" },
  { name: "backtests", path: "/#/lab/backtests" },
  { name: "methods", path: "/#/lab/methods" },
  { name: "settings", path: "/#/settings" },
];

const WIDTHS = [375, 768, 1280];

for (const width of WIDTHS) {
  for (const route of ROUTES) {
    test(`no horizontal overflow @${width} — ${route.name}`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.goto(route.path);
      await page.locator("h1, .state__title").first().waitFor();
      await page.waitForLoadState("networkidle");
      const overflow = await page.evaluate(() => {
        const el = document.documentElement;
        return { scroll: el.scrollWidth, client: el.clientWidth };
      });
      expect(
        overflow.scroll,
        `document scrollWidth ${overflow.scroll} exceeds viewport ${overflow.client}`,
      ).toBeLessThanOrEqual(overflow.client);
    });
  }
}

// The reading-comfort popover is right-anchored to the header "Aa" button; on a
// narrow screen it must pin to the viewport, not spill off the left edge.
test("reading-comfort popover stays on-screen @375", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/#/");
  await page.locator("h1").first().waitFor();
  await page.getByRole("button", { name: /reading comfort/i }).click();
  const panel = page.locator(".rc__panel");
  await panel.waitFor();
  const box = await panel.boundingBox();
  expect(box, "popover should be visible").not.toBeNull();
  expect(box!.x, "popover left edge is on-screen").toBeGreaterThanOrEqual(0);
  expect(box!.x + box!.width, "popover right edge is on-screen").toBeLessThanOrEqual(375);
  const overflow = await page.evaluate(() => {
    const el = document.documentElement;
    return { scroll: el.scrollWidth, client: el.clientWidth };
  });
  expect(overflow.scroll).toBeLessThanOrEqual(overflow.client);
});
