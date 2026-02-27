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

variable "firestore_location" {
  description = "Firestore location"
  type        = string
  default     = "nam5"
}

variable "core_service_account_email" {
  description = "Core service account email"
  type        = string
}

variable "vpc_connector_name" {
  description = "VPC connector name"
  type        = string
}

variable "api_image" {
  description = "API container image"
  type        = string
}

variable "worker_image" {
  description = "Worker container image"
  type        = string
}

variable "webhook_image" {
  description = "Webhook container image"
  type        = string
}

variable "api_cpu_limit" {
  description = "API CPU limit"
  type        = string
  default     = "2"
}

variable "api_memory_limit" {
  description = "API memory limit"
  type        = string
  default     = "2Gi"
}

variable "api_cpu_request" {
  description = "API CPU request"
  type        = string
  default     = "1"
}

variable "api_memory_request" {
  description = "API memory request"
  type        = string
  default     = "1Gi"
}

variable "worker_cpu_limit" {
  description = "Worker CPU limit"
  type        = string
  default     = "4"
}

variable "worker_memory_limit" {
  description = "Worker memory limit"
  type        = string
  default     = "8Gi"
}

variable "worker_cpu_request" {
  description = "Worker CPU request"
  type        = string
  default     = "2"
}

variable "worker_memory_request" {
  description = "Worker memory request"
  type        = string
  default     = "4Gi"
}

variable "min_instances" {
  description = "Minimum instances for API"
  type        = string
  default     = "1"
}

variable "max_instances" {
  description = "Maximum instances for API"
  type        = string
  default     = "10"
}

variable "worker_min_instances" {
  description = "Minimum instances for worker"
  type        = string
  default     = "0"
}

variable "worker_max_instances" {
  description = "Maximum instances for worker"
  type        = string
  default     = "20"
}

variable "blue_traffic_percentage" {
  description = "Traffic percentage for blue deployment"
  type        = number
  default     = 100
}

variable "langfuse_host" {
  description = "LangFuse host URL"
  type        = string
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
