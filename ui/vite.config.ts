import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// The dev server binds to loopback; the desktop shell proxies to the sidecar.
export default defineConfig({
  plugins: [react()],
  server: { host: "127.0.0.1", port: 5173 },
  // Vitest runs only the co-located unit tests. The Playwright e2e specs under
  // tests/ (overflow + axe) use Playwright's own runner via `npm run test:e2e`;
  // without this exclude, `vitest run` tries to collect them and errors on the
  // `test()`-in-async-describe pattern Playwright uses.
  test: {
    include: ["src/**/*.test.{ts,tsx}"],
    exclude: ["tests/**", "node_modules/**", "dist/**"],
  },
});
