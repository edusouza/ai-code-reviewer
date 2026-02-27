output "firestore_database_id" {
  description = "Firestore database ID"
  value       = google_firestore_database.database.id
}

output "pr_events_topic_id" {
  description = "PR events topic ID"
  value       = google_pubsub_topic.pr_events.id
}

output "review_requests_topic_id" {
  description = "Review requests topic ID"
  value       = google_pubsub_topic.review_requests.id
}

output "review_results_topic_id" {
  description = "Review results topic ID"
  value       = google_pubsub_topic.review_results.id
}

output "api_blue_url" {
  description = "Blue API service URL"
  value       = google_cloud_run_service.api_blue.status[0].url
}

output "api_green_url" {
  description = "Green API service URL"
  value       = google_cloud_run_service.api_green.status[0].url
}

output "webhook_url" {
  description = "Webhook service URL"
  value       = google_cloud_run_service.webhook.status[0].url
}

output "worker_url" {
  description = "Worker service URL"
  value       = google_cloud_run_service.worker.status[0].url
}

output "github_token_secret_id" {
  description = "GitHub token secret ID"
  value       = google_secret_manager_secret.github_token.id
}

output "openai_key_secret_id" {
  description = "OpenAI key secret ID"
  value       = google_secret_manager_secret.openai_key.id
}
