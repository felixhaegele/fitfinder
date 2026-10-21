# Values CI needs; none of them are secret. Set them as GitHub repo variables (README.md).

output "GCP_PROJECT_ID" {
  value = var.project_id
}

output "GCP_REGION" {
  value = var.region
}

output "GCP_WORKLOAD_IDENTITY_PROVIDER" {
  value = google_iam_workload_identity_pool_provider.github.name
}

output "GCP_DEPLOY_SERVICE_ACCOUNT" {
  value = google_service_account.deployer.email
}

output "WORKER_IMAGE" {
  description = "Image name without tag; CI appends the git SHA."
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.worker.repository_id}/drain"
}

output "worker_jobs" {
  value = local.job_name
}
