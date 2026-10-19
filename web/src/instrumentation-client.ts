/**
 * Browser instrumentation: runs before React hydrates. No Session Replay and no
 * user-feedback widget are added, only error reporting. Without
 * NEXT_PUBLIC_SENTRY_DSN, Sentry is never initialised.
 */
import * as Sentry from "@sentry/nextjs";

import { sentryOptions } from "@/lib/sentry";

const options = sentryOptions({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT,
  vercelEnv: process.env.NEXT_PUBLIC_VERCEL_ENV,
});
if (options) Sentry.init(options);

// Navigation breadcrumbs (their URLs are scrubbed by beforeSend).
export const onRouterTransitionStart = Sentry.captureRouterTransitionStart;
