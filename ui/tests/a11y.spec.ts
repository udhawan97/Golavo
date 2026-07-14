import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

/** No serious/critical accessibility violations on the detail pages — checked in
 *  every theme, because the warm palette is where a muted token could slip under
 *  the 4.5:1 contrast floor. Uses the real deterministic mock pages. */

const PAGES = [
  { name: "matchday", path: "/#/" },
  { name: "forecast", path: "/#/forecast/fa_5cb65a59b038d9586aea" },
  { name: "match-cockpit", path: "/#/match/m_synthetic_played_01" },
  { name: "club-half-time", path: "/#/match/m_synthetic_played_05" },
  { name: "world-cup-pedigree", path: "/#/match/m_4c107c1bc7e11203" },
  { name: "methods", path: "/#/lab/methods" },
  { name: "sealing-guide", path: "/#/guide/sealing" },
  { name: "picks-guide", path: "/#/guide/picks" },
  { name: "my-season", path: "/#/season" },
  // Table/form-dense routes: where a muted caption or header could slip contrast.
  { name: "search", path: "/#/matches" },
  { name: "leagues", path: "/#/leagues" },
  { name: "track-record", path: "/#/lab/track-record" },
  { name: "backtests", path: "/#/lab/backtests" },
  { name: "sealed-forecasts", path: "/#/lab/forecasts" },
  { name: "settings", path: "/#/settings" },
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
