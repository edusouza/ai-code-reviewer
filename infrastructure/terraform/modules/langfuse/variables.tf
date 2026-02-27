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

variable "vpc_id" {
  description = "VPC network ID"
  type        = string
}

variable "vpc_connector_name" {
  description = "VPC connector name"
  type        = string
}

variable "langfuse_service_account_email" {
  description = "LangFuse service account email"
  type        = string
}

variable "db_tier" {
  description = "Cloud SQL tier"
  type        = string
  default     = "db-g1-small"
}

variable "langfuse_image" {
  description = "LangFuse web container image"
  type        = string
  default     = "ghcr.io/langfuse/langfuse:latest"
}

variable "langfuse_worker_image" {
  description = "LangFuse worker container image"
  type        = string
  default     = "ghcr.io/langfuse/langfuse-worker:latest"
}

variable "langfuse_cpu" {
  description = "LangFuse CPU limit"
  type        = string
  default     = "2"
}

variable "langfuse_memory" {
  description = "LangFuse memory limit"
  type        = string
  default     = "4Gi"
}

variable "nextauth_secret" {
  description = "NextAuth secret"
  type        = string
  sensitive   = true
}

variable "langfuse_salt" {
  description = "LangFuse salt"
  type        = string
  sensitive   = true
}
