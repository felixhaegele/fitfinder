# Secret *containers* only. The values are added by the owner with gcloud (README.md),
# so they never end up in Terraform code or state.

locals {
  secret_names = ["supabase-secret-key", "supabase-db-url"]
  secrets = merge([
    for env, _ in var.environments : {
      for name in local.secret_names : "${name}-${env}" => { env = env, name = name }
    }
  ]...)
}

resource "google_secret_manager_secret" "worker" {
  for_each  = local.secrets
  secret_id = each.key

  replication {
    user_managed {
      replicas {
        location = var.region # EU only
      }
    }
  }

  depends_on = [google_project_service.apis]
}

# Each environment's worker may read only its own secrets.
resource "google_secret_manager_secret_iam_member" "worker" {
  for_each  = local.secrets
  secret_id = google_secret_manager_secret.worker[each.key].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.worker[each.value.env].email}"
}
