// Runs after `playwright test` (see `pnpm test:e2e:coverage`): by then the Next.js server
// has exited and Node has written its coverage. Merges it with the browser coverage the
// fixtures collected and writes coverage-e2e/report/lcov-e2e.info.
import { existsSync, readdirSync, readFileSync, writeFileSync } from "node:fs";

import MCR from "monocart-coverage-reports";

import { coverageOptions, LCOV_FILE, SERVER_COVERAGE_DIR } from "./coverage.mjs";

// Node only writes coverage on a clean exit; a killed server leaves nothing.
if (!existsSync(SERVER_COVERAGE_DIR) || readdirSync(SERVER_COVERAGE_DIR).length === 0) {
  throw new Error(`No server coverage in ${SERVER_COVERAGE_DIR}. Did next start exit cleanly?`);
}

// Without browser maps, client components silently drop out of the report (e.g. Sentry's
// deleteSourcemapsAfterUpload strips them, see next.config.ts).
const staticFiles = readdirSync(".next/static", { recursive: true });
if (!staticFiles.some((file) => String(file).endsWith(".js.map"))) {
  throw new Error("No browser source maps in .next/static. Was the build made with E2E_COVERAGE=1?");
}

const report = MCR(coverageOptions);
await report.addFromDir(SERVER_COVERAGE_DIR);
await report.generate();

// A bundle whose map holds only Next.js code (route templates etc.) has nothing left after
// sourceFilter, and MCR then reports the bundle itself (SF:.next/...). Drop those records.
const records = readFileSync(LCOV_FILE, "utf8").split(/^end_of_record\n/m);
const ours = records.filter((record) => record.startsWith("SF:src/") || record.includes("\nSF:src/"));
writeFileSync(LCOV_FILE, ours.map((record) => `${record}end_of_record\n`).join(""));
console.log(`e2e coverage: ${ours.length} files from src/ in ${LCOV_FILE}`);
