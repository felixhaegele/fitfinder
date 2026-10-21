// Playwright globalSetup for coverage runs: start from empty coverage data.
import { rmSync } from "node:fs";

import MCR from "monocart-coverage-reports";

import { coverageOptions, SERVER_COVERAGE_DIR } from "./coverage.mjs";

export default function globalSetup() {
  MCR(coverageOptions).cleanCache();
  rmSync(SERVER_COVERAGE_DIR, { recursive: true, force: true });
}
