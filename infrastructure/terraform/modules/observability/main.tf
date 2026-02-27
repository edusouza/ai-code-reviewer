# Observability Module - BigQuery, Monitoring, and Alerts

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

# BigQuery Dataset for logs and metrics
resource "google_bigquery_dataset" "observability" {
  dataset_id  = "${var.environment}_ai_reviewer"
  project     = var.project_id
  description = "AI Code Reviewer observability data"
  location    = var.region

  default_table_expiration_ms = var.environment == "prod" ? null : 2592000000 # 30 days for non-prod

  labels = {
    environment = var.environment
    service     = "ai-reviewer"
  }

  access {
    role          = "OWNER"
    user_by_email = var.observability_service_account_email
  }

  access {
    role   = "READER"
    domain = var.domain
  }
}

# Table for review logs
resource "google_bigquery_table" "review_logs" {
  dataset_id = google_bigquery_dataset.observability.dataset_id
  table_id   = "review_logs"
  project    = var.project_id

  schema = jsonencode([
    {
      name = "timestamp"
      type = "TIMESTAMP"
      mode = "REQUIRED"
    },
    {
      name = "review_id"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "repository"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "pr_number"
      type = "INTEGER"
      mode = "REQUIRED"
    },
    {
      name = "status"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "duration_ms"
      type = "INTEGER"
      mode = "NULLABLE"
    },
    {
      name = "tokens_used"
      type = "INTEGER"
      mode = "NULLABLE"
    },
    {
      name = "cost_usd"
      type = "FLOAT"
      mode = "NULLABLE"
    },
    {
      name = "error_message"
      type = "STRING"
      mode = "NULLABLE"
    }
  ])

  time_partitioning {
    type          = "DAY"
    field         = "timestamp"
    expiration_ms = var.environment == "prod" ? null : 2592000000
  }

  clustering = ["status", "repository"]
}

# Table for metrics
resource "google_bigquery_table" "metrics" {
  dataset_id = google_bigquery_dataset.observability.dataset_id
  table_id   = "metrics"
  project    = var.project_id

  schema = jsonencode([
    {
      name = "timestamp"
      type = "TIMESTAMP"
      mode = "REQUIRED"
    },
    {
      name = "metric_name"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "metric_value"
      type = "FLOAT"
      mode = "REQUIRED"
    },
    {
      name = "labels"
      type = "JSON"
      mode = "NULLABLE"
    }
  ])

  time_partitioning {
    type          = "DAY"
    field         = "timestamp"
    expiration_ms = var.environment == "prod" ? null : 2592000000
  }
}

# Log sink to BigQuery
resource "google_logging_project_sink" "bigquery_sink" {
  name                   = "${var.environment}-ai-reviewer-logs"
  project                = var.project_id
  destination            = "bigquery.googleapis.com/projects/${var.project_id}/datasets/${google_bigquery_dataset.observability.dataset_id}"
  filter                 = <<-EOT
    resource.type="cloud_run_revision"
    resource.labels.service_name=~"${var.environment}-(api|worker|webhook|langfuse)"
  EOT
  unique_writer_identity = true
}

resource "google_bigquery_dataset_iam_member" "log_writer" {
  dataset_id = google_bigquery_dataset.observability.dataset_id
  project    = var.project_id
  role       = "roles/bigquery.dataEditor"
  member     = google_logging_project_sink.bigquery_sink.writer_identity
}

# Uptime check for API
resource "google_monitoring_uptime_check_config" "api" {
  display_name = "${var.environment} API Health Check"
  project      = var.project_id
  timeout      = "10s"
  period       = "60s"

  http_check {
    path         = "/health"
    port         = "443"
    use_ssl      = true
    validate_ssl = true
  }

  monitored_resource {
    type = "uptime_url"
    labels = {
      host       = var.api_host
      project_id = var.project_id
    }
  }
}

# Alerting policies
resource "google_monitoring_alert_policy" "high_latency" {
  display_name = "${var.environment} High API Latency"
  project      = var.project_id
  combiner     = "OR"

  conditions {
    display_name = "API Latency > 2s"

    condition_threshold {
      filter          = <<-EOT
        resource.type="cloud_run_revision"
        metric.type="run.googleapis.com/request_latencies"
        resource.labels.service_name="${var.environment}-api-blue"
      EOT
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 2000

      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_PERCENTILE_99"
        cross_series_reducer = "REDUCE_MEAN"
      }

      trigger {
        count = 1
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.id]

  alert_strategy {
    auto_close = "86400s"
  }

  severity = "WARNING"
}

resource "google_monitoring_alert_policy" "high_error_rate" {
  display_name = "${var.environment} High Error Rate"
  project      = var.project_id
  combiner     = "OR"

  conditions {
    display_name = "Error rate > 5%"

    condition_threshold {
      filter          = <<-EOT
        resource.type="cloud_run_revision"
        metric.type="run.googleapis.com/request_count"
        metric.labels.response_code_class!="2xx"
        resource.labels.service_name=~"${var.environment}-(api|worker|webhook)"
      EOT
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0.05

      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_RATE"
        cross_series_reducer = "REDUCE_SUM"
      }

      denominator_filter = <<-EOT
        resource.type="cloud_run_revision"
        metric.type="run.googleapis.com/request_count"
        resource.labels.service_name=~"${var.environment}-(api|worker|webhook)"
      EOT

      denominator_aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_RATE"
        cross_series_reducer = "REDUCE_SUM"
      }

      trigger {
        count = 1
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.id]

  alert_strategy {
    auto_close = "86400s"
  }

  severity = "CRITICAL"
}

resource "google_monitoring_alert_policy" "db_connections" {
  display_name = "${var.environment} Database Connection Issues"
  project      = var.project_id
  combiner     = "OR"

  conditions {
    display_name = "Failed DB connections"

    condition_threshold {
      filter          = <<-EOT
        resource.type="cloudsql_database"
        metric.type="cloudsql.googleapis.com/database/network/connections"
        resource.labels.database_id="${var.project_id}:${var.environment}-langfuse-db"
      EOT
      duration        = "300s"
      comparison      = "COMPARISON_LT"
      threshold_value = 1

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_MEAN"
      }

      trigger {
        count = 1
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.id]

  alert_strategy {
    auto_close = "86400s"
  }

  severity = "CRITICAL"
}

# Notification channel
resource "google_monitoring_notification_channel" "email" {
  display_name = "${var.environment} Alert Email"
  project      = var.project_id
  type         = "email"

  labels = {
    email_address = var.alert_email
  }
}

# Custom dashboard
resource "google_monitoring_dashboard" "main" {
  project        = var.project_id
  dashboard_json = jsonencode({
    displayName = "${var.environment} AI Reviewer Dashboard"
    gridLayout = {
      columns = "2"
      widgets = [
        {
          title = "API Request Rate"
          xyChart = {
            dataSets = [{
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = <<-EOT
                    resource.type="cloud_run_revision"
                    metric.type="run.googleapis.com/request_count"
                    resource.labels.service_name="${var.environment}-api-blue"
                  EOT
                  aggregation = {
                    alignmentPeriod    = "60s"
                    perSeriesAligner   = "ALIGN_RATE"
                    crossSeriesReducer = "REDUCE_SUM"
                  }
                }
              }
            }]
          }
        },
        {
          title = "API Latency (p99)"
          xyChart = {
            dataSets = [{
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = <<-EOT
                    resource.type="cloud_run_revision"
                    metric.type="run.googleapis.com/request_latencies"
                    resource.labels.service_name="${var.environment}-api-blue"
                  EOT
                  aggregation = {
                    alignmentPeriod  = "60s"
                    perSeriesAligner = "ALIGN_PERCENTILE_99"
                  }
                }
              }
            }]
          }
        },
        {
          title = "Worker Queue Depth"
          xyChart = {
            dataSets = [{
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = <<-EOT
                    resource.type="pubsub_subscription"
                    metric.type="pubsub.googleapis.com/subscription/num_undelivered_messages"
                    resource.labels.subscription_id="${var.environment}-review-requests-sub"
                  EOT
                }
              }
            }]
          }
        },
        {
          title = "Error Rate"
          xyChart = {
            dataSets = [{
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = <<-EOT
                    resource.type="cloud_run_revision"
                    metric.type="run.googleapis.com/request_count"
                    metric.labels.response_code_class!="2xx"
                    resource.labels.service_name=~"${var.environment}-(api|worker|webhook)"
                  EOT
                  aggregation = {
                    alignmentPeriod    = "60s"
                    perSeriesAligner   = "ALIGN_RATE"
                    crossSeriesReducer = "REDUCE_SUM"
                  }
                }
              }
            }]
          }
        }
      ]
    }
  })
}

# Log-based metrics
resource "google_logging_metric" "review_completed" {
  name   = "${var.environment}/review_completed"
  project = var.project_id
  filter = <<-EOT
    resource.type="cloud_run_revision"
    jsonPayload.message="Review completed"
  EOT
  metric_descriptor {
    metric_kind  = "DELTA"
    value_type   = "INT64"
    unit         = "1"
    labels {
      key         = "repository"
      value_type  = "STRING"
      description = "Repository name"
    }
  }
  label_extractors = {
    "repository" = "EXTRACT(jsonPayload.repository)"
  }
}
