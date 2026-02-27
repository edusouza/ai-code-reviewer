# LangFuse Module - Cloud SQL and LangFuse Deployment

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
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

# Generate random password for database
resource "random_password" "db_password" {
  length  = 32
  special = true
}

# Secret for database password
resource "google_secret_manager_secret" "db_password" {
  provider  = google-beta
  secret_id = "${var.environment}-langfuse-db-password"
  project   = var.project_id

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "db_password" {
  provider    = google-beta
  secret      = google_secret_manager_secret.db_password.id
  secret_data = random_password.db_password.result
}

# Cloud SQL Instance
resource "google_sql_database_instance" "langfuse" {
  name             = "${var.environment}-langfuse-db"
  database_version = "POSTGRES_15"
  project          = var.project_id
  region           = var.region

  settings {
    tier              = var.db_tier
    availability_type = var.environment == "prod" ? "REGIONAL" : "ZONAL"

    backup_configuration {
      enabled                        = true
      start_time                     = "03:00"
      point_in_time_recovery_enabled = var.environment == "prod"
      transaction_log_retention_days = var.environment == "prod" ? 7 : 1
      backup_retention_settings {
        retained_backups = var.environment == "prod" ? 30 : 7
        retention_unit   = "COUNT"
      }
    }

    maintenance_window {
      day          = 7
      hour         = 3
      update_track = "stable"
    }

    insights_config {
      query_insights_enabled  = true
      query_string_length     = 1024
      record_application_tags = true
      record_client_address   = true
    }

    ip_configuration {
      ipv4_enabled    = false
      private_network = var.vpc_id
    }

    database_flags {
      name  = "cloudsql.iam_authentication"
      value = "on"
    }
  }

  deletion_protection = var.environment == "prod"
}

# Database
resource "google_sql_database" "langfuse" {
  name     = "langfuse"
  instance = google_sql_database_instance.langfuse.name
  project  = var.project_id
}

# Database User
resource "google_sql_user" "langfuse" {
  name     = "langfuse"
  instance = google_sql_database_instance.langfuse.name
  project  = var.project_id
  password = random_password.db_password.result
}

# Cloud Run Service for LangFuse Web
resource "google_cloud_run_service" "langfuse_web" {
  name     = "${var.environment}-langfuse-web"
  project  = var.project_id
  location = var.region

  template {
    spec {
      service_account_name = var.langfuse_service_account_email
      
      containers {
        image = var.langfuse_image

        resources {
          limits = {
            cpu    = var.langfuse_cpu
            memory = var.langfuse_memory
          }
        }

        env {
          name  = "DATABASE_URL"
          value = "postgresql://langfuse:${random_password.db_password.result}@/${google_sql_database.langfuse.name}?host=/cloudsql/${google_sql_database_instance.langfuse.connection_name}"
        }

        env {
          name  = "NEXTAUTH_URL"
          value = "https://${var.environment}-langfuse-web-${var.project_id}-${var.region}.run.app"
        }

        env {
          name  = "NEXTAUTH_SECRET"
          value = var.nextauth_secret
        }

        env {
          name  = "SALT"
          value = var.langfuse_salt
        }

        env {
          name  = "TELEMETRY_ENABLED"
          value = "false"
        }

        env {
          name  = "LANGFUSE_ENABLE_EXPERIMENTAL_FEATURES"
          value = "false"
        }

        ports {
          container_port = 3000
        }
      }

      timeout_seconds = 300
    }

    metadata {
      annotations = {
        "autoscaling.knative.dev/minScale" = "1"
        "autoscaling.knative.dev/maxScale" = "5"
        "run.googleapis.com/cloudsql-instances" = google_sql_database_instance.langfuse.connection_name
        "run.googleapis.com/vpc-access-connector" = var.vpc_connector_name
        "run.googleapis.com/vpc-access-egress"    = "private-ranges-only"
      }
    }
  }

  depends_on = [google_sql_database.langfuse]
}

# Cloud Run Service for LangFuse Worker
resource "google_cloud_run_service" "langfuse_worker" {
  name     = "${var.environment}-langfuse-worker"
  project  = var.project_id
  location = var.region

  template {
    spec {
      service_account_name = var.langfuse_service_account_email
      
      containers {
        image = var.langfuse_worker_image

        resources {
          limits = {
            cpu    = "2"
            memory = "4Gi"
          }
        }

        env {
          name  = "DATABASE_URL"
          value = "postgresql://langfuse:${random_password.db_password.result}@/${google_sql_database.langfuse.name}?host=/cloudsql/${google_sql_database_instance.langfuse.connection_name}"
        }

        env {
          name  = "SALT"
          value = var.langfuse_salt
        }
      }

      timeout_seconds = 600
    }

    metadata {
      annotations = {
        "autoscaling.knative.dev/minScale" = "1"
        "autoscaling.knative.dev/maxScale" = "10"
        "run.googleapis.com/cloudsql-instances" = google_sql_database_instance.langfuse.connection_name
      }
    }
  }

  depends_on = [google_sql_database.langfuse]
}

# IAM for public access (for now - should be restricted in production)
resource "google_cloud_run_service_iam_member" "langfuse_web_public" {
  location = google_cloud_run_service.langfuse_web.location
  project  = google_cloud_run_service.langfuse_web.project
  service  = google_cloud_run_service.langfuse_web.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
