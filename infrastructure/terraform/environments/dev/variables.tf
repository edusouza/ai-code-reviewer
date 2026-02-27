variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region"
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"
}

variable "subnet_cidr" {
  description = "CIDR range for the subnet"
  type        = string
  default     = "10.0.0.0/24"
}

variable "vpc_connector_cidr" {
  description = "CIDR range for the VPC connector"
  type        = string
  default     = "10.8.0.0/28"
}

variable "api_image" {
  description = "API container image"
  type        = string
  default     = "gcr.io/PROJECT_ID/ai-reviewer-api:latest"
}

variable "worker_image" {
  description = "Worker container image"
  type        = string
  default     = "gcr.io/PROJECT_ID/ai-reviewer-worker:latest"
}

variable "webhook_image" {
  description = "Webhook container image"
  type        = string
  default     = "gcr.io/PROJECT_ID/ai-reviewer-webhook:latest"
}

variable "api_cpu_limit" {
  description = "API CPU limit"
  type        = string
  default     = "1"
}

variable "api_memory_limit" {
  description = "API memory limit"
  type        = string
  default     = "1Gi"
}

variable "min_instances" {
  description = "Minimum instances for API"
  type        = string
  default     = "0"
}

variable "max_instances" {
  description = "Maximum instances for API"
  type        = string
  default     = "5"
}

variable "worker_cpu_limit" {
  description = "Worker CPU limit"
  type        = string
  default     = "2"
}

variable "worker_memory_limit" {
  description = "Worker memory limit"
  type        = string
  default     = "4Gi"
}

variable "worker_min_instances" {
  description = "Minimum instances for worker"
  type        = string
  default     = "0"
}

variable "worker_max_instances" {
  description = "Maximum instances for worker"
  type        = string
  default     = "10"
}

variable "langfuse_db_tier" {
  description = "Cloud SQL tier for LangFuse"
  type        = string
  default     = "db-f1-micro"
}

variable "github_token" {
  description = "GitHub token"
  type        = string
  sensitive   = true
}

variable "openai_api_key" {
  description = "OpenAI API key"
  type        = string
  sensitive   = true
}

variable "webhook_secret" {
  description = "GitHub webhook secret"
  type        = string
  sensitive   = true
}

variable "langfuse_public_key" {
  description = "LangFuse public key"
  type        = string
  sensitive   = true
}

variable "langfuse_secret_key" {
  description = "LangFuse secret key"
  type        = string
  sensitive   = true
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

variable "alert_email" {
  description = "Email address for alerts"
  type        = string
  default     = "alerts@example.com"
}

variable "domain" {
  description = "Domain for BigQuery access"
  type        = string
  default     = "example.com"
}
