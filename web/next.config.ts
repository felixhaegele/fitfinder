import { withSentryConfig } from "@sentry/nextjs/config";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

// Sentry build step: source-map upload and release tagging. The release name
// defaults to VERCEL_GIT_COMMIT_SHA on Vercel. Without SENTRY_AUTH_TOKEN (local,
// CI, forks) source maps are neither generated nor uploaded, so the build works
// without any Sentry secrets. With the token, maps are uploaded to Sentry and then
// deleted from .next/, so they are never served publicly.
export default withSentryConfig(nextConfig, {
  org: process.env.SENTRY_ORG,
  project: process.env.SENTRY_PROJECT,
  authToken: process.env.SENTRY_AUTH_TOKEN,
  sourcemaps: {
    disable: !process.env.SENTRY_AUTH_TOKEN,
    deleteSourcemapsAfterUpload: true,
  },
  silent: !process.env.CI,
  telemetry: false,
});
