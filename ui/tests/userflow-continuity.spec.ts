import { expect, test } from "@playwright/test";

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
        left: rect.left,
        right: rect.right,
        width: rect.width,
        scrollWidth: element.scrollWidth,
        clientWidth: element.clientWidth,
      };
    }));

    for (const metric of metrics) {
      expect(metric.scrollWidth).toBeLessThanOrEqual(metric.clientWidth);
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

  const card = page.getByRole("link", { name: /Example Home 4 versus Example Away 4/ });
  await card.scrollIntoViewIfNeeded();
  const before = await page.evaluate(() => window.scrollY);
  expect(before).toBeGreaterThan(300);
  await card.click();
  await expect(page.locator("h1").first()).toBeVisible();

  await page.goBack();
  await expect(page.getByRole("link", { name: /Example Home 4 versus Example Away 4/ })).toBeVisible();
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(before - 80);

  await page.goForward();
  await expect(page.locator("h1").first()).toBeVisible();
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBeLessThan(10);

  await page.goBack();
  await page.getByRole("navigation", { name: "Primary" }).getByRole("link", { name: "Leagues" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Leagues & Europe" })).toBeVisible();
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
