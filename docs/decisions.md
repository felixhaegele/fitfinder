# Decisions log

Smaller decisions that shaped the code but don't need a full ADR. Bigger ones are in [`adr/`](adr/). Newest first; add a row when you decide something a future reader would otherwise have to dig out of a PR.

| Date | Decision | Why | Where |
|---|---|---|---|
| 2026-10-19 | Magic links verify a token hash on `/auth/confirm` (works on any device); `/auth/confirm` also accepts PKCE codes | People request the link on a laptop and open it on their phone. Accepting both keeps login working while hosted templates are updated | `supabase/templates/`, #46 |
| 2026-10-19 | CI logs in to hosted databases through the access token (temporary login role), not a database password | A wrong password secret broke prod deploys while local tests passed; one secret less | `.github/workflows/db-deploy.yml`, #89 |
| 2026-10-18 | One Vercel project (`fitfinder-prod`): previews use staging Supabase, production uses prod | One build per push, private previews; a second project doubled builds and exposed a public staging site | #32, `docs/environments.md` |
| 2026-10-18 | Vercel Hobby plan, `*.vercel.app` domain for now | Non-commercial project; own domain comes with the email provider (#69) | #32 |
| 2026-10-18 | Vercel functions in `dub1` (Dublin) | Next to both Supabase projects (`eu-west-1`), EU for GDPR | `web/vercel.json` |
| 2026-10-18 | Staging gets `seed.sql`, prod doesn't | Seed is development data with approximate years | `docs/environments.md` |
| 2026-10-18 | Exclude e2e-tested glue code from Sonar's coverage percentage | Only unit tests count; pages and Supabase wiring are covered by Playwright. Proper e2e coverage: #62 | `sonar-project.properties`, #63 |
| 2026-10-18 | SonarQube Cloud project is public | The repo is public anyway; badges work | – |
| 2026-10-18 | Keep both photos (original upload and worker's cleaned copy) and show them side by side | Owner request; the raw image is kept for re-processing, the cleaned copy is what the server vouches for | `submissions.processed_image_path`, #30 |
| 2026-10-18 | Status page polls every 5 s instead of using Supabase Realtime | Results take ~1 min (ADR 0003); one less service to secure and test | `web/src/app/submissions/[id]/auto-refresh.tsx` |
| 2026-10-18 | Record insole condition (`new` / `used`), required, no default | Worn insoles compress and stretch; how to treat `used` is decided in #23 / #24 | #54 |
| 2026-10-18 | At most 20 submissions per user per 24 h | Protects storage and the queue from abuse; enforced in the DB | `*_submissions_daily_limit.sql`, #28 |
| 2026-10-18 | Photos go straight from the browser to Storage, not through our server | Phone photos exceed Vercel's ~4.5 MB request limit; Storage RLS restricts the folder | `web/src/app/upload/upload-form.tsx` |
| 2026-10-18 | Re-encode photos in the browser (orientation first, then strip metadata, max 4000 px) | Privacy (GPS) and smaller uploads; **not** a security check | `web/src/lib/prepare-photo.ts` |
| 2026-10-18 | Shoe picker is a plain list + "my shoe isn't listed" for now; curated pick-from-list later | MVP; duplicates and typos accepted until #45 | #28, #45 |
| 2026-10-18 | Logged-in users may add shoe models | An unknown shoe shouldn't block an upload | #11 |
| 2026-10-18 | Magic links use the default PKCE flow; cross-device links later | Simpler start; the limitation is tracked | #15, #46 |
| 2026-10-18 | Supabase's new key format (publishable / secret) instead of anon / service_role | Rotatable, the legacy keys are being phased out | `.env.example`, #15 |
| 2026-10-18 | Full login flow tested in CI (Playwright + local Supabase + Mailpit), separate `e2e` job | Real auth coverage without slowing lint/unit feedback | `.github/workflows/ci.yml` |
| 2026-10-18 | Worker triggered by a scheduled Cloud Run Job (option C); push-based wake-up later | Scale to zero at minimal complexity; users wait up to ~1 min | ADR 0003, #42 |
| 2026-10-18 | Classifier labels are `text` + check constraint, not enums | Enum values can't be removed as the classifier evolves | `*_core_schema.sql` |
| 2026-10-18 | Strike through n/a items in the PR checklist | Unchecked boxes read as unfinished work; ticking them would be false | `.github/pull_request_template.md` |
