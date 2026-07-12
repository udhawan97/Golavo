import { expect, test } from "@playwright/test";

/** The acceptance check from the redesign plan: the page body never scrolls
 *  horizontally at desktop, tablet, or mobile widths. Tables may scroll inside
 *  their own overflow-x container, but the document must not. */

const ROUTES = [
  { name: "matchday", path: "/#/" },
  { name: "search", path: "/#/matches" },
  { name: "match-played", path: "/#/match/m_synthetic_played_01" },
  { name: "forecast-outcome", path: "/#/forecast/fa_b44892255616a50d59bb" },
  { name: "forecast-goal", path: "/#/forecast/fa_5cb65a59b038d9586aea" },
  { name: "ledger", path: "/#/ledger" },
  { name: "eval", path: "/#/eval" },
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
