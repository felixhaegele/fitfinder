# 0007. Track errors with Sentry (EU region), scrubbing personal data before it leaves the app

- **Status:** Accepted
- **Date:** 2026-10-18

## Context

Once the web app (Vercel) and the worker (Cloud Run) are live, we need to find out about crashes without waiting for a user to complain. Logs alone are hard to search and don't group repeated errors. Constraints:

1. **Privacy (GDPR / Swiss FADP).** Error reports can easily carry personal data: emails in messages, Supabase auth cookies and `Authorization` headers, magic-link codes in URLs, signed storage URLs (their path holds the user id and the URL holds a token), request bodies (uploaded photos) and, in Python, the local variables of every stack frame (image arrays, DB URLs).
2. **No secrets needed to build or test.** Local dev, CI and forks have no Sentry credentials, and tests must never send events.
3. **Readable stack traces** for the minified browser bundle, without publishing our source maps.

## Decision

We will use **Sentry** (hosted, **EU data region**), with one Sentry project per deployable: `web` and `worker`.

- **Web:** `@sentry/nextjs`, initialised from Next.js's `instrumentation.ts` (server and edge, plus `onRequestError` for server errors) and `instrumentation-client.ts` (browser). The shared options and the scrubbing live in `web/src/lib/sentry.ts`.
- **Worker:** `sentry-sdk` with its FastAPI integration, initialised by `init_sentry()` in `worker/app/observability.py`. Every worker entrypoint calls it.
- **Off without a DSN.** With no DSN set, the SDK is never initialised. Tests also clear the DSN, and the Playwright build blanks it.
- **Privacy by default.**
  - `sendDefaultPii` / `send_default_pii` is false.
  - No request bodies or cookies. Headers are kept from an allowlist only (`user-agent`, `content-type`, `accept`, `accept-language`).
  - No Python local variables. Attachments are dropped.
  - No Session Replay and no feedback widget. Performance tracing is off.
  - A `beforeSend` / `before_send` hook walks the whole event:
    - replaces emails, JWTs, signed storage paths, query-string values and connection-string passwords;
    - blanks values under keys like `cookie`, `token`, `authorization`, `email`.
- **Environment and release tags.**
  - Environment is `development` / `preview` / `production`. The web app takes it from Vercel's `VERCEL_ENV`; the worker takes it from `SENTRY_ENVIRONMENT`.
  - Release is the git SHA: `VERCEL_GIT_COMMIT_SHA` for the web app, and `SENTRY_RELEASE`, set at deploy time (#33), for the worker.
- **Source maps** are uploaded at build time only when `SENTRY_AUTH_TOKEN` is set, and deleted from the build output afterwards, so they're never served. Without the token, no source maps are generated.

## Alternatives considered

- **Self-hosted Sentry / GlitchTip:** full data control, but another service to run and patch. That's too much operations work for a learning project at this stage.
- **Vercel / Cloud Run logs only:** no grouping, no alerts, no browser errors, and the web app and worker are hard to correlate.
- **OpenTelemetry to a generic backend:** more flexible, but more setup for the same result. Sentry's SDKs are built for exactly this.

## Consequences

- Errors from both apps arrive grouped in one place, tagged with environment and commit.
- The scrubbing rules exist twice (TypeScript and Python). They're small and both have unit tests, but a change to one must be mirrored in the other.
- Scrubbing is a safety net, not a licence: still don't put personal data in error messages or `extra`.
- Sentry is a processor of (scrubbed) technical data. The privacy policy should list it once one exists.
- The owner must pick the **EU region** when creating the Sentry organisation. Sentry doesn't move an existing organisation to another region.
