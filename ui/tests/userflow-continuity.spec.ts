import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("Matchday leads with current fixtures and keeps the World Cup in the archive", async ({ page }) => {
  await page.goto("/#/");

  await expect(page.getByRole("heading", { level: 1, name: /Make the score call/ })).toBeVisible();
  await expect(page.getByRole("button", { name: "Upcoming", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator(".tournament-outlook")).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Premier League", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "World Cup 2026 archive" })).toBeVisible();
});

test("Premier League keeps live modules ahead of historical research", async ({ page }) => {
  await page.goto("/#/league/premier-league");

  await expect(page.getByText("2026–27 live season desk", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "2026–27 season pulse" })).toBeVisible();
  await expect(page.getByLabel("Current season league statistics")).toContainText("Played10 / 380");
  await expect(page.getByLabel("Current season league statistics")).toContainText("Future361");
  await expect(page.getByLabel("Current season league statistics")).toContainText("Result gaps9");
  await expect(page.getByText(/9 past result gaps are held back/)).toBeVisible();
  await expect(page.getByText(/Sources: golavo-synthetic-contract-fixtures/)).toBeVisible();
  await page.getByText("Open the 2-team form board").click();
  await expect(page.getByRole("rowheader", { name: "Example Athletic" })).toBeVisible();
  await expect(page.getByLabel("Example Athletic last 1: W")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Season outlook" })).toBeVisible();
  const archive = page.locator("details.history-archive").filter({ hasText: "Historical research archive" });
  await expect(archive).not.toHaveAttribute("open", "");
  await expect(archive.getByText("Older event data · model context, not the live-season headline")).toBeVisible();
  expect(await page.evaluate(() => {
    const fixtures = document.querySelector("#current-fixtures");
    const history = Array.from(document.querySelectorAll("details.history-archive")).at(-1) ?? null;
    return Boolean(fixtures && history && (fixtures.compareDocumentPosition(history) & Node.DOCUMENT_POSITION_FOLLOWING));
  })).toBe(true);
});

test("320px primary navigation stays legible at M and XL reading sizes", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 568 });
  await page.goto("/#/");

  const links = page.getByRole("navigation", { name: "Primary" }).getByRole("link");
  await expect(links).toHaveCount(4);
  for (const size of ["md", "xl"]) {
    await page.evaluate((textSize) => localStorage.setItem("golavo-text-size", textSize), size);
    await page.reload();
    const metrics = await links.evaluateAll((nodes) => nodes.map((node) => {
      const element = node as HTMLElement;
      const rect = element.getBoundingClientRect();
      return {
        label: element.textContent,
        left: rect.left,
        right: rect.right,
        width: rect.width,
        scrollWidth: element.scrollWidth,
        clientWidth: element.clientWidth,
      };
    }));

    for (const metric of metrics) {
      expect(metric.scrollWidth, `${metric.label} must stay inside its nav target`).toBeLessThanOrEqual(metric.clientWidth);
      expect(Math.abs(metric.width - metrics[0].width)).toBeLessThan(0.1);
    }
    for (let index = 1; index < metrics.length; index += 1) {
      expect(metrics[index].left - metrics[index - 1].right).toBeGreaterThanOrEqual(4);
    }
  }
});

test("Back restores the Matchday card that opened the cockpit", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/#/");
  await page.getByRole("button", { name: "Recent 30 days", exact: true }).click();

  const card = page.getByRole("link", { name: /Example Home 4 versus Example Away 4/ });
  await card.scrollIntoViewIfNeeded();
  expect(await page.evaluate(() => window.scrollY)).toBeGreaterThan(300);
  await card.click();
  await expect(page.locator("h1").first()).toBeVisible();
  await expect(page.locator("main#main")).toBeFocused();
  await expect(page).toHaveTitle("Match cockpit · Golavo");

  await page.goBack();
  await expect(card).toBeInViewport();
  await expect(page).toHaveTitle("Matchday · Golavo");

  await page.goForward();
  await expect(page.locator("h1").first()).toBeVisible();
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBeLessThan(10);

  await page.goBack();
  await page.getByRole("navigation", { name: "Primary" }).getByRole("link", { name: "Leagues" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Leagues & 2026–27" })).toBeVisible();
  await expect(page.locator("main#main")).toBeFocused();
  await expect(page).toHaveTitle("Leagues & Europe · Golavo");
  await expect(page.locator('[role="status"]').filter({ hasText: "Leagues & Europe" })).toBeAttached();
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBeLessThan(10);
});

test("Escape closes Reading Comfort and restores focus to its trigger", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/#/");

  const trigger = page.getByRole("button", { name: /reading comfort/i });
  await trigger.click();
  await expect(page.locator(".rc__panel")).toBeVisible();
  await page.getByRole("group", { name: "Text size" }).getByRole("button", { name: "XL" }).click();
  await page.keyboard.press("Escape");

  await expect(page.locator(".rc__panel")).toHaveCount(0);
  await expect(trigger).toBeFocused();
  await expect(trigger).toHaveAttribute("aria-expanded", "false");
});

test("the page guide follows the route and restores focus on Escape", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/#/settings");

  const trigger = page.getByRole("button", { name: /guide for this page/i });
  await trigger.click();
  const guide = page.getByRole("dialog", { name: /tune golavo without crossing a boundary/i });
  await expect(guide).toBeVisible();
  await expect(guide).toBeFocused();
  await expect(guide.getByText("Set theme, text size, spacing, and contrast first.")).toBeVisible();
  await page.keyboard.press("Tab");
  const close = guide.getByRole("button", { name: "Close page guide" });
  await expect(close).toBeFocused();
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  expect(results.violations.filter(
    (violation) => violation.impact === "serious" || violation.impact === "critical",
  )).toEqual([]);
  await close.click();

  await expect(guide).toHaveCount(0);
  await expect(trigger).toBeFocused();
  await expect(trigger).toHaveAttribute("aria-expanded", "false");

  await trigger.click();
  await expect(guide).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(guide).toHaveCount(0);
  await expect(trigger).toBeFocused();

  await page.goto("/#/match/m_synthetic_played_01");
  await trigger.click();
  await expect(page.getByRole("dialog", { name: /read the match from headline to source/i })).toBeVisible();
});

test("Settings jump controls and in-page guide keep orientation intact", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 700 });
  await page.goto("/#/settings");

  await page.getByRole("button", { name: "Sources", exact: true }).click();
  const sources = page.getByRole("heading", { name: "Data & local history" });
  await expect(sources).toBeFocused();
  await expect(sources).toBeInViewport();

  await page.getByRole("button", { name: "Reading", exact: true }).click();
  const appearance = page.getByRole("heading", { name: "Appearance" });
  await expect(appearance).toBeFocused();
  await expect(appearance).toBeInViewport();

  await page.getByRole("button", { name: "Open this page’s guide" }).click();
  const guide = page.getByRole("dialog", { name: /tune golavo without crossing a boundary/i });
  await expect(guide).toBeVisible();
  await expect(guide).toBeFocused();
  await guide.getByRole("link", { name: "Open the Trust Center" }).click();
  await expect(page).toHaveURL(/#\/trust$/);
  await expect(page.getByRole("heading", { level: 1, name: "Trust Center" })).toBeVisible();
});

test("destructive settings confirmations expose Cancel and disarm with Escape", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/#/settings");

  const followTrigger = page.getByRole("button", { name: "Remove follow history" });
  await followTrigger.click();
  const followCancel = page.getByRole("button", { name: "Cancel removing follow history" });
  await expect(followCancel).toBeVisible();
  await expect(followCancel).toBeFocused();
  await expect(page.getByRole("button", { name: "Confirm remove follow history" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(followTrigger).toBeVisible();
  await expect(followTrigger).toBeFocused();

  await page.getByRole("button", { name: "Remove all proposals" }).click();
  const proposalCancel = page.getByRole("button", { name: "Cancel removing all proposals" });
  await expect(proposalCancel).toBeFocused();
  await proposalCancel.click();
  await expect(page.getByRole("button", { name: "Remove all proposals" })).toBeFocused();
});

test("wide analytical tables reveal and clear a horizontal-scroll cue", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.addInitScript(() => localStorage.setItem("golavo-text-size", "xl"));
  await page.goto("/#/lab/track-record");

  const shell = page.locator(".table-scroll-shell").first();
  await expect(shell).toHaveAttribute("data-overflow", "true");
  const hint = shell.getByText("More: sealed date, outcome and scores", { exact: false });
  await expect(hint).toBeVisible();
  const scroller = shell.locator(".table-wrap");
  const firstRowHeader = scroller.getByRole("rowheader").first();
  await scroller.evaluate((node) => {
    node.scrollLeft = node.scrollWidth;
    node.dispatchEvent(new Event("scroll"));
  });
  await expect(shell).toHaveAttribute("data-at-end", "true");
  await expect(hint).toBeHidden();
  const [scrollerBox, rowHeaderBox] = await Promise.all([
    scroller.boundingBox(),
    firstRowHeader.boundingBox(),
  ]);
  expect(scrollerBox).not.toBeNull();
  expect(rowHeaderBox).not.toBeNull();
  expect(Math.abs(rowHeaderBox!.x - scrollerBox!.x)).toBeLessThanOrEqual(2);

  await page.setViewportSize({ width: 1440, height: 900 });
  await scroller.evaluate((node) => {
    node.scrollLeft = 0;
    node.dispatchEvent(new Event("scroll"));
  });
  await expect(shell).toHaveAttribute("data-compact", "false");
  await expect(shell).toHaveAttribute("data-at-end", "false");
  await expect(hint).toBeHidden();
});
