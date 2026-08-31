import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const status = {
  schema_version: "0.1.0",
  enabled: true,
  capabilities: ["player_lens"],
  terms_accepted_at_utc: "2026-08-20T16:00:00Z",
  terms_acceptance_version: "sportmonks-terms-reviewed-2026-08-29",
  connector_supported: true,
  request_policy: "foreground_click_only",
  storage_policy: "derived_response_memory_only",
  provider: {
    source_id: "sportmonks-v3",
    name: "Sportmonks",
    docs_url: "https://docs.sportmonks.com/v3/",
    terms_url: "https://www.sportmonks.com/terms-of-service/",
    privacy_url: "https://www.sportmonks.com/privacy-policy/",
    pricing_url: "https://www.sportmonks.com/football-api/pricing/",
    terms_reviewed_date: "2026-08-29",
    terms_content_sha256: "0".repeat(64),
    terms_acceptance_version: "sportmonks-terms-reviewed-2026-08-29",
  },
  credential: { configured: true, source: "keychain", writable: true, environment_variable: "SPORTMONKS_API_TOKEN" },
  usage: { display: true, model_input: false, forecast_sealing: false, forecast_settlement: false, calibration: false, scoring: false, ai_evidence: false, exports: false },
};

const players = Array.from({ length: 24 }, (_, index) => ({
  lineup_id: 100 + index,
  player_id: 200 + index,
  team_id: index < 12 ? 1 : 2,
  name: `Roster Player ${index + 1}`,
  jersey_number: index + 1,
  position_id: 27,
  participation: index % 6 === 0 ? "substitute" : "starter",
  metrics: index === 0 ? [] : [{
    type_id: 52,
    developer_name: "GOALS",
    label: "Goals",
    group: "offensive",
    unit: "count",
    value: 1,
  }],
}));

const response = {
  schema_version: "0.1.0",
  status: "available",
  label: "Outside signals — not a Golavo forecast.",
  provider: { source_id: "sportmonks-v3", name: "Sportmonks", docs_url: status.provider.docs_url, terms_url: status.provider.terms_url },
  identity: {
    golavo_match_id: "m_player_dossier_fixture",
    provider_fixture_id: 42,
    provider_home_team_id: 1,
    provider_away_team_id: 2,
    provider_home_team: "Provider Home FC",
    provider_away_team: "Provider Away FC",
    provider_league_id: 8,
    provider_league: "Premier League",
    provider_season_id: 202627,
    provider_season: "2026/2027",
    provider_kickoff_utc: "2026-08-20T18:00:00Z",
    match_method: "exact_competition_season_teams_and_kickoff",
  },
  prediction: { status: "unavailable", reason_code: "not_requested", message: "Not requested.", retryable: false },
  odds: { status: "unavailable", reason_code: "not_requested", message: "Not requested.", retryable: false },
  player_lens: {
    status: "available",
    lineup_state: "confirmed",
    players,
    coverage: { player_count: 24, players_with_metrics: 23, missing_stat_is_zero: false },
  },
  provenance: {
    fetched_at_utc: "2026-08-20T17:05:00Z",
    terms_acceptance_version: "sportmonks-terms-reviewed-2026-08-29",
    raw_response_sha256: {},
    raw_response_storage: "not_persisted",
    model_input: false,
  },
};

async function mockPlayerLens(page: Page) {
  await page.route("**/api/v1/providers/sportmonks/settings", (route) => route.fulfill({ json: status }));
  await page.route("**/api/v1/matches/m_player_dossier_fixture/outside-signals", (route) => route.fulfill({ json: response }));
}

for (const width of [1280, 390]) {
  test(`large-roster dossier moves into view and restores focus @${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 720 });
    await mockPlayerLens(page);
    await page.goto("/tests/fixtures/player-dossier.html");
    await page.getByRole("button", { name: "Fetch player data" }).click();

    const firstPlayer = page.getByRole("button", { name: /^Roster Player 1 Bench/ });
    await firstPlayer.click();
    const dossier = page.locator(".player-dossier");

    await expect(dossier).toBeFocused();
    await expect(dossier).toBeInViewport();
    await expect(dossier).toContainText("No match statistics were supplied for this player");
    const overflow = await page.evaluate(() => ({
      scroll: document.documentElement.scrollWidth,
      client: document.documentElement.clientWidth,
    }));
    expect(overflow.scroll).toBeLessThanOrEqual(overflow.client);
    const accessibility = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
      .analyze();
    const serious = accessibility.violations.filter(
      (violation) => violation.impact === "serious" || violation.impact === "critical",
    );
    expect(serious).toEqual([]);

    await dossier.getByRole("button", { name: "Close dossier" }).click();
    await expect(firstPlayer).toBeFocused();
    await expect(dossier).toHaveCount(0);
  });
}
