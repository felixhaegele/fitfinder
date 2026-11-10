# Email alerts (to the billing account's admins) before costs get real. A budget only
# warns: nothing is switched off when it's exceeded.
resource "google_billing_budget" "monthly" {
  billing_account = var.billing_account_id
  display_name    = "FitFinder monthly"

  budget_filter {
    projects = ["projects/${data.google_project.this.number}"]
  }

  amount {
    specified_amount {
      units = tostring(var.monthly_budget)
    }
  }

  threshold_rules {
    threshold_percent = 0.5
  }
  threshold_rules {
    threshold_percent = 0.9
  }
  threshold_rules {
    threshold_percent = 1.0
  }

  depends_on = [google_project_service.apis]
}
