# Identities, each with the least it needs:
#   worker-<env>   what the job runs as: read its own secrets, nothing else
#   scheduler      may start the jobs
#   deployer       what GitHub Actions becomes: push images, update the jobs

resource "google_service_account" "worker" {
  for_each     = var.environments
  account_id   = "worker-${each.key}"
  display_name = "FitFinder worker (${each.key})"
}

resource "google_service_account" "scheduler" {
  account_id   = "scheduler"
  display_name = "Starts the FitFinder worker jobs"
}

resource "google_service_account" "deployer" {
  account_id   = "github-deployer"
  display_name = "GitHub Actions: deploys the worker"
}

# Scheduler → start jobs
resource "google_cloud_run_v2_job_iam_member" "scheduler_runs_job" {
  for_each = var.environments
  name     = google_cloud_run_v2_job.drain[each.key].name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler.email}"
}

# Deployer → push images to our registry only
resource "google_artifact_registry_repository_iam_member" "deployer_pushes" {
  repository = google_artifact_registry_repository.worker.name
  location   = var.region
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.deployer.email}"
}

# Deployer → update the two jobs (not create or delete other services)
resource "google_cloud_run_v2_job_iam_member" "deployer_updates_job" {
  for_each = var.environments
  name     = google_cloud_run_v2_job.drain[each.key].name
  location = var.region
  role     = "roles/run.developer"
  member   = "serviceAccount:${google_service_account.deployer.email}"
}

# Deployer → may set the worker service accounts on the jobs it updates
resource "google_service_account_iam_member" "deployer_acts_as_worker" {
  for_each           = var.environments
  service_account_id = google_service_account.worker[each.key].name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deployer.email}"
}
