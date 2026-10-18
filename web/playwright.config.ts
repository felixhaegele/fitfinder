import { defineConfig, devices } from "@playwright/test";
import { loadEnvConfig } from "@next/env";

// Same .env.local the app uses, so tests can reach the local Supabase (see e2e/helpers.ts).
loadEnvConfig(process.cwd());

const port = 3100;

export default defineConfig({
  testDir: "./e2e",
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  // Tests run against a production build, like users would see it.
  webServer: {
    command: `pnpm build && pnpm start --port ${port}`,
    url: `http://127.0.0.1:${port}`,
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
  },
});
