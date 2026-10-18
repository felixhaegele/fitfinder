"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

const INTERVAL_MS = 5_000;

/**
 * Re-fetches the page's server data every few seconds while the submission is still
 * queued or processing. Rendered only in that state, so it stops on its own once the
 * status is final. Polling is enough here: results take about a minute (ADR 0003).
 */
export function AutoRefresh() {
  const router = useRouter();
  useEffect(() => {
    const timer = setInterval(() => router.refresh(), INTERVAL_MS);
    return () => clearInterval(timer);
  }, [router]);
  return null;
}
