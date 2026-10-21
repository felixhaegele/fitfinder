// V8 coverage of the e2e run (`pnpm test:e2e:coverage`, issue #62).
//
// Two sources, both V8's built-in coverage (byte ranges of executed JS, no instrumentation):
// - browser: Playwright's page.coverage records every test page (see fixtures.ts)
// - server: `next start` runs with NODE_V8_COVERAGE, so Node writes its coverage to
//   SERVER_COVERAGE_DIR when it exits
// monocart-coverage-reports (MCR) maps the bundled .next/ JS back to src/ through the
// source maps the coverage build emits (next.config.ts) and writes LCOV.
//
// Plain JS (not TS) because coverage-report.mjs runs under plain `node` too.
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";

export const E2E_COVERAGE = process.env.E2E_COVERAGE === "1";

export const SERVER_COVERAGE_DIR = "coverage-e2e/server-raw";

// Own file name (not lcov.info), so CI can tell it apart from Vitest's report.
export const LCOV_FILE = "coverage-e2e/report/lcov-e2e.info";

/**
 * Only our app's bundles, and only those with a source map: browser chunks from
 * /_next/static, server chunks from .next/server. Skips Node internals, node_modules and
 * Playwright's scripts. A bundle without a map can't be traced back to src/.
 * @param {{ url: string, source?: string }} entry
 */
const isMappedAppBundle = ({ url, source }) => {
  if (url.includes("/_next/static/")) return !!source?.includes("sourceMappingURL=");
  if (url.startsWith("file:") && url.includes("/.next/server/")) {
    return existsSync(`${fileURLToPath(url)}.map`);
  }
  return false;
};

/** @type {import("monocart-coverage-reports").CoverageReportOptions} */
export const coverageOptions = {
  name: "FitFinder e2e coverage",
  outputDir: "coverage-e2e/report",
  reports: [["lcovonly", { file: "lcov-e2e.info" }]],
  entryFilter: isMappedAppBundle,
  // Server maps list sources relative to web/ ("src/lib/auth.ts"); browser maps use
  // Turbopack's own scheme ("turbopack:///[project]/src/lib/auth.ts"). Make both relative
  // to web/: the same SF: paths as Vitest's lcov, so Sonar (after CI's rewrite to
  // web/src/...) treats both reports alike.
  sourcePath: (filePath) => filePath.replace(/^.*\[project\]\//, ""),
  // Bundles also contain Next.js and library code: keep only our sources.
  sourceFilter: (sourcePath) =>
    /^src\/.+\.tsx?$/.test(sourcePath) && sourcePath !== "src/lib/database.types.ts",
};
