# infra

Terraform for Google Cloud: where the measurement worker runs (ADR 0011).

```
Cloud Scheduler ──► Cloud Run Job fitfinder-drain-<env> ──► Supabase (queue, photos, results)
                      image from Artifact Registry, secrets from Secret Manager
GitHub Actions ──(Workload Identity Federation, no stored key)──► push image, update job
```

| File | What |
|---|---|
| `main.tf` | APIs to enable, shared locals |
| `registry.tf` | Artifact Registry for worker images (keeps the newest 20) |
| `jobs.tf` | One Cloud Run Job + one Cloud Scheduler job per environment |
| `secrets.tf` | Secret Manager *containers* (values are added by hand, never in Terraform) |
| `service_accounts.tf` | Identities and their (minimal) permissions |
| `github_oidc.tf` | Workload Identity Federation: only this repo's `main` can deploy |
| `budget.tf` | Email alerts at 50 / 90 / 100 % of the monthly budget |
| `variables.tf`, `outputs.tf`, `versions.tf` | Inputs, values for CI, provider and state backend |

**What Terraform is:** the cloud resources are described as code. `terraform plan` shows what would change; `terraform apply` makes it so. Terraform remembers what it created in a *state* file, which lives in a Cloud Storage bucket (not on a laptop).

Day to day: change a `.tf` file in a PR → CI checks formatting and validity → after merging, the owner runs `terraform plan` and `terraform apply` from this folder. CI never applies Terraform; it only deploys new worker **images** (`.github/workflows/worker-deploy.yml`).

## One-time setup (owner)

Prerequisites: `brew install --cask google-cloud-sdk` and `brew install hashicorp/tap/terraform`.

### 1. Google Cloud account, billing, project

1. Sign in at https://console.cloud.google.com with your Google account and accept the terms.
2. Create a **billing account** (Billing → Create account; needs a credit card). Billing must exist even within the free tier.
3. In your terminal:

```sh
gcloud auth login                         # opens the browser
gcloud billing accounts list              # note the ACCOUNT_ID, e.g. 012345-6789AB-CDEF01

PROJECT=fitfinder-$RANDOM                 # project IDs are global; note the result
gcloud projects create $PROJECT --name="FitFinder"
gcloud billing projects link $PROJECT --billing-account=<ACCOUNT_ID>
gcloud config set project $PROJECT
```

### 2. Login for Terraform and the state bucket

```sh
gcloud auth application-default login     # Terraform uses this login
gcloud auth application-default set-quota-project $PROJECT
gcloud services enable storage.googleapis.com cloudresourcemanager.googleapis.com serviceusage.googleapis.com

gcloud storage buckets create gs://$PROJECT-tfstate \
  --location=europe-west1 --uniform-bucket-level-access --public-access-prevention
gcloud storage buckets update gs://$PROJECT-tfstate --versioning   # keeps old state versions
```

### 3. Create everything with Terraform

```sh
cd infra
cp terraform.tfvars.example terraform.tfvars   # fill in project_id and billing_account_id
terraform init -backend-config="bucket=$PROJECT-tfstate"
terraform plan        # read it: around 35 resources to add, nothing to destroy
terraform apply       # type "yes"
```

### 4. Secret values

Per environment, two secrets. `read -rs` asks without showing the value and keeps it out of your shell history; `printf '%s'` adds no newline.

| Secret | Value | Where to get it |
|---|---|---|
| `supabase-secret-key-<env>` | `sb_secret_…` | Supabase → project → Project Settings → API Keys → Secret keys |
| `supabase-db-url-<env>` | `postgresql://postgres.<project-id>:<password>@aws-0-eu-west-1.pooler.supabase.com:5432/postgres` | Supabase → project → **Connect** → **Session pooler** (Cloud Run has no IPv6, so not the direct connection). Put in the database password; **URL-encode special characters** in it (e.g. `@` → `%40`) |

```sh
for name in supabase-secret-key-staging supabase-db-url-staging \
            supabase-secret-key-prod    supabase-db-url-prod; do
  echo "Value for $name:"; read -rs value
  printf '%s' "$value" | gcloud secrets versions add "$name" --data-file=-
  unset value
done
```

Changing a value later: add a new version the same way. Jobs read `latest` on their next start.

### 5. GitHub variables for the deploy workflow

Not secrets; Claude can set them from the output:

```sh
terraform output
gh variable set GCP_PROJECT_ID --body "<value>"   # same for GCP_REGION, GCP_WORKLOAD_IDENTITY_PROVIDER,
                                                    # GCP_DEPLOY_SERVICE_ACCOUNT, WORKER_IMAGE
```

### 6. First deploy, then switch the schedules on

1. GitHub → Actions → **Worker deploy** → **Run workflow** (on `main`). Approve `production` when asked.
2. Try one run by hand: `gcloud run jobs execute fitfinder-drain-staging --region europe-west1 --wait`, and check its logs in the console (Cloud Run → Jobs → the job → Logs).
3. In `terraform.tfvars`, set `schedules_enabled = true`, then `terraform apply`. From now on staging runs every 5 minutes and prod every minute.

## Costs

Each run starts a container for a few seconds. Cloud Run, Scheduler (3 jobs free per billing account), Artifact Registry and Secret Manager should stay at or near the free tier at our volume. The budget alert emails the billing admins before that changes. Check the bill after the first month.
