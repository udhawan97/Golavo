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
