import { defineConfig, devices } from "@playwright/test";
import { loadEnvConfig } from "@next/env";

import { E2E_COVERAGE, SERVER_COVERAGE_DIR } from "./e2e/coverage.mjs";

// Same .env.local the app uses, so tests can reach the local Supabase (see e2e/helpers.ts).
loadEnvConfig(process.cwd());

// Coverage runs (`pnpm test:e2e:coverage`) use their own port and always start their own
// server: a reused `pnpm test:e2e` server has no source maps and no NODE_V8_COVERAGE.
const port = E2E_COVERAGE ? 3101 : 3100;

export default defineConfig({
  testDir: "./e2e",
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    trace: "on-first-retry",
  },
  globalSetup: E2E_COVERAGE ? "./e2e/coverage-setup.ts" : undefined,
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  // Tests run against a production build, like users would see it.
  webServer: {
    // Coverage: only `next start` gets NODE_V8_COVERAGE, so prerendering during the
    // build doesn't count as tested.
    command: E2E_COVERAGE
      ? `pnpm build && NODE_V8_COVERAGE=${SERVER_COVERAGE_DIR} pnpm start --port ${port}`
      : `pnpm build && pnpm start --port ${port}`,
    url: `http://127.0.0.1:${port}`,
    reuseExistingServer: !process.env.CI && !E2E_COVERAGE,
    timeout: 180_000,
    // E2E runs never report to Sentry or upload source maps, even if .env.local has them.
    // (An empty value wins over .env.local: Next.js only fills in unset variables.)
    env: { NEXT_PUBLIC_SENTRY_DSN: "", SENTRY_AUTH_TOKEN: "" },
    // Node writes NODE_V8_COVERAGE only on a clean exit, and next start exits on SIGTERM.
    gracefulShutdown: { signal: "SIGTERM", timeout: 10_000 },
  },
});
