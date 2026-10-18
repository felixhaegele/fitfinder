# supabase

Supabase CLI project: database schema (`migrations/`), local seed data (`seed.sql`), database tests (`tests/database/`) and local stack settings (`config.toml`).

## Prerequisites

- [Supabase CLI](https://supabase.com/docs/guides/local-development/cli/getting-started) (`brew install supabase/tap/supabase`)
- Docker. The CLI runs Postgres, Auth, Storage etc. as containers. On macOS, [OrbStack](https://orbstack.dev) or Docker Desktop.

Run all commands from the **repo root**. The CLI looks for `./supabase/`.

## Daily use

```sh
supabase start        # start the local stack; prints URLs and keys
supabase status       # print them again
supabase stop         # stop (data is kept in a Docker volume)
supabase db reset     # drop the local DB, re-apply all migrations + seed.sql
```

Local URLs after `supabase start`:

| What | URL |
|---|---|
| API (what the web app talks to) | http://127.0.0.1:54321 |
| Postgres | `postgresql://postgres:postgres@127.0.0.1:54322/postgres` |
| Studio (admin UI) | http://127.0.0.1:54323 |
| Mailpit (catches magic-link emails) | http://127.0.0.1:54324 |

Copy the **publishable key** and **secret key** from `supabase status` into `web/.env.local` (see `.env.example`). Local keys are well-known dev values, but treat the habit seriously: hosted keys are real secrets.

## Schema changes

```sh
supabase migration new <name>   # creates migrations/<timestamp>_<name>.sql
supabase db reset               # apply it locally
supabase gen types typescript --local > web/src/lib/database.types.ts
```

- Never edit a migration that has already been applied (merged to `main`). Add a new one instead.
- Every table gets RLS enabled and explicit policies, in the same migration that creates it.
- Commit the regenerated `web/src/lib/database.types.ts` with the migration. CI regenerates it and fails if it differs.
- `seed.sql` is for local development only. Tests must not rely on it: they create their own rows with made-up names.

## Tests

```sh
supabase test db   # runs tests/database/*.test.sql with pgTAP
supabase db lint   # static checks on the schema (plpgsql_check)
```

Tests are SQL files using [pgTAP](https://pgtap.org). Each one runs inside a transaction that is rolled back, so tests don't leave data behind. `00_rls_enabled.test.sql` fails if any table in `public` has RLS turned off. RLS policy tests for each table go next to it.

CI runs the same commands on every PR that touches `supabase/**`.

## Region

`config.toml` only configures the **local** stack. The hosted projects (staging/prod, #34) must be created in an **EU region** (e.g. Frankfurt `eu-central-1`) for GDPR / Swiss FADP. The region can't be changed after creation.
