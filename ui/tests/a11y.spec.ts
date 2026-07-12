import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

/** No serious/critical accessibility violations on the detail pages — checked in
 *  every theme, because the warm palette is where a muted token could slip under
 *  the 4.5:1 contrast floor. Uses the real deterministic mock pages. */

const PAGES = [
  { name: "games", path: "/#/" },
  { name: "forecast", path: "/#/forecast/fa_5cb65a59b038d9586aea" },
  { name: "match-cockpit", path: "/#/match/m_synthetic_played_01" },
  { name: "methods", path: "/#/lab/methods" },
];

const THEMES = ["light", "dark", "warm"] as const;

for (const p of PAGES) {
  for (const theme of THEMES) {
    test(`no serious a11y violations — ${p.name} (${theme})`, async ({ page }) => {
      // Set the theme before first paint, the same way the app's inline script does.
      await page.addInitScript((t) => {
        try { localStorage.setItem("golavo-theme", t as string); } catch { /* ignore */ }
      }, theme);
      await page.goto(p.path);
      await page.locator("h1, .state__title").first().waitFor();
      await page.waitForLoadState("networkidle");

      const results = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
        .analyze();

      const serious = results.violations.filter(
        (v) => v.impact === "serious" || v.impact === "critical",
      );
      const summary = serious.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.length }));
      expect(serious, JSON.stringify(summary, null, 2)).toEqual([]);
    });
  }
}
