# Environments, accounts and runbooks

Where FitFinder runs, which accounts and secrets it depends on, and how to do the recurring manual steps. **No secret values belong in this file**, only names and where they live.

## Environments

| | Local | Preview | Production |
|---|---|---|---|
| Web | `pnpm dev` (http://localhost:3000) | Vercel preview, one per PR, URL posted on the PR | Vercel production: https://fitfinder-tau.vercel.app |
| Who can open it | you | only people logged in to Vercel (Vercel Authentication) | everyone |
| Supabase | local stack (`supabase start`, Docker) | `fitfinder-staging` | `fitfinder-prod` |
| Data | throwaway; `supabase db reset` re-applies migrations + `seed.sql` | test data, incl. the 10 seed shoes | real users, **no** seed data |
| Login emails | Mailpit, http://127.0.0.1:54324 | real email (Supabase built-in, rate-limited) | real email (Supabase built-in, rate-limited; own provider: #69) |

## Services and accounts

All accounts belong to the owner and use GitHub login.

| Service | What for | Identifiers |
|---|---|---|
| GitHub | code, issues, CI, branch protection (`ci-ok` required) | `felixhaegele/fitfinder` (public) |
| Supabase | Postgres, Auth, Storage, pgmq queue | org `ghmjttkdsvszvwzkunaj`; projects below |
| Vercel (Hobby plan, non-commercial) | hosts `web/` | team `felixhaegeles-projects`, project `fitfinder-prod` |
| SonarQube Cloud (free, public project) | code quality + coverage on every PR | org `felixhaegele`, project `felixhaegele_fitfinder` |
| Google Cloud | worker on Cloud Run Jobs (ADR 0012) | project: see `infra/terraform.tfvars` / `gcloud config get project`; region `europe-west1`; Terraform in [`infra/`](../infra/) |

### Supabase projects

| Project | Project ID | Region | Used by |
|---|---|---|---|
| `fitfinder-staging` | `xjusmksmnnywliwgspmf` | `eu-west-1` (Ireland) | Vercel previews |
| `fitfinder-prod` | `usdetilhsblzfnezwdvs` | `eu-west-1` (Ireland) | Vercel production |

- Region is permanent per project. Ireland is in the EU, which meets the GDPR / Swiss FADP requirement. (Frankfurt was the original plan; both ended up in Ireland, which is just as fine.)
- Free plan: at most 2 active projects, and projects **pause after 7 days without activity** (unpause with one click in the dashboard).
- The first staging project (`uhmeurzjiyvciifbpwzr`) was deleted by mistake on 2026-10-18 and recreated. **Supabase can't restore deleted projects.** Before deleting anything, check the name twice.

### Vercel

- One project, `fitfinder-prod`, root directory `web/`. It deploys via the Vercel GitHub integration: no deploy job and no Vercel token in our CI.
- Server functions run in `dub1` (Dublin, pinned in `web/vercel.json`), next to the Supabase projects. A response header `x-vercel-id: fra1::dub1::…` shows edge server and function region.
- Domains: production `fitfinder-tau.vercel.app`; previews `fitfinder-prod-git-<branch>-felixhaegeles-projects.vercel.app` and `fitfinder-prod-<hash>-felixhaegeles-projects.vercel.app`. The team alias kept the project's old name: `fitfinder-felixhaegeles-projects.vercel.app`.

## Where secrets and settings live

| Name | Kind | Where | Used by |
|---|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | public config | Vercel (Production → prod, Preview → staging); `web/.env.local` | web |
| `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | public config (RLS protects the data) | same as above | web |
| `SUPABASE_SECRET_KEY` | **secret**, bypasses RLS | `web/.env.local` (local dev key); **Vercel: still to be added as Secret** for account deletion (#65) | web server only (`web/src/lib/supabase/admin.ts`), e2e tests |
| `SONAR_TOKEN` | secret | GitHub repo secret (Actions) | CI `sonar` job |
| `supabase-secret-key-<env>`, `supabase-db-url-<env>` | secrets | Google Secret Manager (values added by hand, `infra/README.md`) | worker (Cloud Run Job) |
| `GCP_PROJECT_ID`, `GCP_REGION`, `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_DEPLOY_SERVICE_ACCOUNT`, `WORKER_IMAGE` | variables (not secret) | GitHub repo variables, from `terraform output` | `worker-deploy.yml` |
| `SUPABASE_ACCESS_TOKEN` | secret | GitHub Environments `staging` and `production` | `db-deploy.yml` |
| `SUPABASE_PROJECT_REF` | variable (not secret) | GitHub Environments `staging` / `production` | `db-deploy.yml` |
| Database passwords | secrets | owner's password manager only | direct `psql` access. Not needed by CI or the CLI: they log in through the access token |

Rules: `NEXT_PUBLIC_*` values end up in the browser bundle, so never give a secret that prefix. Secrets go in the dashboard or `gh secret set` from the owner's own terminal, never into chat, code or committed files. When adding a variable, also add it to `.env.example`.

## Runbooks

### Apply migrations to the hosted databases

**Normally CI does it** ([`.github/workflows/db-deploy.yml`](../.github/workflows/db-deploy.yml)):

1. **PR** that touches `supabase/migrations/`: the job `dry-run` lists what would be applied to staging. Nothing changes
2. **Merge to `main`**: `staging` applies the migrations
3. Then `production` waits for approval: Actions → the run → **Review deployments** → `production` → **Approve and deploy**

GitHub Environments: `staging` (any branch can read its secrets; the workflow only writes on `main`) and `production` (only `main`, requires the owner's approval). Settings → Environments.

Migrations only go forward: a rollback is a new migration that undoes the change. That's why staging always goes first.

**Manually** (e.g. the first setup, or to re-seed staging), from the repo root in the owner's terminal. After `supabase login`, the CLI logs in to the database through a temporary role ("Initialising login role..."); no database password is needed:

```sh
supabase link --project-ref xjusmksmnnywliwgspmf   # staging
supabase db push --include-seed                     # staging gets the seed
supabase link --project-ref usdetilhsblzfnezwdvs   # prod
supabase db push                                    # prod: no seed
```

`supabase link` is remembered in `supabase/.temp/project-ref` (gitignored). **Check which project the CLI is linked to before every `db push`.**

### Vercel environment variables

Vercel → `fitfinder-prod` → Settings → Environment Variables. Each key exists twice: once for **Production** (prod values), once for **Preview** (staging values, "All Preview Branches"). Use the **Config** type for public values, **Secret** for secrets. Development stays empty (local uses `web/.env.local`).

Variables are baked in **at build time**. After changing one, push a commit to rebuild previews. A manual "Redeploy" creates a new deployment but doesn't move the branch URL.

### Supabase Auth URL configuration

Per project: `https://supabase.com/dashboard/project/<project-id>/auth/url-configuration`. Magic links only redirect to allowed URLs; anything else falls back to the Site URL.

| Project | Site URL | Redirect URLs |
|---|---|---|
| prod | `https://fitfinder-tau.vercel.app` | `https://fitfinder-tau.vercel.app/**` |
| staging | `https://fitfinder-felixhaegeles-projects.vercel.app` | `https://fitfinder-prod-*-felixhaegeles-projects.vercel.app/**` |

Local values are in `supabase/config.toml` (`[auth]`).

### Login email templates

Magic links point to the app's `/auth/confirm` with a one-time token hash, so they work in any browser (#46). The text lives in [`supabase/templates/`](../supabase/templates/); locally `config.toml` loads it. **Hosted projects need it pasted into the dashboard**, per project: `https://supabase.com/dashboard/project/<project-id>/auth/templates`

| Template | Subject | Body |
|---|---|---|
| **Magic Link** | `Your FitFinder login link` | contents of `supabase/templates/magic_link.html` |
| **Confirm signup** | `Your FitFinder login link` | contents of `supabase/templates/confirmation.html` |

Until a project has the new templates, Supabase sends its default PKCE link. `/auth/confirm` accepts that too (it only works in the requesting browser), so login never breaks in between.

### SonarQube Cloud

- **Automatic Analysis is off** (project → Administration → Analysis Method). Our CI scanner sends the analysis instead, because only CI has the coverage reports. Both at once makes the CI scan fail.
- The CI `sonar` job skips itself (and passes) when `SONAR_TOKEN` is missing, e.g. on Dependabot PRs. A 3–5 s `sonar` job means it skipped.
- The Quality Gate ("Sonar way": 80 % coverage on new code) is reported as the separate check **"SonarCloud Code Analysis"**. It isn't required for merging.
- Code that the Playwright e2e tests cover is excluded from the coverage percentage (`sonar.coverage.exclusions` in `sonar-project.properties`). Counting e2e coverage instead: #62.

## Gotchas we hit

- **Supabase CLI in a non-interactive shell:** `supabase migration new` waits for SQL on stdin and hangs. Run CLI commands with `</dev/null`.
- **A local `supabase migration list` doesn't test the database password:** once logged in, the CLI uses a temporary login role through the access token. A wrong `SUPABASE_DB_PASSWORD` in CI kept failing while everything worked locally (#89). CI now uses the access token too.
- **Vercel env vars are build-time:** a preview built before the Preview variables existed fails on every request with "Missing environment variable NEXT_PUBLIC_SUPABASE_URL".
- **Redirects must be relative** in route handlers (`web/src/app/auth/callback/route.ts`): an absolute URL built from `request.nextUrl` can name a different host (localhost vs 127.0.0.1, or an internal proxy host), and the session cookie is then lost.
- **Next.js renders an empty `role="alert"`** (its route announcer) on every page. In Playwright, match alerts by text.
- **Labels around `<select>`** make every option part of the accessible name. Use `<label htmlFor>`.
- **Several Claude sessions work in parallel** (see CLAUDE.md "Parallel sessions"). Parallel PRs can pick the same next ADR number; whoever merges second renumbers.
