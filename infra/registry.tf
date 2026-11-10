# Docker images of the worker. CI pushes one tag per commit (the git SHA).
resource "google_artifact_registry_repository" "worker" {
  repository_id = "worker"
  format        = "DOCKER"
  location      = var.region
  description   = "FitFinder measurement worker images"

  # Keep the newest 20 images, delete older ones: storage costs money.
  cleanup_policies {
    id     = "keep-recent"
    action = "KEEP"
    most_recent_versions {
      keep_count = 20
    }
  }
  cleanup_policies {
    id     = "delete-old"
    action = "DELETE"
    condition {
      older_than = "2592000s" # 30 days
    }
  }

  depends_on = [google_project_service.apis]
}
