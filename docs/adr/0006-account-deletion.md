# 0006. Delete accounts in a server action with the secret key: files first, then the user

- **Status:** Accepted
- **Date:** 2026-10-18

## Context

GDPR (Art. 17) and the Swiss FADP give users the right to have their data erased. A FitFinder user owns:

- an `auth.users` row (their login) and a `profiles` row,
- `submissions` with `measurements` and `classifications`,
- photos in the private `insoles` bucket under `<user_id>/` (the upload and, from #29, the worker's processed copy under `<user_id>/processed/`),
- possibly `shoe_models` they added (`created_by`).

Constraints:

1. A user's own session can't delete their auth user. That needs the Auth **admin** API, which needs the **secret key** (formerly "service-role key"). That key bypasses Row-Level Security, so it must never reach the browser.
2. Supabase blocks deleting storage objects with SQL: `storage.objects` only holds metadata, and deleting a row there would leave the actual file behind in the object store. Files must be removed through the Storage API, which deletes both.
3. Supabase refuses to delete a user who still owns storage objects.

## Decision

We will delete accounts in a **Next.js server action** (`web/src/app/account/delete/actions.ts`) using a **server-only admin client** (`web/src/lib/supabase/admin.ts`) built from `SUPABASE_SECRET_KEY`. The user id comes from the verified session (`getClaims()`), never from the request, so users can only delete themselves. The user must type `DELETE` to confirm.

Order of operations (`web/src/lib/account-deletion.ts`):

1. **Purge files**: list everything under `insoles/<user_id>/` recursively and remove it in batches.
2. **Delete the auth user** (hard delete). Foreign keys cascade: `auth.users` → `profiles` → `submissions` → `measurements` → `classifications`. `shoe_models.created_by` is set to null: the catalogue entry stays (it's shared data about a shoe, not about the person), but the link to the person is gone. A pgTAP test guards that every foreign key into user-owned rows cascades or sets null.
3. **Purge files again**, to catch a processed copy the worker may have written between steps 1 and 2.

Deletion is **immediate**: no grace period, no soft delete.

**Partial failure.** Steps 1 and 2 are idempotent, and the action stops at the first error and asks the user to try again:

- Step 1 fails halfway: some photos are gone, the account and its rows still exist. Retrying finishes the job. (Nothing is left that the user can't reach or retry.)
- Step 2 fails: all photos are gone, the account and rows still exist. Retrying purges nothing and deletes the user.
- Step 3 fails: the account is already deleted, so the user sees success; the error is logged for the operator. A leftover file sits in a folder nobody can access any more and needs a manual cleanup.

Doing it the other way round (user first, then files) would turn every failure after step 2 into files that belong to nobody and can't be found from the app any more, which is exactly the kind of leftover the law asks us to avoid.

## Alternatives considered

- **Supabase Edge Function** called from the browser: same logic, but another runtime to deploy, test and keep secrets in. The web server already runs server-side code with access to secrets.
- **Postgres function (security definer) that deletes `auth.users`**: handles the rows, but can't remove the files (constraint 2), so it would still need a second step outside the database.
- **Queue a deletion job for the worker**: more robust against timeouts for users with many files, but the worker doesn't exist yet in production and the user would have to wait without feedback. Fine to revisit if users ever have thousands of files.
- **Soft delete / grace period** (e.g. 30 days to undo): friendlier against accidents, but needs a scheduled purge job and means data is kept after the user asked for erasure. Open question for the owner; immediate deletion is the simplest compliant default.

## Consequences

- The web server now holds the secret key. It must be set as a **server-side** environment variable (never `NEXT_PUBLIC_`), and `admin.ts` imports `server-only` so a client-side import fails the build. Any future admin-client use should be just as narrow.
- The worker (#29) must cope with a submission disappearing mid-job: if the row is gone when it writes results, it should delete any file it just uploaded and archive the message.
- Backups: deleted data can still exist in Supabase's database backups until they rotate out. That's normal and accepted under GDPR as long as backups aren't restored selectively, but the privacy notice should mention it.
