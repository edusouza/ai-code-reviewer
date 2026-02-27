# Bootstrap Configuration
# Run this first to set up the GCS backend bucket and enable APIs

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}

# Enable required APIs
resource "google_project_service" "apis" {
  for_each = toset([
    "compute.googleapis.com",
    "run.googleapis.com",
    "firestore.googleapis.com",
    "pubsub.googleapis.com",
    "secretmanager.googleapis.com",
    "sqladmin.googleapis.com",
    "bigquery.googleapis.com",
    "monitoring.googleapis.com",
    "logging.googleapis.com",
    "cloudbuild.googleapis.com",
    "containerregistry.googleapis.com",
    "iam.googleapis.com",
    "cloudresourcemanager.googleapis.com",
  ])

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

# Create GCS bucket for Terraform state
resource "google_storage_bucket" "terraform_state" {
  name          = "${var.project_id}-terraform-state"
  project       = var.project_id
  location      = var.region
  force_destroy = false

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      num_newer_versions = 10
    }
    action {
      type = "Delete"
    }
  }

  encryption {
    default_kms_key_name = google_kms_crypto_key.terraform_state.id
  }

  depends_on = [google_project_service.apis]
}

# KMS key for state encryption
resource "google_kms_key_ring" "terraform" {
  name     = "terraform-keyring"
  location = var.region

  depends_on = [google_project_service.apis]
}

resource "google_kms_crypto_key" "terraform_state" {
  name            = "terraform-state-key"
  key_ring        = google_kms_key_ring.terraform.id
  rotation_period = "7776000s" # 90 days

  version_template {
    algorithm        = "GOOGLE_SYMMETRIC_ENCRYPTION"
    protection_level = "HSM"
  }
}

# IAM for KMS
resource "google_kms_crypto_key_iam_member" "terraform_encrypt" {
  crypto_key_id = google_kms_crypto_key.terraform_state.id
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = "serviceAccount:service-${data.google_project.project.number}@gs-project-accounts.iam.gserviceaccount.com"
}

data "google_project" "project" {
  project_id = var.project_id
}
