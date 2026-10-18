"use client";

/**
 * Last-resort error page for errors thrown while rendering the root layout.
 * Reports the error to Sentry (a no-op without a DSN) and offers a retry.
 * It renders its own document without globals.css, so it stays unstyled.
 */
import * as Sentry from "@sentry/nextjs";
import { useEffect } from "react";

export default function GlobalError({
  error,
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  useEffect(() => {
    Sentry.captureException(error);
  }, [error]);

  return (
    <html lang="en">
      <body>
        <h1>Something went wrong</h1>
        <button type="button" onClick={() => retry()}>
          Try again
        </button>
      </body>
    </html>
  );
}
