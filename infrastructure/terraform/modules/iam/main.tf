# IAM Module - Service Accounts and Roles

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0"
    }
  }
}

# Service Account for Core Services
resource "google_service_account" "core" {
  account_id   = "${var.environment}-core-sa"
  display_name = "Core Services Service Account"
  project      = var.project_id
  description  = "Service account for core Cloud Run services and Pub/Sub"
}

# Service Account for LangFuse
resource "google_service_account" "langfuse" {
  account_id   = "${var.environment}-langfuse-sa"
  display_name = "LangFuse Service Account"
  project      = var.project_id
  description  = "Service account for LangFuse deployment"
}

# Service Account for Observability
resource "google_service_account" "observability" {
  account_id   = "${var.environment}-observability-sa"
  display_name = "Observability Service Account"
  project      = var.project_id
  description  = "Service account for BigQuery and monitoring"
}

# Core Service Account Permissions
resource "google_project_iam_member" "core_pubsub" {
  project = var.project_id
  role    = "roles/pubsub.editor"
  member  = "serviceAccount:${google_service_account.core.email}"
}

resource "google_project_iam_member" "core_firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.core.email}"
}

resource "google_project_iam_member" "core_secretmanager" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.core.email}"
}

resource "google_project_iam_member" "core_cloudtrace" {
  project = var.project_id
  role    = "roles/cloudtrace.agent"
  member  = "serviceAccount:${google_service_account.core.email}"
}

resource "google_project_iam_member" "core_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.core.email}"
}

resource "google_project_iam_member" "core_monitoring" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.core.email}"
}

resource "google_project_iam_member" "core_storage" {
  project = var.project_id
  role    = "roles/storage.objectViewer"
  member  = "serviceAccount:${google_service_account.core.email}"
}

# LangFuse Service Account Permissions
resource "google_project_iam_member" "langfuse_cloudsql" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.langfuse.email}"
}

resource "google_project_iam_member" "langfuse_secretmanager" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.langfuse.email}"
}

resource "google_project_iam_member" "langfuse_cloudtrace" {
  project = var.project_id
  role    = "roles/cloudtrace.agent"
  member  = "serviceAccount:${google_service_account.langfuse.email}"
}

resource "google_project_iam_member" "langfuse_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.langfuse.email}"
}

# Observability Service Account Permissions
resource "google_project_iam_member" "observability_bigquery" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.observability.email}"
}

resource "google_project_iam_member" "observability_bigquery_job" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.observability.email}"
}

resource "google_project_iam_member" "observability_monitoring" {
  project = var.project_id
  role    = "roles/monitoring.alertPolicyEditor"
  member  = "serviceAccount:${google_service_account.observability.email}"
}

resource "google_project_iam_member" "observability_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.observability.email}"
}

# Cloud Run Service Agent
resource "google_project_service_identity" "run" {
  provider = google-beta
  project  = var.project_id
  service  = "run.googleapis.com"
}
