import { expect, test } from "@playwright/test";

const MATCH = "/#/match/m_synthetic_01";

test("match cockpit reads as a six-chapter programme ending in the verdict", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto(MATCH);
  await page.locator(".programme-teaser h1").waitFor();

  const teaser = page.locator(".programme-teaser");
  await expect(teaser.getByText("Matchday programme")).toBeVisible();
  await expect(teaser.getByText("Casual read")).toBeVisible();
  await expect(teaser.getByText("The essential story, with technical depth kept out of the way.")).toBeVisible();
  await expect(teaser.getByRole("group", { name: "Detail level" })).toBeVisible();
  await expect(teaser.getByText("Most likely score")).toHaveCount(0);

  const chapters = [
    "The form book",
    "How they play",
    "The history",
    "The models deliberate",
    "The verdict",
    "The analyst’s column",
  ];
  const chapterHeadings = page.locator(".programme-chapter__heading > h2");
  await expect(chapterHeadings).toHaveCount(6);
  expect(await chapterHeadings.allTextContents()).toEqual(chapters);
  await expect(page.locator(".programme-chapter__icon svg")).toHaveCount(6);
  await expect(page.locator(".programme-chapter__divider")).toHaveCount(5);

  const intro = page.locator("#programme-01 .programme-chapter__heading > p");
  expect(await intro.evaluate((element) => element.childNodes[0]?.nodeType)).toBe(3);
  await expect(intro.locator("svg")).toHaveCount(0);
  const firstLetter = await intro.evaluate((element) => {
    const style = getComputedStyle(element, "::first-letter");
    return style.float;
  });
  expect(firstLetter).toBe("none");

  const pulls = page.locator(".programme-pull");
  for (const pull of await pulls.all()) {
    await expect(pull).toHaveAttribute("aria-label", /highlight:/i);
    await expect(pull.locator(".programme-pull__value.num.mono")).toHaveCount(1);
  }

  const positions = await chapterHeadings.evaluateAll((items) =>
    items.map((item) => item.getBoundingClientRect().top + window.scrollY),
  );
  expect(positions).toEqual([...positions].sort((a, b) => a - b));

  const verdict = page.locator("#match-verdict");
  await expect(verdict.locator(".programme-verdict")).toBeVisible();
  await expect(verdict.locator(".pick-ticket")).toBeVisible();
});

test("shared mode switch persists the existing forecast depth choice", async ({ page }) => {
  await page.goto(MATCH);
  const mode = page.getByRole("group", { name: "Detail level" });
  await expect(mode.getByRole("button", { name: "Casual" })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByText("The essential story, with technical depth kept out of the way.")).toBeVisible();
  await expect(page.locator(".match-programme--casual")).toHaveCount(1);

  await mode.getByRole("button", { name: "Expert" }).click();
  await expect(mode.getByRole("button", { name: "Expert" })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByText("Full model values, market detail, sources and audit context.")).toBeVisible();
  await expect(page.locator(".match-programme--expert")).toHaveCount(1);
  expect(await page.evaluate(() => localStorage.getItem("golavo-forecast-mode"))).toBe("expert");

  await page.reload();
  await expect(page.getByRole("group", { name: "Detail level" }).getByRole("button", { name: "Expert" })).toHaveAttribute("aria-pressed", "true");
});

test("sticky pick shortcut appears between teaser and picker, then yields to the picker", async ({ page }) => {
  await page.setViewportSize({ width: 1000, height: 650 });
  await page.goto(MATCH);
  await page.locator("#programme-03").scrollIntoViewIfNeeded();

  const shortcut = page.getByRole("complementary", { name: "Your match pick shortcut" });
  await expect(shortcut).toBeVisible();
  await expect(shortcut.getByText("No pick yet")).toBeVisible();
  await expect(shortcut.getByText(/Locks in|Locks when match day starts|Locked/)).toBeVisible();

  await shortcut.getByRole("button").click();
  await expect(page.locator("#match-verdict .pick-ticket")).toBeInViewport();
  await expect(shortcut).toBeHidden();

  await page.getByRole("button", { name: "Increase Example Home 1 score" }).click();
  await page.getByRole("button", { name: "Save my call" }).click();
  await expect(page.locator(".pick-ticket").getByText("Saved. Your call:")).toBeVisible();

  await page.locator("#programme-03").scrollIntoViewIfNeeded();
  await expect(shortcut).toBeVisible();
  await expect(shortcut.getByText("Your call: 1–0")).toBeVisible();
});
