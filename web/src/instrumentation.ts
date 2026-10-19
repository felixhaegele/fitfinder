/**
 * Server-side instrumentation (Node.js and Edge runtimes). Next.js calls
 * `register()` once per server instance and `onRequestError` for every error
 * thrown while handling a request (Server Components, route handlers, server
 * actions, proxy). Without NEXT_PUBLIC_SENTRY_DSN, Sentry is never initialised
 * and `captureRequestError` does nothing.
 */
import * as Sentry from "@sentry/nextjs";

import { sentryOptions } from "@/lib/sentry";

export function register() {
  const options = sentryOptions({
    dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
    environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT,
    vercelEnv: process.env.VERCEL_ENV,
  });
  if (options) Sentry.init(options);
}

export const onRequestError = Sentry.captureRequestError;
