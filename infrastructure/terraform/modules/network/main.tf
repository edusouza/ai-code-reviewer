# Network Module - VPC, Subnets, and Firewall Rules

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0"
    }
  }
}

# VPC Network
resource "google_compute_network" "vpc" {
  name                    = "${var.environment}-vpc"
  project                 = var.project_id
  auto_create_subnetworks = false
  routing_mode            = "GLOBAL"
}

# Subnet for Cloud Run and other services
resource "google_compute_subnetwork" "subnet" {
  name          = "${var.environment}-subnet"
  project       = var.project_id
  network       = google_compute_network.vpc.id
  region        = var.region
  ip_cidr_range = var.subnet_cidr

  private_ip_google_access = true

  log_config {
    aggregation_interval = "INTERVAL_5_SEC"
    flow_sampling        = 0.5
    metadata             = "INCLUDE_ALL_METADATA"
  }
}

# Serverless VPC connector for Cloud Run
resource "google_vpc_access_connector" "connector" {
  name          = "${var.environment}-connector"
  project       = var.project_id
  region        = var.region
  network       = google_compute_network.vpc.id
  ip_cidr_range = var.vpc_connector_cidr
  min_throughput = 200
  max_throughput = 1000
}

# Cloud Router for NAT
resource "google_compute_router" "router" {
  name    = "${var.environment}-router"
  project = var.project_id
  region  = var.region
  network = google_compute_network.vpc.id
}

# Cloud NAT for private instances to access internet
resource "google_compute_router_nat" "nat" {
  name                               = "${var.environment}-nat"
  project                            = var.project_id
  router                             = google_compute_router.router.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}

# Firewall rules
resource "google_compute_firewall" "allow_internal" {
  name    = "${var.environment}-allow-internal"
  project = var.project_id
  network = google_compute_network.vpc.name

  allow {
    protocol = "tcp"
    ports    = ["0-65535"]
  }

  allow {
    protocol = "udp"
    ports    = ["0-65535"]
  }

  allow {
    protocol = "icmp"
  }

  source_ranges = [var.subnet_cidr]
}

resource "google_compute_firewall" "deny_all_ingress" {
  name    = "${var.environment}-deny-all-ingress"
  project = var.project_id
  network = google_compute_network.vpc.name

  deny {
    protocol = "all"
  }

  source_ranges = ["0.0.0.0/0"]
  priority      = 1000
}
