# Security and privacy model

How FitFinder protects user data, what it trusts and what it doesn't. Details of individual decisions are in the ADRs and the linked issues.

## Principles

1. **The browser talks to Postgres directly** (ADR 0002), so **Row-Level Security is the access control**. Every table has RLS with explicit policies; `supabase/tests/database/00_rls_enabled.test.sql` fails CI if any table in `public` doesn't.
2. **Never trust the client.** Anything the browser does (validation, photo re-encoding) is a convenience. The rules are enforced again in the database, in server actions or in the worker.
3. **Least privilege.** Users get the narrowest grants that work; only server-side code holds the secret key; only the worker writes results.
4. **Privacy by default:** EU hosting, private photos, explicit consent, real deletion.

## Who can do what

| | Anonymous | Logged-in user | Worker / server (secret key) |
|---|---|---|---|
| `shoe_models` | read | read, add (not edit/delete) | everything |
| `profiles` | – | read own | everything |
| `submissions` | – | read, insert, delete **own**; can't update | everything (sets status, results) |
| `measurements`, `classifications` | – | read own (via the submission) | write |
| Photos (`insoles` bucket, private) | – | upload, read, delete in **own folder** `<user_id>/`; can't overwrite | everything |
| pgmq queue | – | – (schema not exposed) | read / archive |

On top of RLS, **column grants** stop users from setting `status`, `user_id`, `created_by`, `processed_image_path` or timestamps at all, so a policy mistake alone doesn't open them up. pgTAP tests in `supabase/tests/database/` cover each rule for anonymous, user A, user B and the worker.

## Uploads (threat model)

The browser re-encodes photos (EXIF orientation applied, all metadata dropped, max 4000 px) before uploading them straight to Storage. That protects privacy for normal users, but **an attacker can skip our page** and call the Storage API with their own token. So:

| Risk | Protection |
|---|---|
| Writing into someone else's folder, overwriting a photo | Storage RLS (own folder only, no update policy); `image_path` / `processed_image_path` check constraints |
| Huge or obviously wrong files | Bucket limits: 10 MiB, JPEG/PNG/WebP. Note: the type check trusts the client's declared content type |
| Crafted image attacking the decoder, decompression bombs | **Worker** (#29): check magic bytes, cap pixels before decoding, time limit per job, non-root container, current OpenCV/Pillow |
| A disguised file (e.g. HTML) delivered back to a browser | Only the owner ever sees their files, via short-lived signed URLs (10 min) from the Supabase domain, shown in `<img>` |
| Metadata (GPS) kept by skipping the browser step | Worker re-encodes on the server too and stores a separate cleaned copy (`processed_image_path`); the status page shows both copies |
| Mass uploads (storage cost, queue flooding) | DB trigger: at most **20 submissions per user per 24 h** (error `P0429`) |
| Photos without a submission (upload worked, saving failed) | Removed with account deletion; periodic cleanup still open |
| Fake insoles poisoning crowd data | Not a v1 risk (nothing aggregated yet); outlier detection in v2 |

The full worker checklist is on #29.

## Authentication

- Supabase Auth, magic links only (no passwords). The link carries a one-time token hash that `/auth/confirm` verifies (`verifyOtp`), so it works on any device (#46); it's valid once, for one hour. Like any magic link, whoever has the email can log in. Known downside: email security scanners that open links automatically can use up the token, and the user then requests a new link.
- `web/src/proxy.ts` refreshes the session on every request; access checks happen in `getUser()` / `requireUser()` (`web/src/lib/auth.ts`), which verify the token with `getClaims()` and always run at request time.
- `safeNextPath()` (`web/src/lib/redirect.ts`) only allows same-site paths after login, so `?next=` can't be used as an open redirect.
- Hosted Supabase only redirects magic links to allow-listed URLs (see `docs/environments.md`).

## Secrets

- Public by design: the Supabase URL and the **publishable key** (`NEXT_PUBLIC_*`). RLS protects the data.
- Secret: `SUPABASE_SECRET_KEY` (bypasses RLS). Only in `web/src/lib/supabase/admin.ts` (`server-only`), the worker and tests; never `NEXT_PUBLIC_`. Database passwords, `SONAR_TOKEN` and access tokens live in dashboards, GitHub secrets or the owner's password manager.
- Never in code, committed files or chat. `.env.local` is gitignored; `.env.example` lists every variable without values.
- Where each one lives: `docs/environments.md`.

## Privacy (GDPR / Swiss FADP)

- **EU hosting:** Supabase `eu-west-1` (Ireland), Vercel functions `dub1` (Dublin). The worker on Cloud Run must also run in an EU region (#33).
- **Consent:** a required checkbox on every upload; `consent_at` is set by the server.
- **Metadata:** removed in the browser and again by the worker.
- **Deletion:** users can delete single submissions and their whole account. Account deletion removes all photos (including `processed/`) and all rows, immediately (ADR 0006).
- **Email:** before real users, login emails need our own provider with an EU region and a DPA (#69).

## Open items

- Worker-side upload checks (#29)
- Cleanup of photos without a submission
- `SUPABASE_SECRET_KEY` in Vercel (Secret type), required for account deletion in production
- Own email provider (#69)
