# 0011. Publish shoe fit as aggregates from security-definer functions, never as rows

- **Status:** Accepted
- **Date:** 2026-10-19

## Context

v1 needs a public page where anyone, logged in or not, can browse and search shoes by fit (#92). The fit data comes from other people's uploads: `submissions`, `measurements` and `classifications`. RLS limits each of those tables to its owner, and that rule must stay.

The browser and our server components talk to Postgres through PostgREST, using the publishable key (ADR 0002). So whatever we expose to `anon` can be read by anyone, through any query PostgREST allows, not only through our pages.

The owner decided (2026-10-19) that a shoe is shown from **one** measured submission. With one upload, any per-person field next to the numbers (user, date, photo path, outline) would identify that upload. So the public data must be **shoe-level only**.

## Decision

We will add two read-only SQL functions, callable by `anon` and `authenticated`:

- `public.shoe_fit_summaries(search text)`: one row per shoe model with at least one measured submission. Columns: shoe model id, brand, model, year, number of measured submissions, median length, ball, heel and arch width (mm), and the most common `width_class`, `arch_class`, `toe_box_shape` and `toe_shape`. `search` matches every word against "brand model year", case-insensitive, as plain text (no wildcards).
- `public.shoe_fit_by_size(shoe_model uuid)`: the same numbers for one shoe, grouped by size and size system. The `/shoes/[id]` page shows them under the overall summary.

Rules for both:

- Only submissions with status `done` count. Per submission, only the **newest** measurement (by `created_at`) and the newest classification of that measurement are used, so re-processing with a new `pipeline_version` / `classifier_version` replaces old results instead of counting twice. We don't sort by the version strings, because text sorts `'1.10.0'` before `'1.9.0'`.
- A done submission that has a measurement but no classification yet still counts and adds to the medians. It just adds nothing to the most-common labels. If no submission of a shoe has a classification, those labels are null.
- With a tie, "most common" (`mode()`) takes the first value in alphabetical order. With one or two uploads that is effectively arbitrary; the page shows the count so readers can judge.
- The functions are `security definer` with `search_path = ''` and fully qualified names. Execute is revoked from `public` (Postgres grants it to everyone by default) and granted only to `anon` and `authenticated`.
- The shared "newest result per done submission" query lives in a view in a new, unexposed `private` schema. PostgREST only serves the schemas listed in `supabase/config.toml` (`public`, `graphql_public`), and `anon` / `authenticated` get no grants on `private`.

The web reads the functions with `supabase.rpc(...)` and applies the class filters with `.eq()`, which PostgREST encodes safely.

## Alternatives considered

- **A view with `security_invoker = false`** (the Postgres default). A view like that also runs with its owner's rights and bypasses the RLS of the tables underneath. We didn't use it because:
  - A view is a table to PostgREST, so its output is easy to widen by accident (`select *`, a new column).
  - It can't pin `search_path` or take a search parameter.
  - Supabase's security advisor reports such views as an error ("Security Definer View"), which would hide real findings.
  The function has an explicit, typed list of output columns, and pgTAP checks that list.
- **Open the tables to anon with an RLS policy for done submissions.** That would publish every row, including `user_id`, image paths, dates and outlines. Column grants could hide some columns, but row-level data at n=1 would still be per-person. Rejected.
- **A materialized view or summary table refreshed by the worker.** Faster at scale, but it needs refresh logic and can go stale. At v1 volumes, aggregating on read is fine. If it gets slow, we can switch to this behind the same function signature.
- **A minimum count (e.g. hide shoes with fewer than 3 uploads).** This is better for privacy, but the owner chose 1 so that the site has content early. Because nothing per-person is exposed, the remaining risk is that someone who knows a person uploaded a given shoe can read that insole's measurements. Those are measurements of a shoe, not of the person.

## Consequences

- RLS on `submissions`, `measurements` and `classifications` is unchanged: anon still can't read a single row. Only the aggregate crosses that boundary, and only the columns listed above. `supabase/tests/database/95_shoe_fit_summary.test.sql` proves both, plus that rejected, failed and queued submissions and older result versions don't count.
- Any new column in these functions is a privacy decision. It must stay shoe-level, and the pgTAP column-list test has to be updated deliberately.
- Every page view aggregates over all done submissions. That's fine for v1; revisit it (materialized view, indexes) when it shows up in timings.
- Crowd data is now public, so fake uploads can skew a shoe's numbers. With few uploads per shoe this is easy. Outlier handling stays a v2 topic (`docs/security.md`).
