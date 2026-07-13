import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

/** The redesigned AI Analyst Read, exercised in its "done" state via a bundled
 *  sample narrative (gated behind the golavo-ai-fixture flag, which only this
 *  spec sets). Verifies the chip wall is gone (footnotes + one legend), the
 *  research lane is clearly separated, accessibility holds across themes, and
 *  the footnote popover is keyboard-operable. */

const COCKPIT = "/#/match/m_synthetic_played_01";

/** Set the fixture flag + turn AI on (Ollama) before first paint, then trigger
 *  the read so the redesigned Result renders from the sample narrative. */
async function openRead(page: import("@playwright/test").Page, theme = "dark") {
  await page.addInitScript((t) => {
    try {
      localStorage.setItem("golavo-ai-fixture", "1");
      localStorage.setItem("golavo-ai-provider", "ollama");
      localStorage.setItem("golavo-theme", t as string);
    } catch { /* ignore */ }
  }, theme);
  await page.goto(COCKPIT);
  await page.locator("h1, .state__title").first().waitFor();
  await page.getByRole("button", { name: /write the read|run/i }).first().click();
  await page.locator(".ai-result").waitFor();
}

test("done state: verdict, one legend, no chip wall", async ({ page }) => {
  await openRead(page);

  // Verdict hero present.
  await expect(page.locator(".ai-verdict")).toBeVisible();

  // The old repeated source chips are gone — claims carry footnote buttons, not
  // a chip per source per claim.
  expect(await page.locator(".ai-chip--src").count()).toBe(0);
  expect(await page.locator(".ai-fnote").count()).toBeGreaterThan(0);

  // Exactly one deduplicated evidence legend, and its rows are unique sources.
  await expect(page.locator(".ai-evidence")).toHaveCount(1);
  const legendRows = await page.locator(".ai-evidence__item").count();
  expect(legendRows).toBeGreaterThan(0);
  expect(legendRows).toBeLessThanOrEqual(6);

  // Research lane is clearly marked and its links open safely in a new tab.
  const research = page.locator(".ai-research");
  await expect(research).toBeVisible();
  await expect(research).toContainText(/not engine-verified/i);
  const link = research.locator("a.ai-research__link").first();
  await expect(link).toHaveAttribute("target", "_blank");
  await expect(link).toHaveAttribute("rel", /noreferrer/);
});

for (const theme of ["dark", "light"] as const) {
  test(`no serious a11y violations — AI read (${theme})`, async ({ page }) => {
    await openRead(page, theme);
    const results = await new AxeBuilder({ page })
      .include(".ai-panel")
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
      .analyze();
    const serious = results.violations.filter(
      (v) => v.impact === "serious" || v.impact === "critical",
    );
    const summary = serious.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.length }));
    expect(serious, JSON.stringify(summary, null, 2)).toEqual([]);
  });
}

test("footnote popover is keyboard-operable", async ({ page }) => {
  await openRead(page);
  const fnote = page.locator(".ai-fnote").first();
  await fnote.focus();
  await page.keyboard.press("Enter");
  await expect(fnote).toHaveAttribute("aria-expanded", "true");
  await expect(page.locator(".ai-fnote__panel").first()).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(fnote).toHaveAttribute("aria-expanded", "false");
});

test("no horizontal overflow at 375 in the done state", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await openRead(page);
  const overflow = await page.evaluate(() => {
    const el = document.documentElement;
    return { scroll: el.scrollWidth, client: el.clientWidth };
  });
  expect(overflow.scroll).toBeLessThanOrEqual(overflow.client);
});
