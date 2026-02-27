output "core_service_account_email" {
  description = "Core service account email"
  value       = google_service_account.core.email
}

output "core_service_account_id" {
  description = "Core service account ID"
  value       = google_service_account.core.id
}

output "langfuse_service_account_email" {
  description = "LangFuse service account email"
  value       = google_service_account.langfuse.email
}

output "langfuse_service_account_id" {
  description = "LangFuse service account ID"
  value       = google_service_account.langfuse.id
}

output "observability_service_account_email" {
  description = "Observability service account email"
  value       = google_service_account.observability.email
}

output "observability_service_account_id" {
  description = "Observability service account ID"
  value       = google_service_account.observability.id
}

output "cloud_run_service_agent" {
  description = "Cloud Run service agent email"
  value       = google_project_service_identity.run.email
}
