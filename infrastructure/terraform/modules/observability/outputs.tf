output "dataset_id" {
  description = "BigQuery dataset ID"
  value       = google_bigquery_dataset.observability.dataset_id
}

output "review_logs_table" {
  description = "Review logs table ID"
  value       = google_bigquery_table.review_logs.id
}

output "metrics_table" {
  description = "Metrics table ID"
  value       = google_bigquery_table.metrics.id
}

output "dashboard_id" {
  description = "Monitoring dashboard ID"
  value       = google_monitoring_dashboard.main.id
}

output "log_sink_writer_identity" {
  description = "Log sink writer identity"
  value       = google_logging_project_sink.bigquery_sink.writer_identity
}
