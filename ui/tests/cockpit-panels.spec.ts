import { expect, test } from "@playwright/test";

const CLUB = "/#/match/m_synthetic_played_05";

test("club cockpit renders the source-backed second-half story once", async ({ page }) => {
  await page.goto(CLUB);
  const panel = page.getByRole("region", { name: "Second-half story" });
  await expect(panel).toBeVisible();
  await expect(panel.getByText("Saved from behind")).toBeVisible();
  await expect(panel.getByText("Leads kept")).toBeVisible();
  await expect(
    panel.getByRole("img", { name: /Example Played Home 5 saved 6 of 12/ }),
  ).toBeVisible();
  await expect(
    panel.getByText(
      "Counted only over matches with a recorded half-time score — older seasons in the pack lack one.",
    ),
  ).toBeVisible();

  await expect(page.getByText(/After trailing at half-time in 12 matches/)).toHaveCount(0);
  await expect(page.getByText(/After leading at half-time in 10 matches/)).toHaveCount(0);
});

test("second-half story stays club-only", async ({ page }) => {
  await page.goto("/#/match/m_synthetic_played_01");
  await page.locator("h1").waitFor();
  await expect(page.getByRole("heading", { name: "Second-half story" })).toHaveCount(0);
});

test("World Cup cockpit renders pedigree, partial awards, and keyboard reveals", async ({ page }) => {
  await page.goto("/#/match/m_4c107c1bc7e11203");
  const panel = page.getByRole("region", { name: "World Cup pedigree" });
  await expect(panel).toBeVisible();
  await expect(panel.getByText("1930–2022")).toBeVisible();
  await expect(
    panel.getByRole("img", { name: "2 World Cup titles, won 1998 and 2018" }),
  ).toBeVisible();

  const away = panel.locator(".wcp-team--away");
  await expect(away.getByRole("heading", { name: "Morocco" })).toBeVisible();
  await expect(away.getByText("Fourth place")).toBeVisible();
  await expect(away.getByText("Individual awards")).toHaveCount(0);

  const more = panel.getByText("8 more awards");
  await more.focus();
  await page.keyboard.press("Enter");
  await expect(panel.getByText("Paul Pogba")).toBeVisible();

  const source = panel.getByRole("button", { name: "Source" }).first();
  await source.focus();
  await page.keyboard.press("Enter");
  await expect(panel.getByText(/Computed from/).first()).toBeVisible();

  await expect(page.getByText(/France have appeared at 16 World Cups/)).toHaveCount(0);
});

test("World Cup pedigree stays on the exact international competition", async ({ page }) => {
  await page.goto("/#/match/m_synthetic_played_01");
  await page.locator("h1").waitFor();
  await expect(page.getByRole("heading", { name: "World Cup pedigree" })).toHaveCount(0);
});
