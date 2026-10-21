# 0011. Run the worker as Cloud Run Jobs, managed with Terraform, deployed via Workload Identity Federation

- **Status:** Accepted
- **Date:** 2026-10-21

## Context

The measurement worker (Python + OpenCV, `python -m app.jobs.drain`) needs somewhere to run. ADR 0003 chose to start it about once a minute; it drains the queue and exits. It must run in the EU, cost close to nothing when idle, and get the Supabase secret key and database URL without them leaking. Supabase itself can't run it: Edge Functions are Deno/TypeScript with tight CPU limits, and Postgres doesn't allow Python (ADR 0002).

The project is also a learning project: infrastructure as code and keyless deploys are goals in themselves.

## Decision

We will run the worker on **Google Cloud Run Jobs** in **`europe-west1`** (Belgium, closest to Supabase's `eu-west-1`), in **one GCP project** with one job per environment (`fitfinder-drain-staging`, `fitfinder-drain-prod`):

- **Cloud Scheduler** starts prod every minute and staging every 5 minutes (staging only gets test uploads; this keeps costs down). A run still going at the next tick is fine: pgmq hides a message while one worker has it.
- **Secret Manager** holds the secret key and database URL per environment. Each environment's worker has its own service account and may read only its own secrets. Values are added by hand, never in Terraform code or state.
- **Terraform** in `infra/` describes all of it. State lives in a versioned Cloud Storage bucket. The owner runs `plan` / `apply`; CI only checks formatting and validity.
- **GitHub Actions deploys new images** via **Workload Identity Federation**: GitHub's OIDC token is exchanged for a short-lived token of a deployer service account. Google accepts only tokens from this repo's `main` branch. The deployer may push to our registry and update the two jobs, nothing else. Production waits for the owner's approval (GitHub Environment `production`).
- A **budget alert** emails the billing admins at 50 / 90 / 100 % of a small monthly budget.

## Alternatives considered

- **Fly.io / Railway / Render:** simpler to set up, but no built-in "start every minute, then exit" (Fly's scheduler is hourly at best), so either an always-on machine (a few dollars a month) or the HTTP wake-up of #42 first. Deploys use a long-lived API token. Less to learn, which here is a downside.
- **Cloud Run *service* with min-instances 1 that polls:** always on, so it always costs money (ADR 0003, option A).
- **Two GCP projects (staging / prod):** stronger isolation, double the setup. Separate service accounts and secrets per environment are enough for now.
- **A JSON service-account key in GitHub secrets:** works everywhere, but it's a long-lived credential that can leak and has to be rotated by hand. WIF avoids it.
- **Terraform applied by CI:** the next step, but it needs a strongly privileged identity in CI. Later, as its own issue.

## Consequences

- Google Cloud is the third provider, with its own account, billing and console. Setup is a documented one-off (`infra/README.md`).
- The worker connects to Postgres through Supabase's **session pooler** (Cloud Run has no IPv6), so its database URL contains the database password. It lives only in Secret Manager; resetting the password means adding a new secret version.
- Schedules start paused (`schedules_enabled = false`) until the first image is deployed, because the jobs are created with a placeholder image.
- Users wait up to ~1 minute (prod). Making it faster is #42.
