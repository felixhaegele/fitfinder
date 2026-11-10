terraform {
  required_version = ">= 1.9"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 8.7"
    }
  }

  # State lives in a GCS bucket, not on a laptop. The bucket name is passed at init:
  #   terraform init -backend-config="bucket=<state bucket>"
  # (see README.md: it's created once by hand, before Terraform exists)
  backend "gcs" {
    prefix = "fitfinder"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region

  # Some APIs (e.g. billing budgets) need a project to bill API calls to when you run
  # Terraform with your own user login.
  user_project_override = true
  billing_project       = var.project_id
}
