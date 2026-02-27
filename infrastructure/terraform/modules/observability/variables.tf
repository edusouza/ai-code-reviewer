variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "observability_service_account_email" {
  description = "Observability service account email"
  type        = string
}

variable "api_host" {
  description = "API host for uptime checks"
  type        = string
}

variable "alert_email" {
  description = "Email address for alerts"
  type        = string
}

variable "domain" {
  description = "Domain for BigQuery access"
  type        = string
  default     = "example.com"
}
