import { defineConfig, devices } from "@playwright/test";

// PW_PORT lets a local run pick a free port (avoiding a collision with another
// dev server); CI leaves it unset and uses the default.
const PORT = process.env.PW_PORT ?? "5173";

/** E2E gate for the redesign: no horizontal overflow at common widths, and no
 *  serious/critical accessibility violations on the detail pages across all
 *  three themes. Runs against the mock-data dev server (hermetic, no network). */
export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "line" : "list",
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: `npm run dev -- --port ${PORT} --strictPort`,
    port: Number(PORT),
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
