# Core Module - Pub/Sub, Firestore, and Cloud Run

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = ">= 5.0"
    }
  }
}

# Firestore Database
resource "google_firestore_database" "database" {
  provider    = google-beta
  project     = var.project_id
  name        = "(default)"
  location_id = var.firestore_location
  type        = "FIRESTORE_NATIVE"

  app_engine_integration_mode = "DISABLED"
  point_in_time_recovery_enablement = var.environment == "prod" ? "POINT_IN_TIME_RECOVERY_ENABLED" : "POINT_IN_TIME_RECOVERY_DISABLED"
  delete_protection_state = var.environment == "prod" ? "DELETE_PROTECTION_ENABLED" : "DELETE_PROTECTION_DISABLED"
}

# Firestore indexes for common queries
resource "google_firestore_index" "reviews_by_status" {
  provider = google-beta
  project  = var.project_id
  database = google_firestore_database.database.name

  collection = "reviews"

  fields {
    field_path = "status"
    order      = "ASCENDING"
  }

  fields {
    field_path = "createdAt"
    order      = "DESCENDING"
  }
}

resource "google_firestore_index" "reviews_by_repository" {
  provider = google-beta
  project  = var.project_id
  database = google_firestore_database.database.name

  collection = "reviews"

  fields {
    field_path = "repositoryId"
    order      = "ASCENDING"
  }

  fields {
    field_path = "createdAt"
    order      = "DESCENDING"
  }
}

# Pub/Sub Topics
resource "google_pubsub_topic" "pr_events" {
  name    = "${var.environment}-pr-events"
  project = var.project_id

  message_retention_duration = "86600s"

  labels = {
    environment = var.environment
    service     = "ai-reviewer"
  }

  message_storage_policy {
    allowed_persistence_regions = [var.region]
  }
}

resource "google_pubsub_topic" "review_requests" {
  name    = "${var.environment}-review-requests"
  project = var.project_id

  message_retention_duration = "86600s"

  labels = {
    environment = var.environment
    service     = "ai-reviewer"
  }
}

resource "google_pubsub_topic" "review_results" {
  name    = "${var.environment}-review-results"
  project = var.project_id

  message_retention_duration = "86600s"

  labels = {
    environment = var.environment
    service     = "ai-reviewer"
  }
}

# Pub/Sub Subscriptions
resource "google_pubsub_subscription" "pr_events" {
  name    = "${var.environment}-pr-events-sub"
  project = var.project_id
  topic   = google_pubsub_topic.pr_events.id

  ack_deadline_seconds = 60

  message_retention_duration = "1200s"
  retain_acked_messages      = false

  expiration_policy {
    ttl = "2592000s" # 30 days
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dlq.id
    max_delivery_attempts = 5
  }
}

resource "google_pubsub_subscription" "review_requests" {
  name    = "${var.environment}-review-requests-sub"
  project = var.project_id
  topic   = google_pubsub_topic.review_requests.id

  ack_deadline_seconds = 300

  message_retention_duration = "1200s"
  retain_acked_messages      = false

  expiration_policy {
    ttl = "2592000s"
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dlq.id
    max_delivery_attempts = 5
  }
}

# Dead Letter Queue
resource "google_pubsub_topic" "dlq" {
  name    = "${var.environment}-dlq"
  project = var.project_id

  labels = {
    environment = var.environment
    service     = "ai-reviewer"
    type        = "dead-letter"
  }
}

resource "google_pubsub_subscription" "dlq" {
  name    = "${var.environment}-dlq-sub"
  project = var.project_id
  topic   = google_pubsub_topic.dlq.id

  ack_deadline_seconds = 60
}

# Cloud Run API Service - Blue Deployment
resource "google_cloud_run_service" "api_blue" {
  name     = "${var.environment}-api-blue"
  project  = var.project_id
  location = var.region

  template {
    spec {
      service_account_name = var.core_service_account_email
      
      containers {
        image = var.api_image

        resources {
          limits = {
            cpu    = var.api_cpu_limit
            memory = var.api_memory_limit
          }
          requests = {
            cpu    = var.api_cpu_request
            memory = var.api_memory_request
          }
        }

        env {
          name  = "ENVIRONMENT"
          value = var.environment
        }

        env {
          name  = "PUBSUB_PROJECT_ID"
          value = var.project_id
        }

        env {
          name  = "FIRESTORE_PROJECT_ID"
          value = var.project_id
        }

        env {
          name = "GITHUB_TOKEN"
          value_from {
            secret_key_ref {
              name = google_secret_manager_secret.github_token.secret_id
              key  = "latest"
            }
          }
        }

        env {
          name = "OPENAI_API_KEY"
          value_from {
            secret_key_ref {
              name = google_secret_manager_secret.openai_key.secret_id
              key  = "latest"
            }
          }
        }

        ports {
          container_port = 8080
        }
      }

      timeout_seconds = 300
    }

    metadata {
      annotations = {
        "run.googleapis.com/max-instance-request-concurrency" = "100"
        "autoscaling.knative.dev/minScale" = var.min_instances
        "autoscaling.knative.dev/maxScale" = var.max_instances
        "run.googleapis.com/vpc-access-connector" = var.vpc_connector_name
        "run.googleapis.com/vpc-access-egress"    = "private-ranges-only"
      }
    }
  }

  traffic {
    percent         = var.blue_traffic_percentage
    latest_revision = true
  }

  depends_on = [google_firestore_database.database]
}

# Cloud Run API Service - Green Deployment
resource "google_cloud_run_service" "api_green" {
  name     = "${var.environment}-api-green"
  project  = var.project_id
  location = var.region

  template {
    spec {
      service_account_name = var.core_service_account_email
      
      containers {
        image = var.api_image

        resources {
          limits = {
            cpu    = var.api_cpu_limit
            memory = var.api_memory_limit
          }
          requests = {
            cpu    = var.api_cpu_request
            memory = var.api_memory_request
          }
        }

        env {
          name  = "ENVIRONMENT"
          value = var.environment
        }

        env {
          name  = "PUBSUB_PROJECT_ID"
          value = var.project_id
        }

        env {
          name  = "FIRESTORE_PROJECT_ID"
          value = var.project_id
        }

        env {
          name = "GITHUB_TOKEN"
          value_from {
            secret_key_ref {
              name = google_secret_manager_secret.github_token.secret_id
              key  = "latest"
            }
          }
        }

        env {
          name = "OPENAI_API_KEY"
          value_from {
            secret_key_ref {
              name = google_secret_manager_secret.openai_key.secret_id
              key  = "latest"
            }
          }
        }

        ports {
          container_port = 8080
        }
      }

      timeout_seconds = 300
    }

    metadata {
      annotations = {
        "run.googleapis.com/max-instance-request-concurrency" = "100"
        "autoscaling.knative.dev/minScale" = var.min_instances
        "autoscaling.knative.dev/maxScale" = var.max_instances
        "run.googleapis.com/vpc-access-connector" = var.vpc_connector_name
        "run.googleapis.com/vpc-access-egress"    = "private-ranges-only"
      }
    }
  }

  traffic {
    percent         = 0
    latest_revision = true
  }

  depends_on = [google_firestore_database.database]
}

# Cloud Run Worker Service
resource "google_cloud_run_service" "worker" {
  name     = "${var.environment}-worker"
  project  = var.project_id
  location = var.region

  template {
    spec {
      service_account_name = var.core_service_account_email
      
      containers {
        image = var.worker_image

        resources {
          limits = {
            cpu    = var.worker_cpu_limit
            memory = var.worker_memory_limit
          }
          requests = {
            cpu    = var.worker_cpu_request
            memory = var.worker_memory_request
          }
        }

        env {
          name  = "ENVIRONMENT"
          value = var.environment
        }

        env {
          name  = "PUBSUB_SUBSCRIPTION"
          value = google_pubsub_subscription.review_requests.name
        }

        env {
          name = "OPENAI_API_KEY"
          value_from {
            secret_key_ref {
              name = google_secret_manager_secret.openai_key.secret_id
              key  = "latest"
            }
          }
        }

        env {
          name = "LANGFUSE_HOST"
          value = var.langfuse_host
        }

        env {
          name = "LANGFUSE_PUBLIC_KEY"
          value_from {
            secret_key_ref {
              name = google_secret_manager_secret.langfuse_public_key.secret_id
              key  = "latest"
            }
          }
        }

        env {
          name = "LANGFUSE_SECRET_KEY"
          value_from {
            secret_key_ref {
              name = google_secret_manager_secret.langfuse_secret_key.secret_id
              key  = "latest"
            }
          }
        }
      }

      timeout_seconds = 600
    }

    metadata {
      annotations = {
        "autoscaling.knative.dev/minScale" = var.worker_min_instances
        "autoscaling.knative.dev/maxScale" = var.worker_max_instances
        "run.googleapis.com/vpc-access-connector" = var.vpc_connector_name
        "run.googleapis.com/vpc-access-egress"    = "private-ranges-only"
      }
    }
  }

  depends_on = [google_pubsub_subscription.review_requests]
}

# Cloud Run Webhook Service
resource "google_cloud_run_service" "webhook" {
  name     = "${var.environment}-webhook"
  project  = var.project_id
  location = var.region

  template {
    spec {
      service_account_name = var.core_service_account_email
      
      containers {
        image = var.webhook_image

        resources {
          limits = {
            cpu    = "1"
            memory = "512Mi"
          }
        }

        env {
          name  = "ENVIRONMENT"
          value = var.environment
        }

        env {
          name  = "PUBSUB_TOPIC"
          value = google_pubsub_topic.pr_events.name
        }

        env {
          name = "WEBHOOK_SECRET"
          value_from {
            secret_key_ref {
              name = google_secret_manager_secret.webhook_secret.secret_id
              key  = "latest"
            }
          }
        }

        ports {
          container_port = 8080
        }
      }

      timeout_seconds = 60
    }

    metadata {
      annotations = {
        "autoscaling.knative.dev/minScale" = "1"
        "autoscaling.knative.dev/maxScale" = "10"
      }
    }
  }
}

# Secret Manager - GitHub Token
resource "google_secret_manager_secret" "github_token" {
  provider  = google-beta
  secret_id = "${var.environment}-github-token"
  project   = var.project_id

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "github_token" {
  provider    = google-beta
  secret      = google_secret_manager_secret.github_token.id
  secret_data = var.github_token
}

# Secret Manager - OpenAI API Key
resource "google_secret_manager_secret" "openai_key" {
  provider  = google-beta
  secret_id = "${var.environment}-openai-api-key"
  project   = var.project_id

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "openai_key" {
  provider    = google-beta
  secret      = google_secret_manager_secret.openai_key.id
  secret_data = var.openai_api_key
}

# Secret Manager - Webhook Secret
resource "google_secret_manager_secret" "webhook_secret" {
  provider  = google-beta
  secret_id = "${var.environment}-webhook-secret"
  project   = var.project_id

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "webhook_secret" {
  provider    = google-beta
  secret      = google_secret_manager_secret.webhook_secret.id
  secret_data = var.webhook_secret
}

# Secret Manager - LangFuse Keys
resource "google_secret_manager_secret" "langfuse_public_key" {
  provider  = google-beta
  secret_id = "${var.environment}-langfuse-public-key"
  project   = var.project_id

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "langfuse_public_key" {
  provider    = google-beta
  secret      = google_secret_manager_secret.langfuse_public_key.id
  secret_data = var.langfuse_public_key
}

resource "google_secret_manager_secret" "langfuse_secret_key" {
  provider  = google-beta
  secret_id = "${var.environment}-langfuse-secret-key"
  project   = var.project_id

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "langfuse_secret_key" {
  provider    = google-beta
  secret      = google_secret_manager_secret.langfuse_secret_key.id
  secret_data = var.langfuse_secret_key
}

# IAM for Cloud Run services to be invoked
resource "google_cloud_run_service_iam_member" "api_blue_public" {
  location = google_cloud_run_service.api_blue.location
  project  = google_cloud_run_service.api_blue.project
  service  = google_cloud_run_service.api_blue.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_service_iam_member" "api_green_public" {
  location = google_cloud_run_service.api_green.location
  project  = google_cloud_run_service.api_green.project
  service  = google_cloud_run_service.api_green.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_service_iam_member" "webhook_public" {
  location = google_cloud_run_service.webhook.location
  project  = google_cloud_run_service.webhook.project
  service  = google_cloud_run_service.webhook.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# Pub/Sub to Cloud Run trigger
resource "google_pubsub_subscription_iam_member" "worker_subscriber" {
  subscription = google_pubsub_subscription.review_requests.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${var.core_service_account_email}"
  project      = var.project_id
}
