# One Cloud Run Job per environment. It runs `python -m app.jobs.drain`: handle queue
# messages until the queue is empty, then exit (ADR 0003, option C).

resource "google_cloud_run_v2_job" "drain" {
  for_each = var.environments
  name     = local.job_name[each.key]
  location = var.region

  # Removing a job needs this set to false first: a deliberate extra step.
  deletion_protection = true

  template {
    task_count = 1

    template {
      service_account = google_service_account.worker[each.key].email
      timeout         = "600s" # per run; each message has its own, shorter limit
      max_retries     = 0      # the queue already retries failed messages

      containers {
        # Placeholder until CI pushes the first worker image; CI updates the image on
        # every deploy, so Terraform ignores it afterwards (lifecycle below).
        image   = "us-docker.pkg.dev/cloudrun/container/job:latest"
        command = ["python", "-m", "app.jobs.drain"]

        resources {
          limits = {
            cpu    = "1"
            memory = "1Gi" # OpenCV + a 4000 px photo, with headroom
          }
        }

        env {
          name  = "SUPABASE_URL"
          value = each.value.supabase_url
        }
        env {
          name = "SUPABASE_SECRET_KEY"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.worker["supabase-secret-key-${each.key}"].secret_id
              version = "latest"
            }
          }
        }
        env {
          name = "SUPABASE_DB_URL"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.worker["supabase-db-url-${each.key}"].secret_id
              version = "latest"
            }
          }
        }
        env {
          name  = "SENTRY_ENVIRONMENT"
          value = each.key
        }
      }
    }
  }

  lifecycle {
    ignore_changes = [
      template[0].template[0].containers[0].image, # CI owns the image
      client,
      client_version,
    ]
  }

  depends_on = [
    google_project_service.apis,
    google_secret_manager_secret_iam_member.worker,
  ]
}

# Starts each job on its schedule.
resource "google_cloud_scheduler_job" "drain" {
  for_each  = var.environments
  name      = "${local.job_name[each.key]}-schedule"
  region    = var.region
  schedule  = each.value.schedule
  time_zone = "Etc/UTC"
  paused    = !var.schedules_enabled

  # A run that is still going when the next tick comes is fine: two workers read the
  # queue safely (each message is hidden while one worker has it).
  attempt_deadline = "30s"

  http_target {
    http_method = "POST"
    uri         = "https://run.googleapis.com/v2/projects/${var.project_id}/locations/${var.region}/jobs/${local.job_name[each.key]}:run"
    oauth_token {
      service_account_email = google_service_account.scheduler.email
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }

  depends_on = [google_cloud_run_v2_job_iam_member.scheduler_runs_job]
}
