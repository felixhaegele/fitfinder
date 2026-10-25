variable "project_id" {
  description = "Google Cloud project that holds everything (e.g. fitfinder-123456)."
  type        = string
}

variable "region" {
  description = "Region for the registry, jobs and scheduler. EU for GDPR; europe-west1 (Belgium) is closest to Supabase's eu-west-1 (Ireland)."
  type        = string
  default     = "europe-west1"
}

variable "github_repository" {
  description = "owner/name of the GitHub repo allowed to deploy (Workload Identity Federation)."
  type        = string
  default     = "felixhaegele/fitfinder"
}

variable "billing_account_id" {
  description = "Billing account for the budget alert, e.g. 012345-6789AB-CDEF01 (gcloud billing accounts list)."
  type        = string
}

variable "monthly_budget" {
  description = "Monthly budget in the billing account's currency. Alerts at 50 %, 90 % and 100 %; nothing is switched off."
  type        = number
  default     = 10
}

variable "environments" {
  description = "One Cloud Run Job per environment, each with its own service account, secrets and schedule."
  type = map(object({
    supabase_url = string
    schedule     = string # cron, UTC
  }))
  default = {
    staging = {
      supabase_url = "https://xjusmksmnnywliwgspmf.supabase.co"
      schedule     = "*/5 * * * *" # test uploads only; every 5 min keeps costs down
    }
    prod = {
      supabase_url = "https://usdetilhsblzfnezwdvs.supabase.co"
      schedule     = "* * * * *" # users wait at most ~1 min (ADR 0003)
    }
  }
}

variable "schedules_enabled" {
  description = "Start the jobs on their schedules. Keep false until CI has deployed the first worker image (the jobs start with a placeholder image), then set true and apply again."
  type        = bool
  default     = false
}
