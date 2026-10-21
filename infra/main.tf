# Everything the worker needs in Google Cloud. ADR 0011 explains the choices.
#
#   Cloud Scheduler ──► Cloud Run Job (per environment) ──► Supabase
#                         image from Artifact Registry, secrets from Secret Manager
#   GitHub Actions ──(Workload Identity Federation, no stored key)──► push image, update job

locals {
  apis = [
    "artifactregistry.googleapis.com",
    "billingbudgets.googleapis.com",
    "cloudscheduler.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "sts.googleapis.com",
  ]
  job_name = { for env, _ in var.environments : env => "fitfinder-drain-${env}" }
}

resource "google_project_service" "apis" {
  for_each = toset(local.apis)
  service  = each.value
  # Keep the API on if this resource is ever removed from code; turning APIs off can
  # break things outside Terraform.
  disable_on_destroy = false
}

data "google_project" "this" {}
