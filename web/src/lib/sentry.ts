/**
 * Shared Sentry settings for the browser, Node.js and Edge runtimes.
 *
 * Kept free of `@sentry/nextjs` runtime imports so it can be unit-tested and so
 * the privacy rules live in one place. The instrumentation files read the env
 * vars (they must be written out literally, `process.env.NEXT_PUBLIC_...`, for
 * Next.js to inline them into the browser bundle) and pass them in here.
 *
 * Privacy (GDPR / Swiss FADP): no default PII, no request bodies, cookies or
 * auth headers, and every string in an event is scrubbed of emails, JWTs,
 * signed storage paths and query-string values before it leaves the app.
 * The worker applies the same rules in worker/app/observability.py.
 */
import type { ErrorEvent, Event, EventHint } from "@sentry/nextjs";

const FILTERED = "[Filtered]";

/** Request headers we keep; everything else (cookie, authorization, apikey, referer, ...) is dropped. */
const SAFE_HEADERS = new Set(["accept", "accept-language", "content-type", "user-agent"]);

/** Object keys whose values are never sent, wherever they appear in an event. */
const SENSITIVE_KEY =
  /cookie|authorization|password|passwd|secret|token|api[-_]?key|session|email|signature/i;

const STRING_RULES: ReadonlyArray<[RegExp, string]> = [
  // Emails, e.g. in an error message from the auth flow.
  [/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g, "[email]"],
  // JWTs: Supabase access tokens and the token in signed storage URLs.
  [/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]*)?/g, "[jwt]"],
  // Signed storage URLs: the object path contains the user id and file name.
  [/(\/storage\/v1\/object\/sign\/)[^?#\s"']+/g, `$1${FILTERED}`],
  // Every query-string value (magic-link `code` / `token_hash`, signed-URL `token`, ...).
  // Keeps the parameter names, which are what you need for debugging.
  [/([?&][^=&#\s"'?]+=)[^&#\s"']*/g, `$1${FILTERED}`],
];

export function scrubString(value: string): string {
  return STRING_RULES.reduce((s, [pattern, replacement]) => s.replace(pattern, replacement), value);
}

const MAX_DEPTH = 12;

function scrubValue(value: unknown, depth: number): unknown {
  if (typeof value === "string") return scrubString(value);
  if (value === null || typeof value !== "object" || depth > MAX_DEPTH) return value;
  if (Array.isArray(value)) return value.map((item) => scrubValue(item, depth + 1));
  return Object.fromEntries(
    Object.entries(value).map(([key, item]) => [
      key,
      SENSITIVE_KEY.test(key) ? FILTERED : scrubValue(item, depth + 1),
    ]),
  );
}

/** Removes personal data from an event before it is sent. Used as `beforeSend`. */
export function scrubEvent<T extends Event>(event: T): T {
  const { request, user } = event;
  if (request) {
    delete request.data;
    delete request.cookies;
    // Stored without the leading `?`, so the query rule below wouldn't catch its first value.
    // The URL keeps the (scrubbed) query string anyway.
    delete request.query_string;
    if (request.headers) {
      request.headers = Object.fromEntries(
        Object.entries(request.headers).filter(([name]) => SAFE_HEADERS.has(name.toLowerCase())),
      );
    }
  }
  if (user) {
    // Only an opaque id (if we ever set one); never email, IP address or username.
    event.user = user.id === undefined ? undefined : { id: user.id };
  }
  return scrubValue(event, 0) as T;
}

export function beforeSend(event: ErrorEvent, hint: EventHint): ErrorEvent {
  // Never upload attachments (e.g. a user's insole photo).
  if (hint.attachments) hint.attachments.length = 0;
  return scrubEvent(event);
}

export type SentryEnv = {
  dsn: string | undefined;
  environment: string | undefined;
  vercelEnv: string | undefined;
};

/**
 * Options for `Sentry.init`, or `null` when no DSN is configured. Without a DSN
 * Sentry is not initialised at all, so local dev, CI and tests send nothing.
 */
export function sentryOptions({ dsn, environment, vercelEnv }: SentryEnv) {
  if (!dsn) return null;
  return {
    dsn,
    // development / preview / production. Vercel sets VERCEL_ENV per deployment.
    environment: environment || vercelEnv || "development",
    // The release (git SHA) is injected at build time by withSentryConfig from
    // VERCEL_GIT_COMMIT_SHA, so it matches the uploaded source maps.
    sendDefaultPii: false,
    // Errors only: no tracesSampleRate, so performance tracing stays off. Spans
    // would carry URLs too; if we enable it later, transactions are scrubbed below.
    beforeSend,
    beforeSendTransaction: scrubEvent,
  };
}
