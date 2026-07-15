import { expect, test } from "@playwright/test";

/** The acceptance check from the redesign plan: the page body never scrolls
 *  horizontally at desktop, tablet, or mobile widths. Tables may scroll inside
 *  their own overflow-x container, but the document must not. */

const ROUTES = [
  { name: "matchday", path: "/#/" },
  { name: "sealing-guide", path: "/#/guide/sealing" },
  { name: "picks-guide", path: "/#/guide/picks" },
  { name: "my-season", path: "/#/season" },
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

test("long club names wrap only between words inside match cards", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/#/");
  const card = page.locator(".game-card:has(.game-card__score)").first();
  await card.waitFor();
  const teams = card.locator(".game-card__team");
  await teams.nth(0).evaluate((node) => {
    node.textContent = "Nottingham Forest";
    node.classList.remove("game-card__team--compact", "game-card__team--tight");
    node.classList.add("game-card__team--regular");
  });
  await teams.nth(1).evaluate((node) => {
    node.textContent = "Wolverhampton Wanderers";
    node.classList.remove("game-card__team--regular", "game-card__team--tight");
    node.classList.add("game-card__team--compact");
  });

  const cardBox = await card.boundingBox();
  expect(cardBox).not.toBeNull();
  for (let index = 0; index < 2; index += 1) {
    const teamBox = await teams.nth(index).boundingBox();
    expect(teamBox).not.toBeNull();
    expect(teamBox!.x).toBeGreaterThanOrEqual(cardBox!.x);
    expect(teamBox!.x + teamBox!.width).toBeLessThanOrEqual(cardBox!.x + cardBox!.width);
    const wrapping = await teams.nth(index).evaluate((node) => {
      const style = getComputedStyle(node);
      return {
        overflowWrap: style.overflowWrap,
        wordBreak: style.wordBreak,
        height: node.getBoundingClientRect().height,
        lineHeight: Number.parseFloat(style.lineHeight),
        scrollWidth: node.scrollWidth,
        clientWidth: node.clientWidth,
      };
    });
    expect(wrapping.overflowWrap).toBe("normal");
    expect(wrapping.wordBreak).toBe("normal");
    expect(wrapping.scrollWidth).toBeLessThanOrEqual(wrapping.clientWidth);
    expect(wrapping.height).toBeGreaterThan(wrapping.lineHeight * 1.5);
    expect(wrapping.height).toBeLessThanOrEqual(wrapping.lineHeight * 2.1);
  }

  // The score owns a protected centre lane: even demanding names must leave a
  // deliberate visual pause on both sides instead of appearing fused to it.
  const scoreBox = await card.locator(".game-card__score").boundingBox();
  const homeBox = await teams.nth(0).boundingBox();
  const awayBox = await teams.nth(1).boundingBox();
  expect(scoreBox).not.toBeNull();
  expect(homeBox).not.toBeNull();
  expect(awayBox).not.toBeNull();
  expect(scoreBox!.x - (homeBox!.x + homeBox!.width)).toBeGreaterThanOrEqual(8);
  expect(awayBox!.x - (scoreBox!.x + scoreBox!.width)).toBeGreaterThanOrEqual(8);
});

test("matchday grid uses three, two, then one column", async ({ page }) => {
  for (const [width, expected] of [[1280, 3], [900, 2], [600, 1]] as const) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/#/");
    const grid = page.locator(".game-grid").first();
    await grid.waitFor();
    const columns = await grid.evaluate((node) => getComputedStyle(node).gridTemplateColumns.split(" ").length);
    expect(columns, `expected ${expected} columns at ${width}px`).toBe(expected);
  }
});

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
