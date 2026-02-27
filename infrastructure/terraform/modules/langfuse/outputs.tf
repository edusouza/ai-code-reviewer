output "database_instance_name" {
  description = "Cloud SQL instance name"
  value       = google_sql_database_instance.langfuse.name
}

output "database_instance_connection_name" {
  description = "Cloud SQL instance connection name"
  value       = google_sql_database_instance.langfuse.connection_name
}

output "database_name" {
  description = "Database name"
  value       = google_sql_database.langfuse.name
}

output "langfuse_web_url" {
  description = "LangFuse web service URL"
  value       = google_cloud_run_service.langfuse_web.status[0].url
}

output "langfuse_worker_url" {
  description = "LangFuse worker service URL"
  value       = google_cloud_run_service.langfuse_worker.status[0].url
}

output "db_password_secret_id" {
  description = "Database password secret ID"
  value       = google_secret_manager_secret.db_password.id
}
