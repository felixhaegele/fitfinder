// Specs import `test` from here instead of @playwright/test, so every test's `page` records
// browser coverage when E2E_COVERAGE=1 (see coverage.mjs). Without it, this is plain Playwright.
import { test as base } from "@playwright/test";
import MCR from "monocart-coverage-reports";

import { coverageOptions, E2E_COVERAGE } from "./coverage.mjs";

export { expect } from "@playwright/test";

// The fixture callback is named `provide`, not Playwright's usual `use`: ESLint's React
// rules would mistake `use(page)` for React's use() hook.
export const test = base.extend({
  page: async ({ page }, provide) => {
    if (!E2E_COVERAGE) {
      await provide(page);
      return;
    }
    // Stored in MCR's cache dir; e2e/coverage-report.mjs merges it with the server's.
    const report = MCR(coverageOptions);
    const start = () => page.coverage.startJSCoverage({ resetOnNavigation: false });
    const save = async () => report.add(await page.coverage.stopJSCoverage());

    // A full page load (page.goto) throws away the previous document's scripts, and with
    // them their coverage. So save what we have before every goto. Client-side navigation
    // (links, redirects from server actions) keeps the document and needs nothing.
    const goto = page.goto.bind(page);
    page.goto = async (...args) => {
      await save();
      await start();
      return goto(...args);
    };

    await start();
    await provide(page);
    await save();
  },
});
